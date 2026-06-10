"""B047 F001 — BacktestRunRepository (queue + result store).

Pins the queue semantics the async worker depends on: enqueue writes a queued
row, claim_next_queued hands out the oldest queued row exactly once
(queued → running, never double-claimed), and save_result / save_error write
the terminal state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.backtest_run import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from workbench_api.db.repositories.backtest_run import BacktestRunRepository

_T0 = datetime(2026, 6, 8, 10, 0, 0, tzinfo=UTC)


def _params() -> dict[str, object]:
    return {"snapshot_id": "snap-1", "start_date": "2024-01-01", "end_date": "2024-12-31"}


def test_enqueue_writes_queued_row(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        row = repo.enqueue(strategy_id="momentum", params=_params(), created_at=_T0)
        session.commit()
        assert row.run_id.startswith("bt-")
        assert row.status == STATUS_QUEUED
        fetched = repo.get_by_run_id(row.run_id)
        assert fetched is not None
        assert fetched.strategy_id == "momentum"
        assert fetched.params["snapshot_id"] == "snap-1"
        assert fetched.metrics is None and fetched.finished_at is None


def test_claim_next_queued_is_fifo_and_single_claim(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        first = repo.enqueue(
            strategy_id="momentum", params=_params(),
            created_at=datetime(2026, 6, 8, 10, 0, 0, tzinfo=UTC),
        )
        second = repo.enqueue(
            strategy_id="risk_parity", params=_params(),
            created_at=datetime(2026, 6, 8, 10, 5, 0, tzinfo=UTC),
        )
        session.commit()

        claimed1 = repo.claim_next_queued()
        assert claimed1 is not None
        assert claimed1.run_id == first.run_id  # oldest first
        assert claimed1.status == STATUS_RUNNING

        claimed2 = repo.claim_next_queued()
        assert claimed2 is not None
        assert claimed2.run_id == second.run_id  # never re-claims the running one

        # Queue drained — both are running, nothing left to claim.
        assert repo.claim_next_queued() is None
        session.commit()


def test_claim_empty_queue_returns_none(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        assert repo.claim_next_queued() is None


def test_save_result_marks_done(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        row = repo.enqueue(strategy_id="momentum", params=_params(), created_at=_T0)
        repo.claim_next_queued()
        done = repo.save_result(
            row.run_id,
            metrics={"cagr": 0.1, "sharpe": 1.2},
            equity=[{"date": "2024-01-01", "nav": 100.0}],
            allocations=[{"date": "2024-01-01", "weights": {"SPY": 1.0}}],
            trades=[{"date": "2024-01-02", "symbol": "SPY", "side": "buy"}],
            report_markdown="# Backtest report",
            finished_at=datetime(2026, 6, 8, 10, 1, 0, tzinfo=UTC),
        )
        session.commit()
        assert done is not None
        assert done.status == STATUS_DONE
        assert done.metrics is not None and done.equity is not None
        assert done.metrics["sharpe"] == 1.2
        assert done.equity[0]["nav"] == 100.0
        assert done.report_markdown == "# Backtest report"
        assert done.finished_at is not None
        assert done.error is None


def test_save_error_marks_error(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        row = repo.enqueue(strategy_id="momentum", params=_params(), created_at=_T0)
        repo.claim_next_queued()
        errored = repo.save_error(row.run_id, "engine blew up")
        session.commit()
        assert errored is not None
        assert errored.status == STATUS_ERROR
        assert errored.error == "engine blew up"
        assert errored.finished_at is not None


def _set_status(repo: BacktestRunRepository, run_id: str, status: str) -> None:
    row = repo.get_by_run_id(run_id)
    assert row is not None
    row.status = status


def test_recover_orphaned_running_reclaims_all_running(initialised_db: str) -> None:
    """B053 F002 — at worker startup every ``running`` row is an orphan (a
    single-instance daemon has none legitimately in flight); recovery flips
    them to ``error`` + the supplied error_kind and stamps finished_at, while
    leaving queued / done rows untouched. Returns the reclaimed count."""

    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)

        # Capture run_ids as plain strings so they survive after the session
        # closes (ORM objects would detach).
        def _enqueue(strategy_id: str) -> str:
            return repo.enqueue(
                strategy_id=strategy_id, params=_params(), created_at=_T0
            ).run_id

        running1_id = _enqueue("momentum")
        running2_id = _enqueue("risk_parity")
        queued_id = _enqueue("master_portfolio")
        done_id = _enqueue("momentum")
        # Construct the exact pre-state directly (no reliance on claim order).
        _set_status(repo, running1_id, STATUS_RUNNING)
        _set_status(repo, running2_id, STATUS_RUNNING)
        _set_status(repo, done_id, STATUS_DONE)
        session.commit()

    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        reclaimed = repo.recover_orphaned_running(
            error="worker restarted while this run was in progress; please re-run",
            error_kind="interrupted",
            finished_at=datetime(2026, 6, 8, 11, 0, 0, tzinfo=UTC),
        )
        session.commit()
        assert reclaimed == 2  # only the two running rows
        for rid in (running1_id, running2_id):
            row = repo.get_by_run_id(rid)
            assert row is not None
            assert row.status == STATUS_ERROR
            assert row.error_kind == "interrupted"
            assert "please re-run" in (row.error or "")
            assert row.finished_at is not None
        assert repo.get_by_run_id(queued_id).status == STATUS_QUEUED  # type: ignore[union-attr]
        assert repo.get_by_run_id(done_id).status == STATUS_DONE  # type: ignore[union-attr]


def test_recover_orphaned_running_no_running_returns_zero(initialised_db: str) -> None:
    """No ``running`` rows → a clean startup reclaims nothing."""

    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        repo.enqueue(strategy_id="momentum", params=_params(), created_at=_T0)
        session.commit()
        assert (
            repo.recover_orphaned_running(error="x", error_kind="interrupted") == 0
        )


def test_save_on_unknown_run_id_returns_none(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        assert repo.get_by_run_id("bt-does-not-exist") is None
        assert (
            repo.save_result(
                "bt-nope", metrics=None, equity=None, allocations=None,
                trades=None, report_markdown=None,
            )
            is None
        )
        assert repo.save_error("bt-nope", "x") is None
