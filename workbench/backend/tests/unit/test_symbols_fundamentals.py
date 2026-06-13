"""B059 F003 — get_symbol_fundamentals: US-equity gating + honest degradation.

Offline tests with a fake provider returning canned ProviderStats. Pins the
spec's US-only contract: financial ratios are surfaced only for US equities;
non-US / ETF / no-data tickers degrade honestly (available=False + reason,
ratios withheld) instead of showing a blank.
"""

from __future__ import annotations

from datetime import date

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.fundamentals import get_symbol_fundamentals
from workbench_api.symbols.provider import (
    InvalidSymbolError,
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
)


class _StatsProvider(SymbolDataProvider):
    name = "fake"

    def __init__(self, stats: ProviderStats) -> None:
        self._stats = stats

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:  # pragma: no cover - unused here
        raise NotImplementedError

    def get_quote(self, symbol: str) -> ProviderQuote:  # pragma: no cover - unused
        raise NotImplementedError

    def get_stats(self, symbol: str) -> ProviderStats:
        return self._stats


def _us_equity_stats() -> ProviderStats:
    return ProviderStats(
        symbol="AAPL",
        source="yfinance",
        long_name="Apple Inc.",
        currency="USD",
        exchange="NMS",
        quote_type="EQUITY",
        country="United States",
        sector="Technology",
        industry="Consumer Electronics",
        market_cap=3.0e12,
        trailing_pe=30.5,
        forward_pe=28.0,
        price_to_book=45.0,
        dividend_yield=0.005,
        profit_margins=0.25,
        gross_margins=0.44,
        revenue=4.0e11,
        shares_outstanding=1.5e10,
        return_on_equity=1.5,
        debt_to_equity=150.0,
    )


def test_us_equity_returns_available_fundamentals() -> None:
    result = get_symbol_fundamentals("aapl", provider=_StatsProvider(_us_equity_stats()))
    assert result.symbol == "AAPL"  # normalised
    assert result.available is True
    assert result.reason is None
    assert result.is_us_equity is True
    assert result.market_cap == 3.0e12
    assert result.trailing_pe == 30.5
    assert result.sector == "Technology"
    assert result.source == "yfinance"


def test_non_us_equity_degrades_and_withholds_ratios() -> None:
    stats = ProviderStats(
        symbol="0700.HK",
        source="yfinance",
        long_name="Tencent",
        currency="HKD",
        quote_type="EQUITY",
        country="China",
        sector="Communication Services",
        market_cap=4.0e12,
        trailing_pe=20.0,
    )
    result = get_symbol_fundamentals("0700.HK", provider=_StatsProvider(stats))
    assert result.available is False
    assert result.reason == "non_us"
    assert result.is_us_equity is False
    # Ratios withheld for non-US (honest US-only degradation)...
    assert result.market_cap is None
    assert result.trailing_pe is None
    # ...but identity is still shown.
    assert result.country == "China"
    assert result.currency == "HKD"
    assert result.sector == "Communication Services"


def test_etf_degrades_with_not_equity_reason() -> None:
    stats = ProviderStats(
        symbol="SPY",
        source="yfinance",
        long_name="SPDR S&P 500 ETF",
        quote_type="ETF",
        country="United States",
        market_cap=5.0e11,
    )
    result = get_symbol_fundamentals("SPY", provider=_StatsProvider(stats))
    assert result.available is False
    assert result.reason == "not_equity"
    assert result.market_cap is None


def test_us_equity_without_data_degrades_no_data() -> None:
    stats = ProviderStats(
        symbol="ZZZ",
        source="yfinance",
        quote_type="EQUITY",
        country="United States",
    )
    result = get_symbol_fundamentals("ZZZ", provider=_StatsProvider(stats))
    assert result.available is False
    assert result.reason == "no_data"
    assert result.is_us_equity is True


def test_missing_quote_type_degrades_no_data() -> None:
    # Regression (F003 review): flaky .info → quote_type None must be 'no_data',
    # not mislabeled 'non_us'.
    stats = ProviderStats(symbol="ZZZ", source="yfinance")
    result = get_symbol_fundamentals("ZZZ", provider=_StatsProvider(stats))
    assert result.available is False
    assert result.reason == "no_data"
    assert result.is_us_equity is False


def test_us_equity_with_only_shares_outstanding_is_available() -> None:
    # Regression (F003 review): shares_outstanding alone is a fundamental field
    # → must count as data (was omitted from the no-data check).
    stats = ProviderStats(
        symbol="ZZZ",
        source="yfinance",
        quote_type="EQUITY",
        country="United States",
        shares_outstanding=1.0e9,
    )
    result = get_symbol_fundamentals("ZZZ", provider=_StatsProvider(stats))
    assert result.available is True
    assert result.shares_outstanding == 1.0e9


def test_invalid_symbol_raises_before_provider() -> None:
    with pytest.raises(InvalidSymbolError):
        get_symbol_fundamentals("A" * 40, provider=_StatsProvider(_us_equity_stats()))
