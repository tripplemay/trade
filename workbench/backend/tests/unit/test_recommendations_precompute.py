"""B044 F002 — recommendation_snapshot repo + Master scoring precompute.

Covers RecommendationSnapshotRepository (save_batch idempotency + latest),
run_precompute with an injected fake scorer (write + data_source marking +
graceful failure), and the real ``trade`` Master Portfolio scoring on the
bundled fixture (data_source=fixture, non-equal-weight, momentum scored).

The real-scoring tests import ``trade`` — installed into the env by B044 F001
(repo-root package). They assert the closed loop produces a non-equal-weight
target, NOT a specific performance conclusion (v0.9.21 fixture-vs-real signal).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.recommendation_snapshot import DATA_SOURCE_FIXTURE
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.recommendations.precompute import (
    MasterTargetResult,
    run_precompute,
    score_master_target,
)

_AS_OF = date(2024, 12, 31)
_META = {"data_source": DATA_SOURCE_FIXTURE, "planning_weights": {"momentum": 0.4}}


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _rows() -> list[dict[str, object]]:
    return [
        {"symbol": "SPY", "sleeve": "momentum", "target_weight": 0.2, "rationale": "r1"},
        {"symbol": "EEM", "sleeve": "momentum", "target_weight": 0.2, "rationale": "r2"},
        {"symbol": "SGOV", "sleeve": "risk_parity", "target_weight": 0.6, "rationale": "r3"},
    ]


# --- RecommendationSnapshotRepository --------------------------------------


def test_save_batch_writes_rows(session: Session) -> None:
    repo = RecommendationSnapshotRepository(session)
    saved = repo.save_batch(as_of_date=_AS_OF, rows=_rows(), master_meta=_META)
    assert len(saved) == 3
    assert {r.symbol for r in saved} == {"SPY", "EEM", "SGOV"}
    assert all(r.master_meta["data_source"] == DATA_SOURCE_FIXTURE for r in saved)


def test_save_batch_idempotent_overwrite(session: Session) -> None:
    repo = RecommendationSnapshotRepository(session)
    repo.save_batch(as_of_date=_AS_OF, rows=_rows(), master_meta=_META)
    # Re-run same date with a different (single-row) target → replaces, not dup.
    repo.save_batch(
        as_of_date=_AS_OF,
        rows=[{"symbol": "SPY", "sleeve": "momentum", "target_weight": 1.0}],
        master_meta=_META,
    )
    latest = repo.latest_snapshot()
    assert len(latest) == 1
    assert latest[0].symbol == "SPY"
    assert latest[0].target_weight == pytest.approx(1.0)


def test_save_batch_denormalises_master_meta(session: Session) -> None:
    repo = RecommendationSnapshotRepository(session)
    saved = repo.save_batch(
        as_of_date=_AS_OF, rows=_rows(), master_meta={"data_source": "fixture", "x": 1}
    )
    assert all(r.master_meta["x"] == 1 for r in saved)


def test_latest_snapshot_returns_latest_date_ordered(session: Session) -> None:
    repo = RecommendationSnapshotRepository(session)
    repo.save_batch(as_of_date=date(2024, 9, 30), rows=_rows(), master_meta=_META)
    repo.save_batch(as_of_date=_AS_OF, rows=_rows(), master_meta=_META)
    latest = repo.latest_snapshot()
    assert {r.as_of_date for r in latest} == {_AS_OF}  # only the newest date
    weights = [r.target_weight for r in latest]
    assert weights == sorted(weights, reverse=True)  # ordered by weight desc


def test_latest_snapshot_empty(session: Session) -> None:
    repo = RecommendationSnapshotRepository(session)
    assert repo.latest_snapshot() == []


# --- run_precompute with an injected fake scorer ---------------------------


def _fake_result() -> MasterTargetResult:
    return MasterTargetResult(
        as_of_date=_AS_OF,
        target_weights={"SPY": 0.2, "EEM": 0.2, "SGOV": 0.6},
        symbol_sleeve={"SPY": "momentum", "EEM": "momentum", "SGOV": "risk_parity"},
        master_meta={"data_source": DATA_SOURCE_FIXTURE, "planning_weights": {}},
    )


def test_run_precompute_with_fake_scorer_writes_and_marks_data_source(
    session: Session,
) -> None:
    summary = run_precompute(session, score_fn=_fake_result)
    assert summary.saved == 3
    assert summary.data_source == DATA_SOURCE_FIXTURE
    assert summary.error is None
    repo = RecommendationSnapshotRepository(session)
    assert len(repo.latest_snapshot()) == 3


def test_run_precompute_graceful_on_score_failure(session: Session) -> None:
    def _boom() -> MasterTargetResult:
        raise RuntimeError("scoring unavailable")

    summary = run_precompute(session, score_fn=_boom)
    assert summary.saved == 0
    assert summary.error is not None
    repo = RecommendationSnapshotRepository(session)
    assert repo.latest_snapshot() == []  # nothing written on failure


# --- real trade Master Portfolio scoring on the bundled fixture ------------


def test_score_master_target_runs_real_master_scoring_on_fixture() -> None:
    result = score_master_target()
    assert result.master_meta["data_source"] == DATA_SOURCE_FIXTURE
    # Weights are a valid portfolio (sum ~ 1.0).
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-4)
    # Per-sleeve status is recorded honestly (real scoring code ran).
    assert set(result.master_meta["sleeve_status"]) == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }


def test_score_master_target_is_non_equal_weight() -> None:
    # The whole point: real composition, not the old equal-weight placeholder.
    result = score_master_target()
    weights = list(result.target_weights.values())
    assert len(weights) >= 2
    assert len(set(round(w, 6) for w in weights)) > 1  # not all-identical


def test_run_precompute_real_writes_snapshot(session: Session) -> None:
    summary = run_precompute(
        session, score_fn=score_master_target, computed_at=datetime(2026, 6, 6, tzinfo=UTC)
    )
    assert summary.error is None
    assert summary.saved >= 2
    assert summary.data_source == DATA_SOURCE_FIXTURE
    repo = RecommendationSnapshotRepository(session)
    rows = repo.latest_snapshot()
    assert len(rows) == summary.saved
    assert all(r.master_meta["data_source"] == DATA_SOURCE_FIXTURE for r in rows)
