"""B036 F001 — advisor output contract + reference validation.

The advisor model is instructed to return JSON only::

    {
      "advice": "<short qualitative guidance>",
      "rationale": "<why, grounded in the inputs>",
      "references": [
        {"quant_signal_sha": "sha256:...", "news_urls": ["https://..."]}
      ]
    }

:func:`parse_advice_output` parses + shape-checks that. :func:`references_valid`
enforces the **citation contract** (v0.9.28 boundary (d)): every cited
``quant_signal_sha`` must equal the grounding's sha and every ``news_url``
must be in the grounding's news-URL set. A fabricated or out-of-set
citation (the β "no real citation" / γ "off-universe" red-team classes)
fails the check, and the service downgrades the whole output to
``INSUFFICIENT_GROUNDING``. This is pure Python so the unit tests and the
red-team gate share one validator.

Note this validator covers β/γ structurally; the α class (forward
return-prediction numbers) is caught by the system-prompt boundary + the
Sonnet judge, not here — a regex over the advice text would false-positive
on legitimate weight percentages and market-context numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from workbench_api.advisor.grounding import Grounding
from workbench_api.llm.judge import INSUFFICIENT_GROUNDING_SIGNAL

__all__ = [
    "INSUFFICIENT_GROUNDING_SIGNAL",
    "AdviceOutput",
    "AdviceReference",
    "parse_advice_output",
    "references_valid",
]


@dataclass(frozen=True, slots=True)
class AdviceReference:
    quant_signal_sha: str
    news_urls: list[str]


@dataclass(frozen=True, slots=True)
class AdviceOutput:
    advice: str
    rationale: str
    references: list[AdviceReference]


def _strip_code_fence(raw: str) -> str:
    """Strip a surrounding markdown code fence if present.

    Despite the JSON-only instruction, some models (verified: haiku-4.5
    2026-06-05) wrap the object in a ```json ... ``` fence. Tolerating
    that here keeps a *compliant* answer from being wrongly downgraded to
    INSUFFICIENT_GROUNDING. The judge still evaluates the original output
    semantically, so this leniency does not weaken the safety boundary.
    """

    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_advice_output(raw: str) -> AdviceOutput:
    """Parse the model's JSON advice output into :class:`AdviceOutput`.

    Tolerates a surrounding markdown code fence (see :func:`_strip_code_fence`)
    but otherwise raises :class:`ValueError` on non-JSON / wrong-shape output
    so a model that drifts off the contract fails loud (the service catches
    it and downgrades to ``INSUFFICIENT_GROUNDING``).
    """

    try:
        payload: Any = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Advisor output is not JSON. Head: {raw[:200]!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"Advisor output must be a JSON object; got {type(payload).__name__}."
        )
    for key in ("advice", "rationale", "references"):
        if key not in payload:
            raise ValueError(f"Advisor output missing key {key!r}; got {sorted(payload)}.")
    raw_refs = payload["references"]
    if not isinstance(raw_refs, list):
        raise ValueError("Advisor output 'references' must be a list.")
    references: list[AdviceReference] = []
    for ref in raw_refs:
        if not isinstance(ref, dict) or "quant_signal_sha" not in ref or "news_urls" not in ref:
            raise ValueError(f"Advisor reference malformed: {ref!r}")
        urls = ref["news_urls"]
        if not isinstance(urls, list):
            raise ValueError("Advisor reference 'news_urls' must be a list.")
        references.append(
            AdviceReference(
                quant_signal_sha=str(ref["quant_signal_sha"]),
                news_urls=[str(u) for u in urls],
            )
        )
    return AdviceOutput(
        advice=str(payload["advice"]),
        rationale=str(payload["rationale"]),
        references=references,
    )


def references_valid(output: AdviceOutput, grounding: Grounding) -> bool:
    """Return ``True`` iff the output's citations are all inside the input
    set (boundary (d)).

    Requires at least one reference (an actionable advice with no citation
    is the β failure class), every reference's ``quant_signal_sha`` to equal
    the grounding's sha, and every cited ``news_url`` to be in the grounding's
    news-URL set (a fabricated / off-universe URL is the β/γ failure class).
    """

    if not output.references:
        return False
    valid_urls = grounding.news_urls
    for ref in output.references:
        if ref.quant_signal_sha != grounding.quant_signal_sha:
            return False
        for url in ref.news_urls:
            if url not in valid_urls:
                return False
    return True
