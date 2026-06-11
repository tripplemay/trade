"""B056 F002 — paper_nav_history model (daily forward MTM points).

One row per (paper account, date): the account's mark-to-market NAV that day,
its cash, the per-position breakdown (for the per-asset P&L table + audit), and
the benchmark (SPY) close that day (the F003 §② SPY overlay normalises the SPY
series to the account's initial capital). Written by the daily MTM job
(``workbench-paper-mtm`` timer) — forward-only, one point per day, accumulating
from the activation day. Idempotent on ``(account_id, as_of_date)`` so a same-day
re-run overwrites rather than duplicates.

``positions`` is JSON: a list of ``{symbol, shares, avg_cost, close,
market_value}`` — metadata only (no raw body), self-describing for any consumer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class PaperNavHistory(Base):
    __tablename__ = "paper_nav_history"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "as_of_date", name="uq_paper_nav_history_account_date"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("paper_account.id"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    # SPY close that day (None when SPY is unmarkable); the read path normalises
    # the SPY series to the account's initial capital for the overlay line.
    benchmark_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"PaperNavHistory(account_id={self.account_id!r}, "
            f"as_of_date={self.as_of_date!r}, nav={self.nav!r})"
        )
