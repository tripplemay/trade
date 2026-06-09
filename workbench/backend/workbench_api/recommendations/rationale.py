"""B043 F001 — per-position recommendation rationale (grounded LLM "why").

Builds the per-symbol grounding from the Master scoring output (sleeve /
target_weight / planning_weight / sleeve_status / data_source / signal_date) and
asks the shared :class:`ExplanationService` for a short grounded "why this
weight". Degrades to the deterministic placeholder (the pre-B043 text) whenever
the LLM is unavailable / over budget / refuses — the rationale is an enhancement,
never a dependency, so the precompute always writes the snapshot.

Runs inside the recommendations precompute (off the request path, §12.10.2); the
request path only ever reads the stored rationale.
"""

from __future__ import annotations

import logging
from typing import Any

from workbench_api.services.explanation import STATUS_OK, ExplanationService

logger = logging.getLogger(__name__)

RATIONALE_TASK = "recommendation_rationale"

_REQUEST_LINE = (
    "In 1-2 sentences, explain why this position carries this target weight, "
    "grounded in its sleeve, the sleeve's planning weight, and the signal date. "
    "Do not predict future returns."
)


def deterministic_rationale(sleeve: str, data_source: Any) -> str:
    """The honest pre-B043 placeholder — used as the degrade fallback."""

    return (
        f"{sleeve} sleeve target from the Master Portfolio composition "
        f"(data_source={data_source})."
    )


def _build_grounding(
    *,
    symbol: str,
    sleeve: str,
    target_weight: float,
    planning_weight: float | None,
    sleeve_status: str | None,
    data_source: Any,
    signal_date: Any,
) -> tuple[str, set[str]]:
    """Render the grounding block + the set of citable tokens (the real values
    the model is allowed to reference)."""

    grounding = (
        f"SYMBOL: {symbol}\n"
        f"SLEEVE: {sleeve}\n"
        f"TARGET_WEIGHT: {target_weight}\n"
        f"SLEEVE_PLANNING_WEIGHT: {planning_weight}\n"
        f"SLEEVE_STATUS: {sleeve_status}\n"
        f"DATA_SOURCE: {data_source}\n"
        f"SIGNAL_DATE: {signal_date}\n"
    )
    citable = {
        str(token)
        for token in (symbol, sleeve, sleeve_status, data_source, signal_date)
        if token is not None
    }
    return grounding, citable


def generate_rationale(
    explainer: ExplanationService | None,
    *,
    symbol: str,
    sleeve: str,
    target_weight: float,
    planning_weight: float | None,
    sleeve_status: str | None,
    data_source: Any,
    signal_date: Any,
) -> str:
    """Return a grounded rationale, or the deterministic placeholder on degrade.

    ``explainer is None`` (no LLM gateway configured — local / CI) → placeholder.
    A refusal / cost-guard trip / any exception also degrades to the placeholder
    so the precompute never fails on an explanation problem."""

    fallback = deterministic_rationale(sleeve, data_source)
    if explainer is None:
        return fallback

    grounding, citable = _build_grounding(
        symbol=symbol,
        sleeve=sleeve,
        target_weight=target_weight,
        planning_weight=planning_weight,
        sleeve_status=sleeve_status,
        data_source=data_source,
        signal_date=signal_date,
    )
    try:
        result = explainer.explain(
            task=RATIONALE_TASK,
            grounding_text=grounding,
            citable=citable,
            request_line=_REQUEST_LINE,
        )
    except Exception as exc:  # noqa: BLE001 — degrade on budget/HTTP/anything
        logger.warning(
            "recommendation_rationale_generation_failed",
            extra={"symbol": symbol, "error": str(exc)},
        )
        return fallback

    if result.status == STATUS_OK and result.explanation:
        return result.explanation
    return fallback
