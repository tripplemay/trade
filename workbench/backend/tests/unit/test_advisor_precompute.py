"""B036 F002 — daily advisor precompute (offline, fake advisor)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.advisor.precompute import advisor_sleeves, run_daily
from workbench_api.db.engine import get_engine
from workbench_api.db.models.advisor_recommendation import (
    STATUS_INSUFFICIENT_GROUNDING,
    STATUS_OK,
    AdvisorRecommendation,
)
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)
from workbench_api.llm.cost_guard import BudgetExceeded


class _FakeAdvisor:
    """Stand-in for AdvisorService: persists a row per sleeve (or raises)."""

    def __init__(self, *, raise_exc: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._raise = raise_exc

    def advise_sleeve(self, session: Session, sleeve: str) -> AdvisorRecommendation:
        self.calls.append(sleeve)
        if self._raise is not None:
            raise self._raise
        row = AdvisorRecommendation(
            id=uuid4(),
            sleeve=sleeve,
            advice_json={"advice": "a", "rationale": "r"},
            quant_signal_sha="sha256:x",
            references_json=[],
            model="claude-haiku-4.5",
            status=STATUS_OK,
            generated_at=datetime.now(UTC),
        )
        return AdvisorRecommendationRepository(session).save(row)


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(session=session)
    session.close()


def test_advisor_sleeves_are_distinct_and_nonempty() -> None:
    sleeves = advisor_sleeves()
    assert sleeves == sorted(set(sleeves))
    assert len(sleeves) >= 1
    assert "satellite_us_quality" in sleeves


def test_advisor_sleeves_cover_master_active_sleeves() -> None:
    """B046 F002 reconcile: the advisor precomputes for every registry
    sleeve, so the newly surfaced momentum core + hk_china stub now get
    advice generated alongside the pre-existing sleeves (regroups cleanly,
    no duplicates)."""

    sleeves = advisor_sleeves()
    assert sleeves == sorted(set(sleeves))
    for sleeve in ("momentum", "risk_parity", "satellite_us_quality", "satellite_hk_china"):
        assert sleeve in sleeves


def test_run_daily_persists_one_per_sleeve(ctx: SimpleNamespace) -> None:
    advisor = _FakeAdvisor()
    summary = run_daily(ctx.session, advisor)  # type: ignore[arg-type]
    n = len(advisor_sleeves())
    assert summary.saved == n
    assert summary.skipped == 0
    assert summary.errors == 0
    assert sorted(advisor.calls) == advisor_sleeves()


def test_run_daily_is_idempotent_same_day(ctx: SimpleNamespace) -> None:
    advisor = _FakeAdvisor()
    today = datetime.now(UTC).date()
    first = run_daily(ctx.session, advisor, today=today)  # type: ignore[arg-type]
    advisor2 = _FakeAdvisor()
    second = run_daily(ctx.session, advisor2, today=today)  # type: ignore[arg-type]
    assert first.saved == len(advisor_sleeves())
    assert second.saved == 0
    assert second.skipped == len(advisor_sleeves())
    assert advisor2.calls == []  # nothing re-generated → no gateway spend


def test_run_daily_retries_degraded_same_day(ctx: SimpleNamespace) -> None:
    """B053 F002 — a same-day refusal (status=insufficient_grounding) row does
    NOT count as 'already generated'. A second run regenerates it, so one
    transient gateway failure cannot pin a sleeve to the refusal all day."""

    today = datetime.now(UTC).date()
    sleeve = advisor_sleeves()[0]
    AdvisorRecommendationRepository(ctx.session).save(
        AdvisorRecommendation(
            id=uuid4(),
            sleeve=sleeve,
            advice_json={},
            quant_signal_sha="sha256:x",
            references_json=[],
            model="claude-haiku-4.5",
            status=STATUS_INSUFFICIENT_GROUNDING,
            generated_at=datetime.now(UTC),
        )
    )
    ctx.session.commit()

    advisor = _FakeAdvisor()
    summary = run_daily(ctx.session, advisor, today=today)  # type: ignore[arg-type]
    # The degraded sleeve is re-advised (not skipped); every sleeve is saved.
    assert sleeve in advisor.calls
    assert summary.saved == len(advisor_sleeves())
    assert summary.skipped == 0


def test_run_daily_counts_errors_and_continues(ctx: SimpleNamespace) -> None:
    advisor = _FakeAdvisor(raise_exc=BudgetExceeded("monthly cap hit"))
    summary = run_daily(ctx.session, advisor)  # type: ignore[arg-type]
    n = len(advisor_sleeves())
    assert summary.errors == n  # every sleeve raised
    assert summary.saved == 0
    assert len(advisor.calls) == n  # did not stop early
