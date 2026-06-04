"""B035 F001 — market_context_observation table.

One row per ``(series_id, obs_date)`` market-context data point — a FRED
macro series (10y ``DGS10`` / VIX ``VIXCLS`` / CPI ``CPIAUCSL``) or an
Alpha Vantage index/ETF quote (``SPY`` / ``QQQ`` / ``DXY``). Only the
numeric value + metadata live in the DB; the raw provider response lands
on disk under ``data/snapshots/market-context/{source}/{YYYY-MM-DD}/``
and is referenced via ``snapshot_path`` (reusing the B027/B029 snapshot
foundation — B035 spec §4.2).

The unique key ``(series_id, obs_date)`` makes
:meth:`~workbench_api.db.repositories.market_context.MarketContextRepository.save_if_new`
idempotent, so the daily systemd-timer fetch (F002) re-running over a
series it already has is a no-op rather than a duplicate insert.

``value`` is a non-decimal ``Numeric`` column (``asdecimal=False`` →
plain ``float``) — market-context values span very different magnitudes
(a 4.25 rate, a 312.x CPI index, a 580.x ETF price) and the Home card
renders them as plain numbers, so float keeps the API / front-end chain
simple without a Decimal round-trip.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class MarketContextObservation(Base):
    __tablename__ = "market_context_observation"
    __table_args__ = (
        UniqueConstraint(
            "series_id", "obs_date", name="uq_market_context_series_date"
        ),
        # Explicit names (not column ``index=True`` auto-names) so the ORM
        # create_all path and the alembic 0007 migration agree on the
        # index names the B035 spec §4.2 pins.
        Index("ix_market_context_series", "series_id"),
        Index("ix_market_context_obs_date", "obs_date"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    snapshot_path: Mapped[str] = mapped_column(String(512), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"MarketContextObservation(series_id={self.series_id!r}, "
            f"source={self.source!r}, obs_date={self.obs_date!r}, "
            f"value={self.value!r})"
        )
