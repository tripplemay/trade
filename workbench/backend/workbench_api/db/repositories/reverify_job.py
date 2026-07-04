"""B080 F003 — ReverifyJobRepository (frozen re-validation queue + result).

Mirrors ``TargetRefreshJobRepository``: request-path ``enqueue`` (no ``trade``
import) + dedup ``latest_queued``; the reverify worker ``claim_next_queued``
(race-safe conditional UPDATE), ``save_result`` / ``save_error`` terminal writes,
and ``recover_orphaned_running`` startup sweep; ``get_by_id`` for polling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from workbench_api.db.models.reverify_job import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
    ReverifyJob,
)
from workbench_api.db.repositories.base import Repository


def _now() -> datetime:
    return datetime.now(UTC)


class ReverifyJobRepository(Repository[ReverifyJob, str]):
    model = ReverifyJob
    primary_key_attr = "job_id"

    def enqueue(
        self,
        *,
        strategy_id: str,
        as_of: str | None = None,
        job_id: str | None = None,
        created_at: datetime | None = None,
    ) -> ReverifyJob:
        row = ReverifyJob(
            job_id=job_id or f"rvf-{uuid.uuid4().hex[:16]}",
            strategy_id=strategy_id,
            status=STATUS_QUEUED,
            as_of=as_of,
            created_at=created_at or _now(),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest_queued(self, strategy_id: str) -> ReverifyJob | None:
        """Newest still-``queued`` job for ``strategy_id`` (enqueue dedup)."""

        stmt = (
            select(ReverifyJob)
            .where(
                ReverifyJob.strategy_id == strategy_id,
                ReverifyJob.status == STATUS_QUEUED,
            )
            .order_by(ReverifyJob.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def claim_next_queued(self) -> ReverifyJob | None:
        """Atomically claim the oldest queued row (``queued → running``)."""

        while True:
            stmt = (
                select(ReverifyJob.job_id)
                .where(ReverifyJob.status == STATUS_QUEUED)
                .order_by(ReverifyJob.created_at, ReverifyJob.job_id)
                .limit(1)
            )
            candidate = self._session.execute(stmt).scalar_one_or_none()
            if candidate is None:
                return None
            result = cast(
                "CursorResult[Any]",
                self._session.execute(
                    update(ReverifyJob)
                    .where(
                        ReverifyJob.job_id == candidate,
                        ReverifyJob.status == STATUS_QUEUED,
                    )
                    .values(status=STATUS_RUNNING)
                ),
            )
            self._session.flush()
            if result.rowcount == 1:
                return self.get_by_id(candidate)

    def save_result(
        self,
        job_id: str,
        *,
        report_ref: str | None,
        verdict: str | None,
        finished_at: datetime | None = None,
    ) -> ReverifyJob | None:
        row = self.get_by_id(job_id)
        if row is None:
            return None
        row.status = STATUS_DONE
        row.report_ref = report_ref
        row.verdict = verdict
        row.error = None
        row.error_kind = None
        row.finished_at = finished_at or _now()
        self._session.flush()
        return row

    def save_error(
        self,
        job_id: str,
        error: str,
        *,
        error_kind: str | None = None,
        finished_at: datetime | None = None,
    ) -> ReverifyJob | None:
        row = self.get_by_id(job_id)
        if row is None:
            return None
        row.status = STATUS_ERROR
        row.error = error
        row.error_kind = error_kind
        row.finished_at = finished_at or _now()
        self._session.flush()
        return row

    def recover_orphaned_running(
        self,
        *,
        error: str,
        error_kind: str,
        finished_at: datetime | None = None,
    ) -> int:
        """Reclaim every ``running`` row as ``error`` (worker-startup orphan sweep)."""

        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(ReverifyJob)
                .where(ReverifyJob.status == STATUS_RUNNING)
                .values(
                    status=STATUS_ERROR,
                    error=error,
                    error_kind=error_kind,
                    finished_at=finished_at or _now(),
                )
            ),
        )
        self._session.flush()
        return result.rowcount or 0

    def get_by_id(self, job_id: str) -> ReverifyJob | None:
        return self._session.get(ReverifyJob, job_id)
