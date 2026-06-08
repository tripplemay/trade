"""B047 F001 — BacktestRunRepository (queue + result store).

Wraps the ``backtest_run`` table for the on-demand async backtest flow:

- :meth:`enqueue` — the request path writes a ``queued`` row and returns its
  ``run_id`` (no ``trade`` import).
- :meth:`claim_next_queued` — the worker atomically claims the oldest queued
  row (``queued → running``). The claim is a **conditional** UPDATE guarded by
  ``status == 'queued'`` so two workers (or a restarted worker racing its
  previous self) can never run the same row twice — the loser's rowcount is 0
  and it tries the next candidate.
- :meth:`save_result` / :meth:`save_error` — the worker writes the terminal
  state (``done`` / ``error``) + ``finished_at``.
- :meth:`get_by_run_id` — the request path reads status/result for polling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from workbench_api.db.models.backtest_run import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
    BacktestRun,
)
from workbench_api.db.repositories.base import Repository


def _now() -> datetime:
    return datetime.now(UTC)


class BacktestRunRepository(Repository[BacktestRun, str]):
    model = BacktestRun
    primary_key_attr = "run_id"

    def enqueue(
        self,
        *,
        strategy_id: str,
        params: dict[str, Any],
        run_id: str | None = None,
        created_at: datetime | None = None,
    ) -> BacktestRun:
        """Insert a ``queued`` row and return it (``run_id`` auto-generated)."""

        row = BacktestRun(
            run_id=run_id or f"bt-{uuid.uuid4().hex[:16]}",
            strategy_id=strategy_id,
            params=params,
            status=STATUS_QUEUED,
            created_at=created_at or _now(),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def claim_next_queued(self) -> BacktestRun | None:
        """Atomically claim the oldest queued row (``queued → running``).

        Returns the claimed row, or ``None`` when the queue is empty. The
        conditional UPDATE (``WHERE status == 'queued'``) makes the claim safe
        against concurrent workers: only one UPDATE affects the row."""

        while True:
            stmt = (
                select(BacktestRun.run_id)
                .where(BacktestRun.status == STATUS_QUEUED)
                .order_by(BacktestRun.created_at, BacktestRun.run_id)
                .limit(1)
            )
            candidate = self._session.execute(stmt).scalar_one_or_none()
            if candidate is None:
                return None
            result = cast(
                "CursorResult[Any]",
                self._session.execute(
                    update(BacktestRun)
                    .where(
                        BacktestRun.run_id == candidate,
                        BacktestRun.status == STATUS_QUEUED,
                    )
                    .values(status=STATUS_RUNNING)
                ),
            )
            self._session.flush()
            if result.rowcount == 1:
                return self.get_by_run_id(candidate)
            # Lost the race for this row — try the next queued one.

    def save_result(
        self,
        run_id: str,
        *,
        metrics: dict[str, Any] | None,
        equity: list[Any] | None,
        allocations: list[Any] | None,
        trades: list[Any] | None,
        report_markdown: str | None,
        finished_at: datetime | None = None,
    ) -> BacktestRun | None:
        """Write the successful result and mark the run ``done``."""

        row = self.get_by_run_id(run_id)
        if row is None:
            return None
        row.status = STATUS_DONE
        row.metrics = metrics
        row.equity = equity
        row.allocations = allocations
        row.trades = trades
        row.report_markdown = report_markdown
        row.error = None
        row.error_kind = None
        row.finished_at = finished_at or _now()
        self._session.flush()
        return row

    def save_error(
        self,
        run_id: str,
        error: str,
        *,
        error_kind: str | None = None,
        finished_at: datetime | None = None,
    ) -> BacktestRun | None:
        """Mark the run ``error`` with a message + structured ``error_kind``.

        ``error_kind`` (B047-OPS2 F001) is the stable code the frontend i18n
        maps to a bilingual friendly message; ``error`` keeps the raw text for
        diagnostics / logs."""

        row = self.get_by_run_id(run_id)
        if row is None:
            return None
        row.status = STATUS_ERROR
        row.error = error
        row.error_kind = error_kind
        row.finished_at = finished_at or _now()
        self._session.flush()
        return row

    def get_by_run_id(self, run_id: str) -> BacktestRun | None:
        return self._session.get(BacktestRun, run_id)
