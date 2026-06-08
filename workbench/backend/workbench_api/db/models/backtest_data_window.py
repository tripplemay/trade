"""B047-OPS2 F001 — backtest_data_window table (L2 data-coverage window).

One singleton row recording the real backtest data coverage the data-refresh
job last wrote: ``data_start`` / ``data_end`` (the earliest / latest date in the
unified daily prices CSV) and ``first_usable_signal_date`` (the conservative
floor a backtest can start from and still satisfy the sleeves' lookbacks —
momentum's ~9-month window is binding, risk_parity needs 120 trading days).

The request-path ``GET /api/backtests/data-range`` reads this row ONLY (no
``trade`` import, §12.10.2) so the frontend can pick a valid default range and
clamp the date picker. The data-refresh job (which already fetches the prices)
is the single writer — it upserts the singleton after writing the CSV.

These are HISTORICAL coverage bounds, never a forward prediction (§1.1).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base

# The table holds a single authoritative coverage row; this fixed primary key
# makes the write an idempotent upsert (no row proliferation across refreshes).
SINGLETON_ID = "default"


class BacktestDataWindow(Base):
    __tablename__ = "backtest_data_window"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=SINGLETON_ID)
    data_start: Mapped[date] = mapped_column(Date, nullable=False)
    data_end: Mapped[date] = mapped_column(Date, nullable=False)
    first_usable_signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"BacktestDataWindow(data_start={self.data_start!r}, "
            f"data_end={self.data_end!r}, "
            f"first_usable_signal_date={self.first_usable_signal_date!r})"
        )
