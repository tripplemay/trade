"""PriceSnapshot model — daily per-symbol close (B037 F001).

One row per ``(symbol, obs_date)`` — the most recent unadjusted/adjusted
daily close the workbench has fetched for a held symbol. The B037 Home
page marks the latest ``AccountSnapshot`` positions to market with these
closes (today's close vs the prior trading day's close) to compute a
read-only Day P&L.

Why a dedicated table (B037 building-phase design clarification, user
approved 2026-06-05): the request path must stay self-contained
(v0.9.32 §12.10) — it may not read the repo-root price-bar snapshot
files the B027 Tiingo loader writes for backtests. So a daily timer
(``workbench-prices``) fetches the held symbols' closes through the same
B027 ``TiingoSnapshotLoader`` and persists them here; the Home request
path only ever reads this table via :class:`PriceSnapshotRepository`.

Mirrors ``market_context_observation`` (B035 0007): same id/obs_date/
value-style shape + ``(symbol, obs_date)`` idempotency key + two indexes.
``close`` is stored as a plain float ``Numeric`` (``asdecimal=False``)
so the mark-to-market arithmetic stays float-native without a Decimal
round-trip — identical to ``MarketContextObservation.value``.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"
    __table_args__ = (
        UniqueConstraint("symbol", "obs_date", name="uq_price_snapshot_symbol_date"),
        # Explicit names (not column ``index=True`` auto-names) so the ORM
        # create_all path and the alembic 0009 migration agree on the
        # index names the B037 spec pins — same convention as B035 0007.
        Index("ix_price_snapshot_symbol", "symbol"),
        Index("ix_price_snapshot_obs_date", "obs_date"),
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
            f"PriceSnapshot(symbol={self.symbol!r}, "
            f"obs_date={self.obs_date!r}, close={self.close!r})"
        )
