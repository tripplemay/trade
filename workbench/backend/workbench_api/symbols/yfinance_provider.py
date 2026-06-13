"""B059 F001 — yfinance implementation of :class:`SymbolDataProvider`.

Composes the existing :class:`YFinanceSnapshotLoader` for price history
(reusing its battle-tested ``auto_adjust=False`` contract + PIT clamping)
and reads ``yfinance.Ticker(...).info`` for instrument metadata. yfinance is
a free, unofficial Yahoo wrapper and the only third-party entry point, so
the whole class is request-path safe (no ``trade``, no broker SDK).

The loader raises ``ValueError`` on an empty / delisted ticker; we translate
that to :class:`SymbolNotFoundError` so the route can return an actionable
404 instead of a generic 500.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import yfinance  # type: ignore[import-untyped]

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data.yfinance_loader import YFinanceSnapshotLoader, _TickerFactory
from workbench_api.symbols.provider import (
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
)

# A short recent window is enough to resolve the latest EOD close for a quote
# (covers weekends / holidays without pulling a full history).
_QUOTE_WINDOW_DAYS = 7


def _as_float(value: Any) -> float | None:
    """Coerce a yfinance ``.info`` value to float, or None if absent/garbage.

    ``.info`` values are loosely typed (int / float / str / None); never let a
    bad value raise — fundamentals degrade honestly to None."""

    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


class YFinanceSymbolProvider(SymbolDataProvider):
    """SymbolDataProvider backed by yfinance (free, arbitrary ticker)."""

    name = "yfinance"

    def __init__(
        self,
        *,
        loader: YFinanceSnapshotLoader | None = None,
        ticker_factory: _TickerFactory | None = None,
    ) -> None:
        self._ticker_factory: _TickerFactory = ticker_factory or yfinance.Ticker
        self._loader = loader or YFinanceSnapshotLoader(
            ticker_factory=self._ticker_factory
        )

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        try:
            return self._loader.fetch_daily_bars(symbol, from_date, to_date)
        except ValueError as exc:
            # Empty / delisted / rate-limited → actionable 404, not a 500.
            raise SymbolNotFoundError(symbol) from exc

    def get_quote(self, symbol: str) -> ProviderQuote:
        today = datetime.now(UTC).date()
        bars = self.get_price_history(
            symbol, today - timedelta(days=_QUOTE_WINDOW_DAYS), today
        )
        if not bars:
            raise SymbolNotFoundError(symbol)
        latest = bars[-1]
        return ProviderQuote(
            symbol=symbol,
            as_of=latest.bar_date,
            close=latest.close,
            source=self.name,
        )

    def get_stats(self, symbol: str) -> ProviderStats:
        try:
            info: dict[str, Any] = self._ticker_factory(symbol).info or {}
        except Exception:
            # ``.info`` is best-effort + flaky; degrade to minimal metadata
            # rather than fail the (price-first) lookup. Mirrors
            # YFinanceSnapshotLoader.health_check's broad guard.
            return ProviderStats(symbol=symbol, source=self.name)
        return ProviderStats(
            symbol=symbol,
            source=self.name,
            long_name=info.get("longName") or info.get("shortName"),
            currency=info.get("currency"),
            exchange=info.get("exchange") or info.get("fullExchangeName"),
            quote_type=info.get("quoteType"),
            country=info.get("country"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=_as_float(info.get("marketCap")),
            trailing_pe=_as_float(info.get("trailingPE")),
            forward_pe=_as_float(info.get("forwardPE")),
            price_to_book=_as_float(info.get("priceToBook")),
            dividend_yield=_as_float(info.get("dividendYield")),
            profit_margins=_as_float(info.get("profitMargins")),
            gross_margins=_as_float(info.get("grossMargins")),
            revenue=_as_float(info.get("totalRevenue")),
            shares_outstanding=_as_float(info.get("sharesOutstanding")),
            return_on_equity=_as_float(info.get("returnOnEquity")),
            debt_to_equity=_as_float(info.get("debtToEquity")),
        )
