"""B043 F003 — daily risk-explanation precompute job.

Architecture point (§12.10.2): the risk panel is a read-only request path and
must never make an LLM call. So this job runs OFF the request path — it reuses
the risk-panel computation (read-only) to build the grounding, asks the shared
:class:`ExplanationService` for a short grounded "why this risk state", and
upserts the result into ``risk_explanation_snapshot``. The request path
(``risk_panel.get_risk_panel``) only reads the latest row.

The explanation explains the *current* state; it never predicts recovery and
never gives buy/sell instructions (no-AI boundary (b)/(c)). Degrades to a row
with ``explanation=None`` when the LLM is unavailable / over budget / refuses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.repositories.risk_explanation_snapshot import (
    RiskExplanationSnapshotRepository,
)
from workbench_api.schemas.risk_panel import RiskPanelResponse
from workbench_api.services.explanation import STATUS_OK, ExplanationService
from workbench_api.services.risk_panel import get_risk_panel

logger = logging.getLogger(__name__)

RISK_TASK = "risk_explanation"

_REQUEST_LINE = (
    "In 1-2 sentences, explain the current risk state and which sleeves "
    "contribute most to the master drawdown, grounded in the real drawdown "
    "values shown. Do not predict recovery and do not give buy/sell instructions."
)


@dataclass(frozen=True, slots=True)
class RiskExplanationSummary:
    as_of_date: date
    state: str
    explained: bool
    reused: bool


def _build_grounding(panel: RiskPanelResponse) -> str:
    """Render the risk grounding block from the panel values."""

    sleeve_lines = "\n".join(
        f"- {s.sleeve}: {s.drawdown}" for s in panel.per_sleeve_dd
    ) or "- (none)"
    return (
        f"STATE: {panel.state}\n"
        f"MASTER_DRAWDOWN: {panel.master_dd}\n"
        f"KILL_SWITCH_THRESHOLD: {panel.kill_switch_threshold}\n"
        f"KILL_SWITCH_TRIGGERED: {panel.kill_switch_triggered}\n"
        f"PER_SLEEVE_THRESHOLD: {panel.per_sleeve_threshold}\n"
        f"PER_SLEEVE_DRAWDOWNS:\n{sleeve_lines}\n"
        f"VALUATION_BASIS: {panel.valuation_basis}\n"
        f"DEGRADED_SYMBOLS: {panel.degraded_symbols or '(none)'}\n"
    )


def run_risk_explanation_precompute(
    session: Session,
    *,
    explainer: ExplanationService | None = None,
    as_of: date | None = None,
    computed_at: datetime | None = None,
) -> RiskExplanationSummary:
    """Compute the risk grounding + generate + upsert the explanation.

    Idempotent: when a row for ``as_of`` already has an explanation it is reused
    (no LLM re-call). ``explainer is None`` (no gateway key — local / CI) → the
    row is written with ``explanation=None`` (the panel shows no explanation
    block). A refusal / cost-guard trip / exception degrades the same way."""

    today = as_of or date.today()
    repo = RiskExplanationSnapshotRepository(session)
    existing = repo.latest()
    if existing is not None and existing.as_of_date == today and existing.explanation:
        return RiskExplanationSummary(
            as_of_date=today, state=existing.state, explained=True, reused=True
        )

    panel = get_risk_panel(session)
    explanation: str | None = None
    if explainer is not None:
        grounding = _build_grounding(panel)
        try:
            result = explainer.explain(
                task=RISK_TASK,
                grounding_text=grounding,
                request_line=_REQUEST_LINE,
            )
            explanation = result.explanation if result.status == STATUS_OK else None
        except Exception as exc:  # noqa: BLE001 — degrade on budget/HTTP/anything
            logger.warning("risk_explanation_generation_failed", extra={"error": str(exc)})

    repo.upsert_explanation(
        as_of_date=today,
        master_dd=panel.master_dd,
        state=panel.state,
        explanation=explanation,
        created_at=computed_at or datetime.now(UTC),
    )
    session.commit()
    return RiskExplanationSummary(
        as_of_date=today,
        state=panel.state,
        explained=explanation is not None,
        reused=False,
    )


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """``python -m workbench_api.services.risk_explanation`` — daily timer entry.

    Builds the production explainer (None without the gateway key → row with
    explanation=None) and upserts today's risk-explanation snapshot."""

    import sys

    from sqlalchemy.orm import sessionmaker

    from workbench_api.db.engine import get_engine
    from workbench_api.db.require_production_db import (
        ScratchDatabaseError,
        require_production_db,
    )
    from workbench_api.services.explanation import build_default_explainer

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        require_production_db(entrypoint="risk-explanation")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    session = sessionmaker(bind=get_engine(), autoflush=False, future=True)()
    try:
        summary = run_risk_explanation_precompute(
            session, explainer=build_default_explainer()
        )
    finally:
        session.close()
    print(
        "risk explanation precompute done — "
        f"as_of_date={summary.as_of_date} state={summary.state} "
        f"explained={summary.explained} reused={summary.reused}"
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
