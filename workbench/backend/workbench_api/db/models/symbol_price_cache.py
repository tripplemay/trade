"""SymbolPriceCache model — B059 F001 on-demand symbol-lookup price cache.

Research-only EOD price cache for the B059 "look up any ticker" surface.
**Deliberately isolated** from the trading / risk price stores
(``price_snapshot`` B037 / ``price_history`` B048): those feed Day P&L, NAV
and drawdown for the *funded* Master / regime strategies and are written
only by the Tiingo ingest pipeline. This table is written on the request
path by the symbol-lookup service from the free **yfinance** EOD feed, for
*arbitrary* tickers the user types in — and is **never** read by the risk /
NAV / recommendation layers.

Keeping it a separate table buys two things:

* an arbitrary-ticker lookup can never perturb the funded strategies' price
  math, so the "Master / B058 不破" invariant stays trivially true; and
* it stores full **OHLCV** (the trading stores keep only ``close``) so the
  detail page can draw candlesticks and a true 52-week *intraday* high/low.

One row per ``(symbol, obs_date)`` with the same idempotency key + explicit
index naming convention as ``price_history``. ``source`` records provenance
(``"yfinance"``); ``fetched_at`` drives the EOD-day TTL — the service
refetches a given symbol at most once per UTC day.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class SymbolPriceCache(Base):
    __tablename__ = "symbol_price_cache"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "obs_date", name="uq_symbol_price_cache_symbol_date"
        ),
        # Explicit names (not column ``index=True`` auto-names) so the ORM
        # create_all path and the alembic 0024 migration agree on the index
        # names — same convention as price_history (0011) / price_snapshot.
        Index("ix_symbol_price_cache_symbol", "symbol"),
        Index("ix_symbol_price_cache_obs_date", "obs_date"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(asdecimal=False), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # B061 F002 — market dimension + display currency. Derivable from the
    # canonical symbol (SymbolRef) but stored explicitly per §9.5 for query
    # efficiency + provenance. US/USD server-default keeps existing rows + any
    # caller that omits them backward-compatible.
    market: Mapped[str] = mapped_column(String(8), nullable=False, server_default="US")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="USD")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"SymbolPriceCache(symbol={self.symbol!r}, "
            f"obs_date={self.obs_date!r}, close={self.close!r})"
        )
