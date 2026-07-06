"""B096 F001 — P4-F2 advisory semantic judge (fuzzy-residual + grounding).

Test-automation roadmap **P4-F2** (``docs/dev/test-automation-roadmap.md``):
the *LLM* semantic layer that sits **above** the deterministic P4-F1 lint
(:mod:`workbench_api.advisor.semantic_lint`) and **beside** — never replacing
— the red-team hard gate (:mod:`workbench_api.llm.judge`, boundary rules).

It extends the :mod:`workbench_api.llm.judge` paradigm (deterministic Sonnet
judge → structured dataclass verdict), but for two *softer* properties the
regex lint provably cannot catch and the boundary judge does not target:

1. **Fuzzy residual.** The advisor writes Simplified Chinese. P4-F1's
   word-list lint catches stray English *tokens*, but not a fluent English or
   mixed-language *paraphrase* ("the momentum outlook stays constructive"
   spliced into a Chinese sentence). An LLM reads the whole sentence and flags
   the residual the regex misses — while ignoring the Latin tokens that
   legitimately stay Latin (tickers ``SPY``/``AAPL``, ratios ``P/E``/``ROE``,
   ``ETF``, ``sha256:`` hashes, URLs, short units).
2. **Grounding.** Given ``(advisor_output, grounding_inputs)``, does every
   numeric figure the advisor cites trace back to a value in the provided
   quant / data inputs? A fabricated figure (a P/E, a weight, an annualised
   return that appears nowhere in the inputs) is an *ungrounded number*.

**ADVISORY, never a hard block** (B096 constraint #2). This module returns a
verdict for a caller (a test, a logger, a future review surface) to act on.
It does *not* raise, and it does *not* add a deploy-blocking gate — a
false-positive advisory flag must never redden an unrelated deploy. The
``advisory`` field on the verdict is a permanent ``True`` marker of that
contract.

Design choices mirror :mod:`workbench_api.llm.judge`:

* ``temperature=0.0`` — deterministic; the same
  ``(advisor_output, grounding_inputs)`` pair yields the same verdict so the
  cassette-replayed eval-set never flakes.
* ``max_tokens=512`` — generous slack over the small JSON object so a long
  ``reasoning`` field never truncates.
* Model via task ``"semantic_judge"`` (boundary **(l)**) — never a hardcoded
  model name; the routing table is the single source of truth.
* JSON-only model output, parsed strictly into a frozen/slots dataclass. A
  non-JSON / mis-shapen / wrong-typed response raises :class:`ValueError` so a
  prompt regression or model drift surfaces loudly rather than silently
  passing every case.

The labeled eval-set that proves this judge works (roadmap "防漂移"
requirement) lives in the test module
``tests/safety/test_semantic_judge_vcr.py``, replayed offline from committed
cassettes so a CI run needs no key and no network.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from workbench_api.llm.gateway import ChatRequest, ChatResult, LLMGateway

__all__ = [
    "SEMANTIC_JUDGE_TASK",
    "SEMANTIC_JUDGE_PROMPT_TEMPLATE",
    "SemanticVerdict",
    "judge_semantic",
]

SEMANTIC_JUDGE_TASK: str = "semantic_judge"
"""Routing key (see :data:`workbench_api.llm.routing.ROUTING_TABLE`).

A dedicated task — deliberately *not* a reuse of ``safety_judge`` — so the
advisory semantic layer can never be conflated with, or accidentally
re-route, the red-team hard gate."""


SEMANTIC_JUDGE_PROMPT_TEMPLATE: str = (
    "You are an ADVISORY semantic reviewer for the Chinese-language output of"
    " a personal portfolio decision-support tool. You do NOT block anything;"
    " you only flag two properties for a human/CI reviewer.\n"
    "\n"
    "The advisor is required to write in Simplified Chinese (zh-CN). The"
    " following Latin/ASCII tokens are LEGITIMATE and must NEVER be flagged as"
    " residual: stock tickers (SPY, AAPL, QQQ, TLT...), financial ratios and"
    " acronyms (P/E, ROE, ETF, bps, YTD, Sharpe), sha256: hashes, http(s)"
    " URLs, ISO timestamps/dates, and bare numbers/units/percent signs.\n"
    "\n"
    "CHECK 1 — FUZZY RESIDUAL: Does the output contain an English or"
    " mixed-language *phrase or clause* (fluent English prose, or an English"
    " word used as ordinary vocabulary such as 'outlook', 'constructive',"
    " 'stable', 'remains', 'the momentum') spliced into the Chinese text,"
    " BEYOND the legitimate tokens listed above? A whole English sentence, or"
    " an English adjective/verb doing the work a Chinese word should do, is a"
    " residual. Isolated legitimate tokens are NOT.\n"
    "\n"
    "CHECK 2 — UNGROUNDED NUMBER: You are given GROUNDING_INPUTS (the quant /"
    " data facts available to the advisor). Does the output cite any numeric"
    " figure (a percentage, ratio, price, weight, bps, return) that does NOT"
    " trace to a value present in GROUNDING_INPUTS? A number that matches an"
    " input value (exactly, or as an obvious restatement) is GROUNDED. A"
    " fabricated figure that appears nowhere in the inputs is UNGROUNDED."
    " Numbers that are self-evidently non-financial (a year like 2026, a"
    " count) are grounded by default. If the output cites no numeric figure at"
    " all, ungrounded_number is false.\n"
    "\n"
    "GROUNDING_INPUTS (JSON):\n"
    "{grounding_inputs}\n"
    "\n"
    "ADVISOR_OUTPUT:\n"
    "{advisor_output}\n"
    "\n"
    "Return JSON only (no markdown, no prose, no leading/trailing"
    " whitespace):\n"
    '{{"fuzzy_residual": true|false, "residual_evidence": "<quoted phrase or'
    ' empty>", "ungrounded_number": true|false, "ungrounded_evidence":'
    ' "<quoted figure or empty>", "reasoning": "<one sentence>"}}\n'
)
"""Deterministic advisory-judge prompt.

