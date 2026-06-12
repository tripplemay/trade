"""B058 F003 — TargetRefreshJobRepository (manual target-refresh queue + result).

Mirrors :class:`BacktestRunRepository` for the on-demand target-refresh flow:

- :meth:`enqueue` — the request path writes a ``queued`` row (no ``trade`` import).
- :meth:`latest_queued` — the enqueue dedup: an in-flight queued job for the same
  strategy is returned instead of spawning a duplicate.
- :meth:`claim_next_queued` — the worker atomically claims the oldest queued row
  (``queued → running``) via a conditional UPDATE, race-safe.
- :meth:`save_result` / :meth:`save_error` — the worker writes the terminal state.
- :meth:`recover_orphaned_running` — worker-startup reclaim of orphaned ``running``
  rows (a previous process died mid-refresh) → ``error`` + ``interrupted``.
- :meth:`get_by_id` — the request path reads status/result for polling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from workbench_api.db.models.target_refresh_job import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
    TargetRefreshJob,
)
from workbench_api.db.repositories.base import Repository


def _now() -> datetime:
    return datetime.now(UTC)


class TargetRefreshJobRepository(Repository[TargetRefreshJob, str]):
    model = TargetRefreshJob
    primary_key_attr = "job_id"

    def enqueue(
        self,
        *,
        strategy_id: str,
        job_id: str | None = None,
        created_at: datetime | None = None,
    ) -> TargetRefreshJob:
        """Insert a ``queued`` row and return it (``job_id`` auto-generated)."""

        row = TargetRefreshJob(
            job_id=job_id or f"trf-{uuid.uuid4().hex[:16]}",
            strategy_id=strategy_id,
            status=STATUS_QUEUED,
            created_at=created_at or _now(),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest_queued(self, strategy_id: str) -> TargetRefreshJob | None:
        """The newest still-``queued`` job for ``strategy_id`` (dedup lookup).

        Only queued (not yet picked up) jobs dedup — a running job is allowed to
        be superseded by a fresh request, and a never-completing running row must
        not block the strategy from ever refreshing again."""

        stmt = (
            select(TargetRefreshJob)
            .where(
                TargetRefreshJob.strategy_id == strategy_id,
                TargetRefreshJob.status == STATUS_QUEUED,
            )
            .order_by(TargetRefreshJob.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def claim_next_queued(self) -> TargetRefreshJob | None:
        """Atomically claim the oldest queued row (``queued → running``).

        The conditional UPDATE (``WHERE status == 'queued'``) makes the claim safe
        against a worker racing its restarted self: only one UPDATE wins."""

        while True:
            stmt = (
                select(TargetRefreshJob.job_id)
                .where(TargetRefreshJob.status == STATUS_QUEUED)
                .order_by(TargetRefreshJob.created_at, TargetRefreshJob.job_id)
                .limit(1)
            )
            candidate = self._session.execute(stmt).scalar_one_or_none()
            if candidate is None:
                return None
            result = cast(
                "CursorResult[Any]",
                self._session.execute(
                    update(TargetRefreshJob)
                    .where(
                        TargetRefreshJob.job_id == candidate,
                        TargetRefreshJob.status == STATUS_QUEUED,
                    )
                    .values(status=STATUS_RUNNING)
                ),
            )
            self._session.flush()
            if result.rowcount == 1:
                return self.get_by_id(candidate)
            # Lost the race for this row — try the next queued one.

    def save_result(
        self,
        job_id: str,
        *,
        as_of_date: str | None,
        saved_count: int,
        data_source: str | None,
        finished_at: datetime | None = None,
    ) -> TargetRefreshJob | None:
        """Write the produced-target summary and mark the job ``done``."""

        row = self.get_by_id(job_id)
        if row is None:
            return None
        row.status = STATUS_DONE
        row.as_of_date = as_of_date
        row.saved_count = saved_count
        row.data_source = data_source
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
    ) -> TargetRefreshJob | None:
        """Mark the job ``error`` with a message + structured ``error_kind``."""

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
        """Reclaim every ``running`` row as ``error`` (worker-startup orphan sweep,
        same rationale as the backtest worker's B053 F002). Returns the count."""

        result = cast(
            "CursorResult[Any]",
            self._session.execute(
                update(TargetRefreshJob)
                .where(TargetRefreshJob.status == STATUS_RUNNING)
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

    def get_by_id(self, job_id: str) -> TargetRefreshJob | None:
        return self._session.get(TargetRefreshJob, job_id)
