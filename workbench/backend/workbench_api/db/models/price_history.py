"""PriceHistory model — deep per-symbol daily close history (B048 F001).

One row per ``(symbol, obs_date)``, the same shape as
:class:`PriceSnapshot` (B037) but a **separate, deep** table. The two
serve different purposes and must not be conflated:

* ``price_snapshot`` (B037) holds only the *latest two* closes per symbol
  — exactly what the Home Day P&L needs (today vs prior trading day). The
  ``workbench-prices`` timer keeps it shallow on purpose.
* ``price_history`` (B048) holds the *full daily history* the safety /
  risk layer needs to reconstruct a mark-to-market NAV time series and
  compute master + per-sleeve drawdown over time (F003). A backfill job
  materialises it from the B045 unified prices CSV
  (``snapshots/prices/unified/prices_daily.csv``), which already carries
  ~2 years of daily closes for the Master universe.

Keeping the two tables separate means the deep backfill never disturbs
the Day P&L's "latest + prior" semantics, and the risk layer never has to
reason about a shallow window.

Mirrors ``price_snapshot``'s column shape + ``(symbol, obs_date)``
idempotency key + two indexes. ``close`` is a plain float ``Numeric``
(``asdecimal=False``) so the mark-to-market arithmetic stays float-native
(identical to ``PriceSnapshot.close``).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("symbol", "obs_date", name="uq_price_history_symbol_date"),
        # Explicit names (not column ``index=True`` auto-names) so the ORM
        # create_all path and the alembic 0011 migration agree on the
        # index names — same convention as price_snapshot (0009).
        Index("ix_price_history_symbol", "symbol"),
        Index("ix_price_history_obs_date", "obs_date"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"PriceHistory(symbol={self.symbol!r}, "
            f"obs_date={self.obs_date!r}, close={self.close!r})"
        )
