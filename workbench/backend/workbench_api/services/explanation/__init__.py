"""B043 — shared grounded-explanation layer.

A thin reuse wrapper over the B031 LLM gateway + B036 advisor guardrail chain,
producing short "why" explanations grounded strictly in already-computed values
(sleeve weights / backtest metrics / risk drawdowns). Used by three injection
points — all OFF the request path (§12.10.2): recommendations precompute (F001),
the backtest worker (F002), and a risk-explanation precompute job (F003).
"""

from __future__ import annotations

from workbench_api.services.explanation.schema import (
    ExplanationOutput,
    parse_explanation_output,
    references_grounded,
)
from workbench_api.services.explanation.service import (
    STATUS_INSUFFICIENT_GROUNDING,
    STATUS_OK,
    ExplanationResult,
    ExplanationService,
)

__all__ = [
    "STATUS_INSUFFICIENT_GROUNDING",
    "STATUS_OK",
    "ExplanationOutput",
    "ExplanationResult",
    "ExplanationService",
    "parse_explanation_output",
    "references_grounded",
]
