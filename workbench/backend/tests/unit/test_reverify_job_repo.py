"""B080 F003 — ReverifyJobRepository (enqueue/dedup/claim/terminal/recover)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.reverify_job import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from workbench_api.db.repositories.reverify_job import ReverifyJobRepository

_SID = "cn_attack_pure_momentum"


def test_enqueue_dedup_claim_and_terminal(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = ReverifyJobRepository(session)
        job = repo.enqueue(strategy_id=_SID, as_of="2026-06-30")
        session.commit()
        assert job.job_id.startswith("rvf-")
        assert job.status == STATUS_QUEUED
        # Dedup: a still-queued job for the strategy is found.
        assert repo.latest_queued(_SID) is not None

        claimed = repo.claim_next_queued()
        assert claimed is not None and claimed.job_id == job.job_id
        assert claimed.status == STATUS_RUNNING
        # Now running → no longer dedup-blocking a fresh request.
        assert repo.latest_queued(_SID) is None
        # Empty queue → None.
        assert repo.claim_next_queued() is None

        done = repo.save_result(
            job.job_id, report_ref="docs/test-reports/auto/reverify-x.md", verdict="GO"
        )
        assert done is not None and done.status == STATUS_DONE
        assert done.report_ref is not None and done.report_ref.endswith("reverify-x.md")
        assert done.verdict == "GO"
        assert done.finished_at is not None


def test_save_error_and_recover_orphaned(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = ReverifyJobRepository(session)
        j1 = repo.enqueue(strategy_id=_SID)
        repo.claim_next_queued()  # → running
        session.commit()

        # A second job left orphaned running (worker died) is swept to error.
        recovered = repo.recover_orphaned_running(
            error="worker restarted", error_kind="interrupted"
        )
        assert recovered == 1
        row = repo.get_by_id(j1.job_id)
        assert row is not None and row.status == STATUS_ERROR
        assert row.error_kind == "interrupted"

        # save_error path.
        j2 = repo.enqueue(strategy_id=_SID)
        repo.save_error(j2.job_id, "baostock unreachable", error_kind="data")
        row2 = repo.get_by_id(j2.job_id)
        assert row2 is not None and row2.status == STATUS_ERROR
