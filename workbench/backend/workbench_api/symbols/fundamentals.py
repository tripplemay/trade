"""B059 F003 — symbol fundamentals service (yfinance, US-equity gated).

Returns best-effort fundamentals for an arbitrary ticker. Design note on the
SEC deviation: B059's spec named SEC EDGAR as the fundamentals source, but the
existing SEC infra (``sec_edgar_loader`` / ``xbrl_parser`` / ``fundamentals_*``)
is **universe-bound** (a bundled ~27-ticker CIK map; unknown ticker → ValueError),
needs a separate ratio-synthesis step, and risks a 30-day SEC IP ban on a bad
request — so it cannot serve *arbitrary* tickers on the request path. We instead
read yfinance ``.info`` (the only feed that covers arbitrary tickers, already the
F001 price provider) via ``provider.get_stats``, and **preserve the spec's
US-equity gating**: financial ratios are surfaced only for US equities
(``quote_type == "EQUITY"`` and ``country == "United States"``); non-US / ETF /
no-data tickers degrade honestly (``available=False`` + ``reason``) rather than
showing a blank. Request-path safe: no ``trade`` import.
"""

from __future__ import annotations

from workbench_api.schemas.symbols import SymbolFundamentals
from workbench_api.symbols.provider import ProviderStats, SymbolDataProvider
from workbench_api.symbols.service import normalize_symbol
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider

_US_COUNTRIES = frozenset({"United States", "USA", "US"})


def _default_provider() -> SymbolDataProvider:
    """Production provider factory (monkeypatched in route tests)."""

    return YFinanceSymbolProvider()


def _is_us(country: str | None) -> bool:
    return country is not None and country in _US_COUNTRIES


def get_symbol_fundamentals(
    raw_symbol: str,
    *,
    provider: SymbolDataProvider | None = None,
) -> SymbolFundamentals:
    """Return fundamentals for ``raw_symbol`` (US-equity gated, honest degrade).

    Always returns a 200-shaped payload for a syntactically valid symbol —
    ``available`` + ``reason`` drive the UI's honest framing. A malformed
    ticker raises :class:`InvalidSymbolError` (→ 400) via ``normalize_symbol``.
    """

    symbol = normalize_symbol(raw_symbol)
    provider = provider or _default_provider()
    stats = provider.get_stats(symbol)

    is_us_equity = stats.quote_type == "EQUITY" and _is_us(stats.country)
    if stats.quote_type is not None and stats.quote_type != "EQUITY":
        available, reason = False, "not_equity"
    elif not is_us_equity:
        available, reason = False, "non_us"
    elif not _has_any_ratio(stats):
        available, reason = False, "no_data"
    else:
        available, reason = True, None

    # Honest US-only degradation: withhold financial ratios unless this is a
    # US equity with data. Identity fields are shown regardless.
    show = available
    return SymbolFundamentals(
        symbol=symbol,
        source=stats.source,
        available=available,
        reason=reason,
        is_us_equity=is_us_equity,
        name=stats.long_name,
        sector=stats.sector,
        industry=stats.industry,
        currency=stats.currency,
        quote_type=stats.quote_type,
        country=stats.country,
        market_cap=stats.market_cap if show else None,
        trailing_pe=stats.trailing_pe if show else None,
        forward_pe=stats.forward_pe if show else None,
        price_to_book=stats.price_to_book if show else None,
        dividend_yield=stats.dividend_yield if show else None,
        profit_margins=stats.profit_margins if show else None,
        gross_margins=stats.gross_margins if show else None,
        revenue=stats.revenue if show else None,
        shares_outstanding=stats.shares_outstanding if show else None,
        return_on_equity=stats.return_on_equity if show else None,
        debt_to_equity=stats.debt_to_equity if show else None,
    )


def _has_any_ratio(stats: ProviderStats) -> bool:
    return any(
        value is not None
        for value in (
            stats.market_cap,
            stats.trailing_pe,
            stats.forward_pe,
            stats.price_to_book,
            stats.dividend_yield,
            stats.profit_margins,
            stats.gross_margins,
            stats.revenue,
            stats.return_on_equity,
            stats.debt_to_equity,
        )
    )
