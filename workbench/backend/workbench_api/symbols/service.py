"""B059 F001 — symbol price-detail service (cache-first, guarded, EOD TTL).

The single request-path entry point for the "look up any ticker" surface.
Flow for ``get_symbol_price_detail``:

1. **Validate** + normalise the raw ticker (bad input → :class:`InvalidSymbolError`
   *before* any external call).
2. **Cache-first**: if the isolated ``symbol_price_cache`` table already holds
   a fetch from today (UTC), serve straight from it — repeated lookups of the
   same symbol never hit the external API again that day (the primary
   "don't hammer Yahoo" protection, B059 §6).
3. **On miss / stale**: run the per-request rate-limit guard (the reuse of the
   ``cost_guard`` family's enforcement seam — a *no-op by default*, like the
   FRED / Alpha Vantage free-tier loaders; an injected guard may raise to
   halt a lookup storm), then fetch the full ~13-month window from the
   provider and write it to the cache idempotently.
4. **Derive** the latest close + 52-week range + window returns from the
   cached series and return the detail.

Request-path safe: imports neither ``trade`` nor any broker SDK. Reads/writes
only ``symbol_price_cache`` — never the funded strategies' price stores.

Why the rate-limit guard is *not* ``MonthlyBudgetGuard``: that guard meters
the shared ``tiingo_budget_log``; reusing it for free yfinance lookups would
let a lookup storm exhaust the **Tiingo** monthly budget and break the daily
price ingest the funded Master / B058 strategies depend on. We reuse the
sibling :class:`RateLimitGuard` seam instead (``market_context_common``), with
the EOD-day cache as the concrete anti-hammer protection.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from workbench_api.data.market_context_common import NoOpRateLimitGuard, RateLimitGuard
from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.models.symbol_price_cache import SymbolPriceCache
from workbench_api.db.repositories.symbol_price_cache import SymbolPriceCacheRepository
from workbench_api.schemas.symbols import (
    PriceBarPoint,
    PriceRangeReturns,
    SymbolPriceDetail,
)
from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.provider import (
    SymbolDataProvider,
    SymbolNotFoundError,
)
from workbench_api.symbols.stats import compute_price_stats
from workbench_api.symbols.symbol_ref import SymbolRef
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider

# ~13 months: enough history for the 1Y return + a full 52-week high / low.
_HISTORY_LOOKBACK_DAYS = 400


def normalize_symbol(raw: str) -> str:
    """Canonicalise a raw ticker to its market-qualified identity string.

    Delegates to :meth:`SymbolRef.parse` (B061 F001): a bare US ticker returns
    its upper-cased form unchanged (so existing cache keys / paths are
    untouched — §9.4 向后兼容铁律), a CN ticker returns its ``600519.SH``
    canonical. Raises :class:`InvalidSymbolError` for empty / over-long /
    illegal-character input (validated at the boundary so the external API is
    never hit for junk)."""

    return SymbolRef.parse(raw).canonical


def _default_provider() -> SymbolDataProvider:
    """Production US provider factory (monkeypatched in route tests)."""

    return YFinanceSymbolProvider()


def _resolve_provider(symbol: str) -> SymbolDataProvider:
    """Pick the EOD provider by market (path-doc §9.8): a CN canonical routes
    to the A-share provider (akshare primary + baostock fallback); US / bare
    routes to yfinance. ``symbol`` must already be the normalized canonical."""

    if SymbolRef.parse(symbol).market == "CN":
        return CnSymbolProvider()
    return _default_provider()


def _provider_source(provider: SymbolDataProvider) -> str:
    """The source that actually served the fetch — the CN provider exposes
    ``last_source`` (akshare, or baostock on fallback); others use ``name``."""

    return str(getattr(provider, "last_source", provider.name))


def _default_guard() -> RateLimitGuard:
    """Production rate-limit guard (no-op; the cache is the real protection)."""

    return NoOpRateLimitGuard()


def _utc_date(stamp: datetime) -> date:
    """Calendar date of ``stamp`` in UTC, tolerating naive timestamps that
    SQLite hands back for ``DateTime(timezone=True)`` columns."""

    if stamp.tzinfo is None:
        return stamp.date()
    return stamp.astimezone(UTC).date()


def get_symbol_price_detail(
    session: Session,
    raw_symbol: str,
    *,
    provider: SymbolDataProvider | None = None,
    guard: RateLimitGuard | None = None,
    today: Callable[[], date] = lambda: datetime.now(UTC).date(),
) -> SymbolPriceDetail:
    """Return the EOD price detail for ``raw_symbol`` (cache-first)."""

    symbol = normalize_symbol(raw_symbol)
    ref = SymbolRef.parse(symbol)
    provider = provider or _resolve_provider(symbol)
    guard = guard or _default_guard()
    repo = SymbolPriceCacheRepository(session)
    now_day = today()

    if not _cache_fresh(repo, symbol, now_day):
        # May raise SymbolRateLimitedError (→ 429) before any network spend.
        guard.check_and_increment()
        fetched = provider.get_price_history(
            symbol,
            now_day - timedelta(days=_HISTORY_LOOKBACK_DAYS),
            now_day,
        )
        # Normalise both error shapes a provider may use for "no such ticker":
        # YFinanceSymbolProvider raises SymbolNotFoundError (from the loader's
        # ValueError), but a future provider could instead return an empty
        # list — guard against that here so the route still surfaces a 404.
        if not fetched:
            raise SymbolNotFoundError(symbol)
        stamp = datetime.now(UTC)
        fetched_source = _provider_source(provider)
        for bar in fetched:
            repo.save_if_new(
                symbol=symbol,
                obs_date=bar.bar_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adj_close=bar.adj_close,
                volume=bar.volume,
                source=fetched_source,
                market=ref.market,
                currency=ref.currency,
                fetched_at=stamp,
            )

    cached = repo.bars_since(symbol, now_day - timedelta(days=_HISTORY_LOOKBACK_DAYS))
    if not cached:
        raise SymbolNotFoundError(symbol)

    bars = [_to_price_bar(row) for row in cached]
    # Anchor the 52-week range + return windows to the latest *observation*
    # (not the calendar "today"): on a weekend / holiday the latest EOD bar
    # predates now_day, and the windows must agree with the as_of we report.
    stats = compute_price_stats(bars)
    latest = bars[-1]
    return SymbolPriceDetail(
        symbol=symbol,
        as_of=latest.bar_date,
        close=latest.close,
        source=cached[-1].source,
        currency=ref.currency,
        is_eod=True,
        week52_high=stats.week52_high,
        week52_low=stats.week52_low,
        returns=PriceRangeReturns(
            one_month=stats.returns["1M"],
            three_month=stats.returns["3M"],
            six_month=stats.returns["6M"],
            one_year=stats.returns["1Y"],
            ytd=stats.returns["YTD"],
        ),
        bars=[
            PriceBarPoint(
                obs_date=row.obs_date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in cached
        ],
    )


def _cache_fresh(
    repo: SymbolPriceCacheRepository, symbol: str, now_day: date
) -> bool:
    """True when ``symbol`` was already fetched today (UTC). The lookup path
    always writes the full window, so a same-day ``fetched_at`` guarantees a
    complete series — the EOD-day TTL bounds external calls to ~1/symbol/day."""

    latest_fetch = repo.latest_fetched_at(symbol)
    return latest_fetch is not None and _utc_date(latest_fetch) >= now_day


def _to_price_bar(row: SymbolPriceCache) -> PriceBar:
    return PriceBar(
        ticker=row.symbol,
        bar_date=row.obs_date,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        adj_close=row.adj_close,
        volume=row.volume,
    )
