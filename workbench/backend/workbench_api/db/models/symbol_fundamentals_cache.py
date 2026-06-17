"""SymbolFundamentalsCache model — B064 F001 on-demand fundamentals cache.

Research-only EOD fundamentals snapshot for the B059 "look up any ticker"
detail page, extended by B064 to A-share (CAS) + Hong Kong (HKFRS) alongside
the US (yfinance / US-GAAP) surface. **Deliberately isolated** from every
trading / risk / scoring store — exactly like ``symbol_price_cache`` (B059):
arbitrary-ticker fundamentals are written on the request path from free,
unofficial data feeds (yfinance ``.info`` for US; akshare for CN/HK) and are
**never** read by the recommendation / backtest / risk / account layers
(B064 红线: research-safe / lookup 展示 only — fundamentals never feed a
strategy).

One row per ``symbol`` (the latest snapshot, upserted), unlike the price cache
which keeps one row per ``(symbol, obs_date)``: fundamentals are a single
point-in-time snapshot, not a series. ``fetched_at`` drives the EOD-day TTL —
the service refetches a given symbol's fundamentals at most once per UTC day.
``as_of_report`` is the *reporting period* date of the statements (≠ the daily
price as_of) and ``accounting_standard`` stamps the口径 (US-GAAP / CAS /
HKFRS) so the surface is honest about cross-standard non-comparability.

Numeric units mirror the provider/yfinance convention (B064 §3): margins / ROE
are fractions; ``debt_to_equity`` / ``debt_to_asset`` are percent; market cap /
revenue / net income / shares are raw currency units.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString

# Shared float-backed Numeric for the nullable metric columns (asdecimal=False
# so the ORM hands back plain floats, matching ProviderStats / yfinance).
_Num = Numeric(asdecimal=False)


class SymbolFundamentalsCache(Base):
    __tablename__ = "symbol_fundamentals_cache"
    __table_args__ = (
        # One snapshot per symbol (latest, upserted) — the unique key the
        # repository's upsert + the EOD-day TTL key off.
        UniqueConstraint("symbol", name="uq_symbol_fundamentals_cache_symbol"),
        Index("ix_symbol_fundamentals_cache_symbol", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False, server_default="US")
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="USD"
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    accounting_standard: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Identity (shown regardless of ratio availability)
    long_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quote_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    as_of_report: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Fundamentals metrics (all nullable best-effort; units per module docstring)
    market_cap: Mapped[float | None] = mapped_column(_Num, nullable=True)
    trailing_pe: Mapped[float | None] = mapped_column(_Num, nullable=True)
    forward_pe: Mapped[float | None] = mapped_column(_Num, nullable=True)
    price_to_book: Mapped[float | None] = mapped_column(_Num, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(_Num, nullable=True)
    profit_margins: Mapped[float | None] = mapped_column(_Num, nullable=True)
    gross_margins: Mapped[float | None] = mapped_column(_Num, nullable=True)
    revenue: Mapped[float | None] = mapped_column(_Num, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(_Num, nullable=True)
    return_on_equity: Mapped[float | None] = mapped_column(_Num, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(_Num, nullable=True)
    eps: Mapped[float | None] = mapped_column(_Num, nullable=True)
    book_value_per_share: Mapped[float | None] = mapped_column(_Num, nullable=True)
    net_income: Mapped[float | None] = mapped_column(_Num, nullable=True)
    debt_to_asset: Mapped[float | None] = mapped_column(_Num, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"SymbolFundamentalsCache(symbol={self.symbol!r}, "
            f"market={self.market!r}, as_of_report={self.as_of_report!r})"
        )
