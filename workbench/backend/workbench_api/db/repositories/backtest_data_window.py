"""B047-OPS2 F001 — BacktestDataWindowRepository (singleton coverage row).

The data-refresh job upserts the single coverage row after writing the unified
prices CSV; the request-path ``GET /api/backtests/data-range`` reads it (only —
no ``trade`` import, §12.10.2). Keyed by the fixed :data:`SINGLETON_ID` so each
refresh replaces the previous window rather than appending.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from workbench_api.db.models.backtest_data_window import (
    SINGLETON_ID,
    BacktestDataWindow,
)
from workbench_api.db.repositories.base import Repository


class BacktestDataWindowRepository(Repository[BacktestDataWindow, str]):
    model = BacktestDataWindow
    primary_key_attr = "id"

    def upsert_window(
        self,
        *,
        data_start: date,
        data_end: date,
        first_usable_signal_date: date,
        updated_at: datetime | None = None,
    ) -> BacktestDataWindow:
        """Insert or replace the singleton coverage row."""

        stamp = updated_at or datetime.now(UTC)
        existing = self.get_by_id(SINGLETON_ID)
        if existing is None:
            row = BacktestDataWindow(
                id=SINGLETON_ID,
                data_start=data_start,
                data_end=data_end,
                first_usable_signal_date=first_usable_signal_date,
                updated_at=stamp,
            )
            self._session.add(row)
            self._session.flush()
            return row
        existing.data_start = data_start
        existing.data_end = data_end
        existing.first_usable_signal_date = first_usable_signal_date
        existing.updated_at = stamp
        self._session.flush()
        return existing

    def get_window(self) -> BacktestDataWindow | None:
        """Read the singleton coverage row, or ``None`` when no refresh has run."""

        return self.get_by_id(SINGLETON_ID)
