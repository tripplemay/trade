"""LLMBudgetLog — daily aigc-gateway LLM call counts + estimated cost.

One row per UTC date the workbench backend made at least one LLM
request via :class:`workbench_api.llm.gateway.LLMGateway`. The shape
mirrors :class:`workbench_api.db.models.tiingo_budget_log.TiingoBudgetLog`
(B027) so the two budget-log surfaces share the same query patterns
and operator mental model — a future "data vendor budget log" table
should follow the same template.

``month_year`` (``YYYY-MM``) is denormalised onto the row so the
per-month total query stays a single indexed scan rather than a
substring match on ``date``. ``total_cost_usd_est`` accumulates
the dollar estimate (input_tokens × input_price + output_tokens ×
output_price from :data:`workbench_api.llm.routing.PRICE_TABLE`); the
column is what :class:`workbench_api.llm.cost_guard.MonthlyBudgetGuard`
compares against the monthly cap (¥1500 ≈ $200 USD per
``docs/product/llm-provider-evaluation-2026-05.md`` §6).

The table is append-and-update only — rows are never deleted by
application code, so the audit trail covers all of B031+ ingest
history. A month rollover means a new row with the next month's
``month_year`` appears; the previous month's rows stay.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class LLMBudgetLog(Base):
    __tablename__ = "llm_budget_log"

    log_date: Mapped[date] = mapped_column("date", Date, primary_key=True)
    month_year: Mapped[str] = mapped_column(String(7), nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd_est: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return (
            f"LLMBudgetLog(date={self.log_date!r}, calls={self.call_count}, "
            f"est_usd={self.total_cost_usd_est:.6f})"
        )
