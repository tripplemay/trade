"""B059 F001 — YFinanceSymbolProvider behaviour.

Injects a stub ``ticker_factory`` so the suite never touches Yahoo. Pins the
three abstraction methods (get_price_history / get_quote / get_stats) and the
ValueError → SymbolNotFoundError translation that lets the route return an
actionable 404 instead of a generic 500.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.provider import (
    ProviderQuote,
    ProviderStats,
    SymbolNotFoundError,
)
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [470.0, 471.0, 472.0],
            "High": [475.0, 476.0, 477.0],
            "Low": [468.0, 469.0, 470.0],
            "Close": [472.65, 473.10, 474.20],
            "Adj Close": [470.12, 470.55, 471.60],
            "Volume": [123_524_300, 98_000_000, 110_000_000],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )


class _StubTicker:
    def __init__(
        self,
        *,
        history_df: pd.DataFrame | None = None,
        info_dict: dict[str, Any] | None = None,
        info_exc: Exception | None = None,
    ) -> None:
        self._history_df = history_df if history_df is not None else _sample_df()
        self._info_dict = info_dict
        self._info_exc = info_exc

    def history(self, **_kwargs: Any) -> pd.DataFrame:
        return self._history_df.copy()

    @property
    def info(self) -> dict[str, Any]:
        if self._info_exc is not None:
            raise self._info_exc
        return dict(self._info_dict or {})


def _provider_with(stub: _StubTicker) -> YFinanceSymbolProvider:
    return YFinanceSymbolProvider(ticker_factory=lambda _t: stub)


def test_get_price_history_maps_bars() -> None:
    provider = _provider_with(_StubTicker())
    bars = provider.get_price_history("SPY", date(2024, 1, 2), date(2024, 1, 4))
    assert len(bars) == 3
    assert all(isinstance(b, PriceBar) for b in bars)
    assert bars[0].bar_date == date(2024, 1, 2)
    assert bars[0].close == 472.65
    assert bars[0].adj_close == 470.12  # auto_adjust=False contract preserved
    assert bars[-1].bar_date == date(2024, 1, 4)


def test_get_price_history_empty_maps_to_symbol_not_found() -> None:
    provider = _provider_with(_StubTicker(history_df=pd.DataFrame()))
    with pytest.raises(SymbolNotFoundError) as exc:
        provider.get_price_history("ZZZZ", date(2024, 1, 2), date(2024, 1, 4))
    assert exc.value.symbol == "ZZZZ"


def test_get_quote_returns_latest_close() -> None:
    provider = _provider_with(_StubTicker())
    quote = provider.get_quote("SPY")
    assert isinstance(quote, ProviderQuote)
    assert quote.source == "yfinance"
    # Latest bar in the stub series.
    assert quote.as_of == date(2024, 1, 4)
    assert quote.close == 474.20


def test_get_stats_parses_info() -> None:
    stub = _StubTicker(
        info_dict={
            "longName": "Apple Inc.",
            "currency": "USD",
            "exchange": "NMS",
            "quoteType": "EQUITY",
        }
    )
    stats = _provider_with(stub).get_stats("AAPL")
    assert isinstance(stats, ProviderStats)
    assert stats.long_name == "Apple Inc."
    assert stats.currency == "USD"
    assert stats.exchange == "NMS"
    assert stats.quote_type == "EQUITY"
    assert stats.source == "yfinance"


def test_get_stats_degrades_when_info_raises() -> None:
    stub = _StubTicker(info_exc=RuntimeError("Yahoo 503"))
    stats = _provider_with(stub).get_stats("AAPL")
    # Never raises for a flaky .info — returns minimal metadata.
    assert stats.symbol == "AAPL"
    assert stats.source == "yfinance"
    assert stats.long_name is None
    assert stats.currency is None


def test_get_stats_parses_fundamentals_fields() -> None:
    # B059 F003 — get_stats also lifts the fundamental fields from .info.
    stub = _StubTicker(
        info_dict={
            "quoteType": "EQUITY",
            "country": "United States",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3.0e12,
            "trailingPE": 30.5,
            "forwardPE": 28.0,
            "priceToBook": 45.0,
            "dividendYield": 0.005,
            "profitMargins": 0.25,
            "grossMargins": 0.44,
            "totalRevenue": 4.0e11,
            "sharesOutstanding": 1.5e10,
            "returnOnEquity": 1.5,
            "debtToEquity": 150.0,
        }
    )
    stats = _provider_with(stub).get_stats("AAPL")
    assert stats.quote_type == "EQUITY"
    assert stats.country == "United States"
    assert stats.sector == "Technology"
    assert stats.market_cap == 3.0e12
    assert stats.trailing_pe == 30.5
    assert stats.forward_pe == 28.0
    assert stats.price_to_book == 45.0
    assert stats.revenue == 4.0e11
    assert stats.debt_to_equity == 150.0


def test_get_stats_coerces_bad_fundamental_values_to_none() -> None:
    stub = _StubTicker(
        info_dict={"marketCap": "not-a-number", "trailingPE": None, "priceToBook": "N/A"}
    )
    stats = _provider_with(stub).get_stats("AAPL")
    assert stats.market_cap is None
    assert stats.trailing_pe is None
    assert stats.price_to_book is None
