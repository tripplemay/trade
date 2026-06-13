"""B059 F001 — response schemas for ``GET /api/symbols/{symbol}/price``.

EOD price detail for an arbitrary ticker: the latest close + the trailing
52-week range + total-return windows + the OHLCV series for the chart. Every
field is honest about being end-of-day (``is_eod`` / ``as_of`` / ``source``)
— there is no live / intraday data and no execution surface here.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class PriceRangeReturns(BaseModel):
    """Total returns over fixed windows. ``None`` when the series doesn't
    reach back far enough (honest degradation, not zero)."""

    one_month: float | None = Field(description="1-month total return (close/close − 1).")
    three_month: float | None = Field(description="3-month total return.")
    six_month: float | None = Field(description="6-month total return.")
    one_year: float | None = Field(description="1-year total return.")
    ytd: float | None = Field(
        description="Year-to-date total return (vs last close of prior year)."
    )


class PriceBarPoint(BaseModel):
    """One EOD OHLCV bar for the chart (line or candlestick)."""

    obs_date: date = Field(description="Trading day (EOD).")
    open: float
    high: float
    low: float
    close: float
    volume: int


class SymbolPriceDetail(BaseModel):
    """EOD price detail for one symbol."""

    symbol: str = Field(description="Normalised ticker, e.g. 'AAPL'.")
    as_of: date = Field(description="Latest EOD observation date (close-of-day, not live).")
    close: float = Field(description="Latest EOD closing price.")
    source: str = Field(description="Data source label, e.g. 'yfinance'.")
    is_eod: bool = Field(
        description="Always true — end-of-day close, never intraday / real-time."
    )
    week52_high: float | None = Field(
        description="Trailing 52-week intraday high, null if unknown."
    )
    week52_low: float | None = Field(
        description="Trailing 52-week intraday low, null if unknown."
    )
    returns: PriceRangeReturns
    bars: list[PriceBarPoint] = Field(description="EOD OHLCV series for the chart, oldest first.")


class SymbolFundamentals(BaseModel):
    """B059 F003 — best-effort fundamentals for one symbol.

    Authoritative fundamentals are a US-equity feature (SEC's domain). For
    non-US tickers / ETFs the financial ratios are withheld and ``available``
    is false with a ``reason`` so the UI degrades honestly (not a blank). The
    identity fields (name / sector / industry / currency) are shown regardless.
    Source is yfinance ``.info`` (the only feed that covers arbitrary tickers).
    """

    symbol: str
    source: str = Field(description="Fundamentals source label, e.g. 'yfinance'.")
    available: bool = Field(
        description="True when financial ratios are shown (US equities only)."
    )
    reason: str | None = Field(
        description=(
            "Why ratios are withheld: 'non_us' / 'not_equity' / 'no_data'. "
            "Null when available."
        )
    )
    is_us_equity: bool = Field(
        description="True when quote type is EQUITY and country is the US."
    )
    # Identity (shown regardless of availability)
    name: str | None
    sector: str | None
    industry: str | None
    currency: str | None
    quote_type: str | None
    country: str | None
    # Financial ratios (null when not available / US-only degradation)
    market_cap: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    dividend_yield: float | None
    profit_margins: float | None
    gross_margins: float | None
    revenue: float | None
    shares_outstanding: float | None
    return_on_equity: float | None
    debt_to_equity: float | None
