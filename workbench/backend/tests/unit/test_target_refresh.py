"""B058 F003 — manual target-refresh primitive (enqueue + async worker + poll).

Covers the request-path enqueue/dedup/poll (no ``trade`` import), the off-path
worker processing (done / empty-target / producer-error / interrupted), the
dispatch wiring (Master + regime), and the §12.10.2 boundary (the route + service
never import ``trade`` or the refresh worker).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.target_refresh_job import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.db.repositories.target_refresh_job import TargetRefreshJobRepository
from workbench_api.strategy_modes.refresh_worker import (
    _DISPATCH,
    ERROR_EMPTY,
    ERROR_INTERRUPTED,
    ERROR_PRODUCER,
    ProducerResult,
    process_next_refresh,
    recover_orphaned_refresh,
)
from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID, REGIME_STRATEGY_ID
from workbench_api.strategy_modes.service import (
    UnknownStrategyModeError,
    enqueue_target_refresh,
    get_target_refresh_job,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


# --- enqueue / dedup / poll (request path) ---------------------------------


def test_enqueue_creates_queued_job(session: Session) -> None:
    resp = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    assert resp.strategy_id == REGIME_STRATEGY_ID
    assert resp.status == STATUS_QUEUED
    assert resp.job_id
    row = TargetRefreshJobRepository(session).get_by_id(resp.job_id)
    assert row is not None and row.status == STATUS_QUEUED


def test_enqueue_dedups_inflight_queued_job(session: Session) -> None:
    first = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    second = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    # The queued job is reused — no duplicate spawn.
    assert second.job_id == first.job_id


def test_enqueue_unknown_strategy_raises(session: Session) -> None:
    with pytest.raises(UnknownStrategyModeError):
        enqueue_target_refresh(session, "not_a_real_mode")


def test_get_target_refresh_job_unknown_is_none(session: Session) -> None:
    assert get_target_refresh_job(session, "trf-does-not-exist") is None


# --- worker processing (off the request path) ------------------------------


def _seed_target_dispatch(
    saved: int = 2, *, error: str | None = None
) -> dict[str, object]:
    """A fake dispatch whose producer writes a recommendation_snapshot (or fails),
    so the worker flow is tested without importing ``trade``."""

    def _producer(session: Session) -> ProducerResult:
        if error is None and saved > 0:
            RecommendationSnapshotRepository(session).save_batch(
                strategy_id=REGIME_STRATEGY_ID,
                as_of_date=date(2026, 6, 12),
                rows=[
                    {"symbol": "SPY", "sleeve": "risk_core", "target_weight": 0.6},
                    {"symbol": "SGOV", "sleeve": "defensive", "target_weight": 0.4},
                ],
                master_meta={"data_source": "fixture"},
            )
            session.commit()
        return ProducerResult(
            saved=saved,
            as_of_date="2026-06-12",
            data_source="fixture",
            error=error,
        )

    return {REGIME_STRATEGY_ID: _producer}


def test_process_next_refresh_runs_producer_and_marks_done(session: Session) -> None:
    job = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    handled = process_next_refresh(session, dispatch=_seed_target_dispatch(saved=2))
    assert handled is True

    status = get_target_refresh_job(session, job.job_id)
    assert status is not None
    assert status.status == STATUS_DONE
    assert status.saved_count == 2
    assert status.as_of_date == "2026-06-12"
    assert status.data_source == "fixture"
    # The producer actually wrote the target.
    rows = RecommendationSnapshotRepository(session).latest_snapshot(
        strategy_id=REGIME_STRATEGY_ID
    )
    assert {r.symbol for r in rows} == {"SPY", "SGOV"}


def test_process_next_refresh_empty_target_is_error(session: Session) -> None:
    job = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    process_next_refresh(session, dispatch=_seed_target_dispatch(saved=0))
    status = get_target_refresh_job(session, job.job_id)
    assert status is not None and status.status == STATUS_ERROR
    assert status.error_kind == ERROR_EMPTY


def test_process_next_refresh_producer_reported_error_is_error(session: Session) -> None:
    job = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    process_next_refresh(
        session, dispatch=_seed_target_dispatch(saved=0, error="data unavailable")
    )
    status = get_target_refresh_job(session, job.job_id)
    assert status is not None and status.status == STATUS_ERROR
    assert status.error_kind == ERROR_PRODUCER
    assert status.error == "data unavailable"


def test_process_next_refresh_raising_producer_is_error(session: Session) -> None:
    def _boom(_session: Session) -> ProducerResult:
        raise RuntimeError("scoring blew up")

    job = enqueue_target_refresh(session, REGIME_STRATEGY_ID)
    handled = process_next_refresh(session, dispatch={REGIME_STRATEGY_ID: _boom})
    assert handled is True
    status = get_target_refresh_job(session, job.job_id)
    assert status is not None and status.status == STATUS_ERROR
    assert status.error_kind == ERROR_PRODUCER
    assert "scoring blew up" in (status.error or "")


def test_process_next_refresh_empty_queue_returns_false(session: Session) -> None:
    assert process_next_refresh(session, dispatch=_seed_target_dispatch()) is False


def test_recover_orphaned_refresh_marks_running_as_interrupted(session: Session) -> None:
    repo = TargetRefreshJobRepository(session)
    repo.enqueue(strategy_id=REGIME_STRATEGY_ID, job_id="trf-orphan")
    claimed = repo.claim_next_queued()  # queued → running
    assert claimed is not None and claimed.job_id == "trf-orphan"
    session.commit()

    reclaimed = recover_orphaned_refresh(session)
    assert reclaimed == 1
    status = get_target_refresh_job(session, "trf-orphan")
    assert status is not None and status.status == STATUS_ERROR
    assert status.error_kind == ERROR_INTERRUPTED


# --- dispatch wiring + boundary --------------------------------------------


def test_dispatch_wires_master_and_regime() -> None:
    assert MASTER_STRATEGY_ID in _DISPATCH
    assert REGIME_STRATEGY_ID in _DISPATCH


def _imported_modules(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_request_path_does_not_import_trade_or_refresh_worker() -> None:
    """§12.10.2: the route + service (request path) must never import ``trade``
    or the refresh worker (which imports trade). The worker runs off-path."""

    for rel in (
        "workbench_api/routes/strategy_modes.py",
        "workbench_api/strategy_modes/service.py",
    ):
        modules = _imported_modules(_BACKEND_ROOT / rel)
        assert not any(
            m == "trade" or m.startswith("trade.") for m in modules
        ), f"{rel} imports trade on the request path"
        assert "workbench_api.strategy_modes.refresh_worker" not in modules, (
            f"{rel} imports the refresh worker (pulls trade) onto the request path"
        )
