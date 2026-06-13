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
