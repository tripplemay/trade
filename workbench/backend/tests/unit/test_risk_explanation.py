"""B043 F003 — risk-explanation precompute job + risk_panel read.

Pins the §12.10.2 architecture split: the job (off the request path) builds the
risk grounding, generates the explanation, and upserts it; the risk panel
(request path) only READS the latest row. Degrades to a row with
``explanation=None`` and an idempotent same-day reuse.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.risk_explanation_snapshot import (
    RiskExplanationSnapshotRepository,
)
from workbench_api.services.explanation import STATUS_OK, ExplanationResult
from workbench_api.services.risk_explanation import (
    _build_grounding,
    run_risk_explanation_precompute,
)
from workbench_api.services.risk_panel import get_risk_panel

_AS_OF = date(2026, 6, 10)


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    sess = sessionmaker(bind=get_engine(), autoflush=False, future=True)()
    yield sess
    sess.close()


class _StubExplainer:
    def __init__(self, result: ExplanationResult | None = None, *, boom: bool = False) -> None:
        self._result = result
        self._boom = boom
        self.calls = 0

    def explain(self, **_kwargs: object) -> ExplanationResult:
        self.calls += 1
        if self._boom:
            raise RuntimeError("budget cap")
        assert self._result is not None
        return self._result


def _ok() -> ExplanationResult:
    return ExplanationResult(
        status=STATUS_OK,
        explanation="The portfolio is in a green risk state with no sleeve past threshold.",
        raw_output="{}",
        model="m",
    )


def test_grounding_includes_real_risk_values(session: Session) -> None:
    panel = get_risk_panel(session)
    text, citable = _build_grounding(panel)
    assert "MASTER_DRAWDOWN" in text and "STATE" in text
    assert panel.state in citable  # the real state is citable


def test_job_writes_explanation_and_panel_reads_it(session: Session) -> None:
    explainer = _StubExplainer(_ok())
    summary = run_risk_explanation_precompute(
        session, explainer=explainer, as_of=_AS_OF  # type: ignore[arg-type]
    )
    assert summary.explained is True and summary.reused is False
    assert explainer.calls == 1
    # Request path (read-only) surfaces the precomputed explanation.
    panel = get_risk_panel(session)
    assert panel.explanation is not None and "green risk state" in panel.explanation


def test_job_idempotent_same_day_reuse(session: Session) -> None:
    explainer = _StubExplainer(_ok())
    run_risk_explanation_precompute(session, explainer=explainer, as_of=_AS_OF)  # type: ignore[arg-type]
    # Second run same day: reuse, no LLM re-call.
    summary = run_risk_explanation_precompute(session, explainer=explainer, as_of=_AS_OF)  # type: ignore[arg-type]
    assert summary.reused is True
    assert explainer.calls == 1  # unchanged


def test_job_degrades_to_null_without_explainer(session: Session) -> None:
    summary = run_risk_explanation_precompute(session, explainer=None, as_of=_AS_OF)
    assert summary.explained is False
    row = RiskExplanationSnapshotRepository(session).latest()
    assert row is not None and row.explanation is None
    assert get_risk_panel(session).explanation is None


def test_job_degrades_on_exception(session: Session) -> None:
    summary = run_risk_explanation_precompute(
        session, explainer=_StubExplainer(boom=True), as_of=_AS_OF  # type: ignore[arg-type]
    )
    assert summary.explained is False
    assert RiskExplanationSnapshotRepository(session).latest().explanation is None  # type: ignore[union-attr]


def test_risk_panel_explanation_none_when_no_snapshot(session: Session) -> None:
    # No job has run → panel renders without an explanation block.
    assert get_risk_panel(session).explanation is None
