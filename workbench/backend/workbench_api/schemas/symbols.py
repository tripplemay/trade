"""B059 F001 — response schemas for ``GET /api/symbols/{symbol}/price``.

EOD price detail for an arbitrary ticker: the latest close + the trailing
52-week range + total-return windows + the OHLCV series for the chart. Every
field is honest about being end-of-day (``is_eod`` / ``as_of`` / ``source``)
— there is no live / intraday data and no execution surface here.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from workbench_api.schemas.news import LatestNewsItem

# B064 F001 — reason codes the UI maps to friendly copy (extends B059's
# US-only set with the CN/HK honest-degradation case).
FUNDAMENTALS_REASONS = ("non_us", "not_equity", "no_data", "source_unavailable")


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
    source: str = Field(description="Data source label, e.g. 'yfinance' / 'akshare'.")
    currency: str = Field(
        description="ISO currency of the quote (USD for US, CNY for A-share); display-only."
    )
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
    """B059 F003 / B064 F001 — best-effort fundamentals for one symbol.

    **Market-aware** (B064): US equities surface yfinance ``.info`` ratios
    (US-GAAP); A-share (.SH/.SZ) + Hong Kong (.HK) equities surface akshare
    fundamentals (CAS / HKFRS) — a *different* accounting standard, stamped via
    ``accounting_standard`` so the口径 is honest and not implied
    cross-comparable. When the source is unreachable / the ticker is a non-US
    ETF / no data, ``available`` is false with a ``reason`` so the UI degrades
    honestly (not a blank). Identity (name / sector / industry / currency) is
    shown regardless. Numeric units (B064 §3): margins / ROE are fractions;
    ``debt_to_equity`` / ``debt_to_asset`` are percent; market cap / revenue /
    net income / shares are raw currency units.
    """

    symbol: str
    source: str = Field(description="Fundamentals source label, e.g. 'yfinance' / 'akshare'.")
    available: bool = Field(
        description="True when financial metrics are shown for this symbol."
    )
    reason: str | None = Field(
        description=(
            "Why metrics are withheld: 'non_us' / 'not_equity' / 'no_data' / "
            "'source_unavailable'. Null when available."
        )
    )
    is_us_equity: bool = Field(
        description="True when quote type is EQUITY and country is the US."
    )
    accounting_standard: str | None = Field(
        default=None,
        description="Reporting standard of the metrics: 'US-GAAP' / 'CAS' / 'HKFRS'.",
    )
    as_of: date | None = Field(
        default=None,
        description="Reporting-period date of the statements (≠ the daily price as_of).",
    )
    # Identity (shown regardless of availability)
    name: str | None
    sector: str | None
    industry: str | None
    currency: str | None
    quote_type: str | None
    country: str | None
    # Financial metrics (null when not available / withheld)
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
    # B064 — CAS/HKFRS-friendly extras (also filled for US from yfinance)
    eps: float | None = None
    book_value_per_share: float | None = None
    net_income: float | None = None
    debt_to_asset: float | None = None


class SymbolNewsResponse(BaseModel):
    """B059 F004 — recent news for one symbol (reuses the B034/B035 feed).

    Items reuse the global-feed :class:`LatestNewsItem` shape (Chinese
    ``title_zh`` preferred, deterministic topic tags, never LLM-generated). An
    empty ``items`` list is the honest empty state — "no recent news for this
    symbol" — not an error.
    """

    symbol: str = Field(description="Normalised ticker the news is filtered to.")
    items: list[LatestNewsItem] = Field(
        default_factory=list, description="Newest-first headlines for the symbol."
    )