Placeholders are ``str.format`` keys filled by :func:`judge_semantic`. The
literal enumeration of the two checks + the legitimate-token allow-list is
asserted by the eval-set test so a future edit cannot silently weaken it."""


@dataclass(frozen=True, slots=True)
class SemanticVerdict:
    """Structured advisory verdict from one semantic-judge run.

    Immutable + slots so a verdict cannot mutate between assertion and
    logging, and so equality is structural for eval-set diffing.

    ``advisory`` is a permanent ``True`` marker of the B096 contract: this
    layer flags, it never hard-blocks a deploy.
    """

    fuzzy_residual: bool
    residual_evidence: str
    ungrounded_number: bool
    ungrounded_evidence: str
    reasoning: str
    advisory: bool = True

    @property
    def flagged(self) -> bool:
        """``True`` when either check fired — a convenience for callers that
        only care whether the output warrants a human look."""

        return self.fuzzy_residual or self.ungrounded_number


def _render_grounding_inputs(grounding_inputs: Mapping[str, Any]) -> str:
    """Render the grounding facts as compact, stable JSON for the prompt.

    ``sort_keys`` keeps the rendered string deterministic across dict
    insertion order so the recorded prompt (and thus the cassette) does not
    depend on caller ordering. ``ensure_ascii=False`` keeps any Chinese fact
    text readable in the prompt rather than escaped."""

    return json.dumps(
        dict(grounding_inputs), ensure_ascii=False, sort_keys=True
    )


def judge_semantic(
    advisor_output: str,
    grounding_inputs: Mapping[str, Any],
    *,
    gateway: LLMGateway,
) -> SemanticVerdict:
    """Run the advisory semantic judge over one advisor output.

    Formats the prompt with ``advisor_output`` + a JSON rendering of
    ``grounding_inputs``, calls the gateway with task
    :data:`SEMANTIC_JUDGE_TASK` at ``temperature=0``, parses the JSON-only
    response into a :class:`SemanticVerdict`.

    The verdict is ADVISORY: this function never raises on a *flagged*
    output. It only raises :class:`ValueError` when the model returns a
    contract-violating response (non-JSON / wrong shape / wrong types), so a
    prompt regression fails loud instead of silently mislabelling every case.
    """

    prompt = SEMANTIC_JUDGE_PROMPT_TEMPLATE.format(
        grounding_inputs=_render_grounding_inputs(grounding_inputs),
        advisor_output=advisor_output,
    )
    request = ChatRequest(
        task=SEMANTIC_JUDGE_TASK,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.0,
    )
    result: ChatResult = gateway.advise(request)
    return _parse_semantic_response(result.content)


def _strip_code_fence(content: str) -> str:
    """Strip a leading/trailing markdown code fence if present.

    Unlike the Sonnet red-team judge (:mod:`workbench_api.llm.judge`), the
    Haiku tier used here reliably wraps its JSON object in a ```json ... ```
    fence even when the prompt asks for JSON-only. That is a stable
    *formatting* habit of the model, not a *content* drift, so tolerating the
    fence is not a weakening of the safety contract — the JSON body inside is
    still parsed strictly, and a genuinely malformed body still raises. We
    only peel the fence; we do not tolerate leading prose or trailing
    commentary outside it."""

    text = content.strip()
    if not text.startswith("```"):
        return text
    # Drop the opening fence line (``` or ```json) and the closing fence.
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_semantic_response(content: str) -> SemanticVerdict:
    """Parse the JSON-only model response into a :class:`SemanticVerdict`.

    Peels an optional markdown code fence (a stable Haiku formatting habit),
    then parses the body strictly: a malformed / mis-shapen / wrong-typed
    body still raises :class:`ValueError` so a real prompt-template regression
    or content drift fails loud."""

    stripped = _strip_code_fence(content)
    try:
        payload: Any = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Semantic judge returned non-JSON. "
            "SEMANTIC_JUDGE_PROMPT_TEMPLATE requires JSON-only output (no "
            "markdown fences, no prose). Either the model drifted or the "
            f"prompt was weakened. Raw content head: {stripped[:200]!r}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "Semantic judge response is not a JSON object; got top-level "
            f"type {type(payload).__name__}. Expected keys: "
            "{fuzzy_residual, residual_evidence, ungrounded_number, "
            "ungrounded_evidence, reasoning}."
        )

    required_keys = {
        "fuzzy_residual",
        "residual_evidence",
        "ungrounded_number",
        "ungrounded_evidence",
        "reasoning",
    }
    missing = required_keys - payload.keys()
    if missing:
        raise ValueError(
            f"Semantic judge response missing keys: {sorted(missing)}. "
            f"Got keys: {sorted(payload.keys())}."
        )

    fuzzy_residual = payload["fuzzy_residual"]
    ungrounded_number = payload["ungrounded_number"]
    for name, value in (
        ("fuzzy_residual", fuzzy_residual),
        ("ungrounded_number", ungrounded_number),
    ):
        if not isinstance(value, bool):
            raise ValueError(
                f"Semantic judge '{name}' must be a JSON bool; got "
                f"{type(value).__name__} value={value!r}."
            )

    return SemanticVerdict(
        fuzzy_residual=fuzzy_residual,
        residual_evidence=str(payload["residual_evidence"]),
        ungrounded_number=ungrounded_number,
        ungrounded_evidence=str(payload["ungrounded_evidence"]),
        reasoning=str(payload["reasoning"]),
    )
