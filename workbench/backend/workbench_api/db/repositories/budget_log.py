"""BudgetLogRepository — read + increment per-day Tiingo call counts.

Two operations beyond the generic Repository surface:

* :py:meth:`get_month_total_calls` aggregates ``call_count`` across all
  rows whose ``month_year`` matches the input day. This is the value
  :class:`workbench_api.data.cost_guard.MonthlyBudgetGuard` compares
  against the monthly budget cap.
* :py:meth:`increment` upserts the per-day row (insert with ``call_count
  = 1`` on first call of the day, then ``+= 1`` thereafter). Each call
  also accumulates ``total_cost_usd_est`` so the audit trail can be
  cross-checked against Tiingo's billing dashboard.

The repository is intentionally session-scoped (like every other
``Repository`` subclass) so callers that need to compose multiple
operations in a single transaction can.
"""

from __future__ import annotations

from datetime import date as _date

from sqlalchemy import func, select

from workbench_api.db.models.tiingo_budget_log import TiingoBudgetLog
from workbench_api.db.repositories.base import Repository


class BudgetLogRepository(Repository[TiingoBudgetLog, _date]):
    model = TiingoBudgetLog
    primary_key_attr = "log_date"

    @staticmethod
    def _month_year(day: _date) -> str:
        return day.strftime("%Y-%m")

    def get_month_total_calls(self, day: _date) -> int:
        """Sum ``call_count`` across the calendar month containing ``day``."""

        stmt = select(func.coalesce(func.sum(self.model.call_count), 0)).where(
            self.model.month_year == self._month_year(day),
        )
        return int(self._session.execute(stmt).scalar_one())

    def increment(self, day: _date, cost_per_call_usd: float) -> None:
        """Bump ``call_count`` for ``day`` by 1, inserting the row if absent."""

        existing = self.get_by_id(day)
        if existing is None:
            self._session.add(
                TiingoBudgetLog(
                    log_date=day,
                    month_year=self._month_year(day),
                    call_count=1,
                    total_cost_usd_est=float(cost_per_call_usd),
                )
            )
        else:
            existing.call_count = existing.call_count + 1
            existing.total_cost_usd_est = float(existing.total_cost_usd_est) + float(
                cost_per_call_usd
            )
        self._session.flush()
