"""TiingoBudgetLog — daily Tiingo API call counts + estimated cost.

One row per UTC date the workbench made at least one Tiingo request.
``month_year`` (``YYYY-MM``) is denormalised onto the row to keep the
per-month total query a single indexed scan rather than a substring
match on ``date``.

The table is append-and-update only — rows are never deleted by
application code. A month rollover means a new row with the next
month's ``month_year`` appears; the previous month's rows stay so
the audit trail covers all of B027/B028 ingest history.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class TiingoBudgetLog(Base):
    __tablename__ = "tiingo_budget_log"

    log_date: Mapped[date] = mapped_column("date", Date, primary_key=True)
    month_year: Mapped[str] = mapped_column(String(7), nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd_est: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return (
            f"TiingoBudgetLog(date={self.log_date!r}, calls={self.call_count}, "
            f"est_usd={self.total_cost_usd_est:.6f})"
        )
