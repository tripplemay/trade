"""LLMBudgetLogRepository — read + increment per-day LLM USD cost.

Two operations beyond the generic Repository surface:

* :py:meth:`get_month_total_usd` aggregates ``total_cost_usd_est``
  across all rows whose ``month_year`` matches the input day. This is
  the value :class:`workbench_api.llm.cost_guard.MonthlyBudgetGuard`
  compares against the monthly budget cap (¥1500 ≈ $200 USD per
  ``docs/product/llm-provider-evaluation-2026-05.md`` §6).
* :py:meth:`increment` upserts the per-day row (insert with
  ``call_count = 1`` + the request's ``cost_usd`` estimate on first
  call of the day, then ``call_count += 1`` and ``total_cost_usd_est
  += cost_usd`` thereafter). Each call also accumulates the call
  count so the audit trail can be cross-checked against the
  aigc-gateway's own log API.

The shape mirrors :class:`workbench_api.db.repositories.budget_log.BudgetLogRepository`
(Tiingo B027) intentionally — a future maintainer reading both can
swap one for the other in their head. The Tiingo guard tracks calls
because Tiingo Starter is flat-rate; the LLM guard tracks dollar
estimates because per-request cost varies by model + token mix.
"""

from __future__ import annotations

from datetime import date as _date

from sqlalchemy import func, select

from workbench_api.db.models.llm_budget_log import LLMBudgetLog
from workbench_api.db.repositories.base import Repository


class LLMBudgetLogRepository(Repository[LLMBudgetLog, _date]):
    model = LLMBudgetLog
    primary_key_attr = "log_date"

    @staticmethod
    def _month_year(day: _date) -> str:
        return day.strftime("%Y-%m")

    def get_month_total_usd(self, day: _date) -> float:
        """Sum ``total_cost_usd_est`` across the calendar month containing ``day``.

        Returns ``0.0`` when the month has no rows yet, matching the
        Tiingo repo's behaviour so the cost guard sees a clean zero
        on the first call of each month.
        """

        stmt = select(func.coalesce(func.sum(self.model.total_cost_usd_est), 0.0)).where(
            self.model.month_year == self._month_year(day),
        )
        return float(self._session.execute(stmt).scalar_one())

    def increment(self, day: _date, cost_usd: float) -> None:
        """Bump ``call_count`` by 1 + accumulate ``cost_usd``, inserting
        the row if absent.

        ``cost_usd`` is the per-request dollar estimate the caller has
        already computed via
        :func:`workbench_api.llm.routing.estimate_cost_usd`. Float
        arithmetic stays stable because the estimate is itself rounded
        to 6 decimals by ``estimate_cost_usd``.
        """

        existing = self.get_by_id(day)
        if existing is None:
            self._session.add(
                LLMBudgetLog(
                    log_date=day,
                    month_year=self._month_year(day),
                    call_count=1,
                    total_cost_usd_est=float(cost_usd),
                )
            )
        else:
            existing.call_count = existing.call_count + 1
            existing.total_cost_usd_est = float(existing.total_cost_usd_est) + float(
                cost_usd
            )
        self._session.flush()
