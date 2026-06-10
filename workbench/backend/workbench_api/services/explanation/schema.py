"""B043 — explanation output contract + grounded-citation validation.

The explanation model is instructed to return JSON only::

    {
      "explanation": "<1-2 sentence plain-language why>",
      "references": ["<input token you used>", ...]
    }

:func:`parse_explanation_output` parses + shape-checks that (tolerating a
markdown code fence, reusing the advisor's ``_strip_code_fence``).
:func:`references_grounded` enforces the citation contract (no-AI boundary (d)):
every cited token must be one the caller marked **citable** (a value actually
present in the grounding input — a sleeve name, signal date, data source, a real
metric label). A fabricated / out-of-set citation downgrades the whole output to
INSUFFICIENT_GROUNDING, exactly as the advisor's ``references_valid`` does.

The α class (forward return-prediction numbers) is held by the system prompt +
the B032 judge, not a regex here — a number check would false-positive on the
legitimate real values the explanation is allowed to restate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from workbench_api.advisor.schema import _strip_code_fence
from workbench_api.llm.judge import INSUFFICIENT_GROUNDING_SIGNAL

__all__ = [
    "INSUFFICIENT_GROUNDING_SIGNAL",
    "ExplanationOutput",
    "parse_explanation_output",
    "references_grounded",
]

# A reference shorter than this is too trivial to prove grounding (a stray ":"
# or digit would substring-match anything); the model's real citations are all
# longer (symbol / sleeve / date / labelled value line).
_MIN_REFERENCE_LEN = 3


@dataclass(frozen=True, slots=True)
class ExplanationOutput:
    explanation: str
    references: list[str]


def parse_explanation_output(raw: str) -> ExplanationOutput:
    """Parse the model's JSON explanation into :class:`ExplanationOutput`.

    Tolerates a surrounding markdown code fence; otherwise raises
    :class:`ValueError` on non-JSON / wrong-shape output so a drifting model
    fails loud (the service catches it → INSUFFICIENT_GROUNDING)."""

    try:
        payload: Any = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Explanation output is not JSON. Head: {raw[:200]!r}") from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"Explanation output must be a JSON object; got {type(payload).__name__}."
        )
    for key in ("explanation", "references"):
        if key not in payload:
            raise ValueError(
                f"Explanation output missing key {key!r}; got {sorted(payload)}."
            )
    refs = payload["references"]
    if not isinstance(refs, list):
        raise ValueError("Explanation output 'references' must be a list.")
    return ExplanationOutput(
        explanation=str(payload["explanation"]).strip(),
        references=[str(ref) for ref in refs],
    )


def references_grounded(output: ExplanationOutput, grounding: str) -> bool:
    """Return ``True`` iff every cited reference appears verbatim in the
    ``grounding`` block (boundary (d)) and there is at least one reference.

    A real model cites grounding tokens in varied forms — the bare value
    (``2026-03-31``), the labelled line (``SIGNAL_DATE: 2026-03-31``), or a
    formatted value (``0.0123``) — all of which are substrings of the grounding
    we provided. A FABRICATED citation (a value/date not in the input — the β/γ
    "no real / off-universe" class) is not a substring and fails the check. An
    explanation with no citation is the β "no citation" class and also fails.
    Case-insensitive; trivially short references don't count as proof."""

    if not output.references:
        return False
    haystack = grounding.lower()
    meaningful = [r.strip() for r in output.references if len(r.strip()) >= _MIN_REFERENCE_LEN]
    if not meaningful:
        return False
    return all(ref.lower() in haystack for ref in meaningful)
