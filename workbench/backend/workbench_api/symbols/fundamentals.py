"""B059 F003 / B064 F001 — market-aware symbol fundamentals (cache-first).

Returns best-effort fundamentals for an arbitrary ticker, **routed by market**
(B064):

* **US** (bare ticker) → yfinance ``.info`` (US-GAAP), preserving B059's
  US-equity gating: ratios surface only for US equities
  (``quote_type == "EQUITY"`` and US country); non-US / ETF / no-data degrade
  honestly (``available=False`` + ``reason``). The SEC deviation note from
  B059 still holds — the SEC infra is universe-bound and risks an IP ban, so
  yfinance ``.info`` (the only arbitrary-ticker feed) backs the US surface.
* **A-share** (.SH/.SZ) → akshare (CAS) via :class:`CnSymbolProvider`;
  **Hong Kong** (.HK) → akshare (HKFRS) via :class:`HkSymbolProvider`. CN/HK
  are *available* whenever the source returned any metric; an unreachable
  source degrades to ``available=False`` + ``reason='source_unavailable'``
  (never a 500). The akshare functions were §23-verified reachable before
  this was built (B064 spec §3).

**Cache-first** (B064): a successful snapshot is written to the isolated
``symbol_fundamentals_cache`` table and re-served for the rest of the UTC day
(EOD-day TTL), so repeated lookups never re-hit yfinance / akshare. A
transient source failure is **not** cached, so the next request retries. The
per-request :class:`RateLimitGuard` (no-op by default; the cache is the real
anti-hammer protection) guards the external fetch — same seam as the price
service.

Request-path safe (§12.10.2): imports neither ``trade`` nor any broker SDK;
akshare is lazy-imported inside the CN/HK providers. Reads / writes only the
isolated ``symbol_fundamentals_cache`` table — never the funded strategies'
stores.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.data.market_context_common import NoOpRateLimitGuard, RateLimitGuard
from workbench_api.db.models.symbol_fundamentals_cache import SymbolFundamentalsCache
from workbench_api.db.repositories.symbol_fundamentals_cache import (
    SymbolFundamentalsCacheRepository,
)
from workbench_api.schemas.symbols import SymbolFundamentals
from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.hk_provider import HkSymbolProvider
from workbench_api.symbols.provider import ProviderStats, SymbolDataProvider
from workbench_api.symbols.service import normalize_symbol
from workbench_api.symbols.symbol_ref import SymbolRef
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider

_US_COUNTRIES = frozenset({"United States", "USA", "US"})

# Metric fields that count as "has fundamentals data" (any non-null → available).
_METRIC_FIELDS = (
    "market_cap",
    "trailing_pe",
    "forward_pe",
    "price_to_book",
    "dividend_yield",
    "profit_margins",
    "gross_margins",
    "revenue",
    "shares_outstanding",
    "return_on_equity",
    "debt_to_equity",
    "eps",
    "book_value_per_share",
    "net_income",
    "debt_to_asset",
)


def _default_provider() -> SymbolDataProvider:
    """Production US provider factory (monkeypatched in route tests)."""

    return YFinanceSymbolProvider()


def _resolve_provider(symbol: str) -> SymbolDataProvider:
    """Pick the fundamentals provider by market (path-doc §9.8): a CN canonical
    routes to the A-share provider (akshare CAS), a HK canonical to the Hong
    Kong provider (akshare HKFRS), US / bare to yfinance. ``symbol`` must
    already be the normalized canonical."""

    market = SymbolRef.parse(symbol).market
    if market == "CN":
        return CnSymbolProvider()
    if market == "HK":
        return HkSymbolProvider()
    return _default_provider()


def _default_guard() -> RateLimitGuard:
    """Production rate-limit guard (no-op; the EOD-day cache is the protection)."""

    return NoOpRateLimitGuard()


def _is_us(country: str | None) -> bool:
    return country is not None and country in _US_COUNTRIES


def _utc_date(stamp: datetime) -> date:
    """Calendar date of ``stamp`` in UTC, tolerating naive timestamps SQLite
    hands back for ``DateTime(timezone=True)`` columns."""

    if stamp.tzinfo is None:
        return stamp.date()
    return stamp.astimezone(UTC).date()


def get_symbol_fundamentals(
    session: Session,
    raw_symbol: str,
    *,
    provider: SymbolDataProvider | None = None,
    guard: RateLimitGuard | None = None,
    today: Callable[[], date] = lambda: datetime.now(UTC).date(),
) -> SymbolFundamentals:
    """Return market-aware fundamentals for ``raw_symbol`` (cache-first).

    Always returns a 200-shaped payload for a syntactically valid symbol —
    ``available`` + ``reason`` drive the UI's honest framing. A malformed
    ticker raises :class:`InvalidSymbolError` (→ 400) via ``normalize_symbol``;
    an injected guard may raise :class:`SymbolRateLimitedError` (→ 429).
    """

    symbol = normalize_symbol(raw_symbol)
    ref = SymbolRef.parse(symbol)
    repo = SymbolFundamentalsCacheRepository(session)
    now_day = today()

    cached = repo.get_by_symbol(symbol)
    if cached is not None and _utc_date(cached.fetched_at) >= now_day:
        return _build_fundamentals(ref, _stats_from_cache(cached))

    guard = guard or _default_guard()
    guard.check_and_increment()  # may raise SymbolRateLimitedError (→ 429)
    resolved = provider or _resolve_provider(symbol)
    stats = resolved.get_stats(symbol)
    if _has_any_metric(stats):
        # Cache successful snapshots only — a transient source failure is not
        # pinned for the UTC day; the next lookup retries.
        repo.upsert_snapshot(
            symbol=symbol,
            market=ref.market,
            stats=stats,
            fetched_at=datetime.now(UTC),
        )
    return _build_fundamentals(ref, stats)


def _has_any_metric(stats: ProviderStats) -> bool:
    return any(getattr(stats, field) is not None for field in _METRIC_FIELDS)


def _gate(ref: SymbolRef, stats: ProviderStats) -> tuple[bool, str | None, bool]:
    """Resolve (available, reason, is_us_equity) for ``ref``'s market.

    US keeps B059's US-equity gate; CN/HK are available whenever the source
    returned any metric, else honestly ``source_unavailable``.
    """

    if ref.market == "US":
        is_us_equity = stats.quote_type == "EQUITY" and _is_us(stats.country)
        # Order matters: a missing quote_type (flaky .info) is a data gap, not
        # a region signal — classify 'no_data' rather than mislabel 'non_us'.
        if stats.quote_type is None:
            return False, "no_data", is_us_equity
        if stats.quote_type != "EQUITY":
            return False, "not_equity", is_us_equity
        if not _is_us(stats.country):
            return False, "non_us", is_us_equity
        if not _has_any_metric(stats):
            return False, "no_data", is_us_equity
        return True, None, is_us_equity

    # CN / HK (akshare CAS / HKFRS).
    if _has_any_metric(stats):
        return True, None, False
    return False, "source_unavailable", False


def _build_fundamentals(ref: SymbolRef, stats: ProviderStats) -> SymbolFundamentals:
    available, reason, is_us_equity = _gate(ref, stats)
    show = available  # withhold metrics unless available; identity shows always
    return SymbolFundamentals(
        symbol=stats.symbol,
        source=stats.source,
        available=available,
        reason=reason,
        is_us_equity=is_us_equity,
        accounting_standard=stats.accounting_standard,
        as_of=stats.as_of_report,
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
        eps=stats.eps if show else None,
        book_value_per_share=stats.book_value_per_share if show else None,
        net_income=stats.net_income if show else None,
        debt_to_asset=stats.debt_to_asset if show else None,
    )


def _stats_from_cache(row: SymbolFundamentalsCache) -> ProviderStats:
    """Reconstruct :class:`ProviderStats` from a cached snapshot row."""

    return ProviderStats(
        symbol=row.symbol,
        source=row.source,
        long_name=row.long_name,
        currency=row.currency,
        quote_type=row.quote_type,
        country=row.country,
        sector=row.sector,
        industry=row.industry,
        market_cap=row.market_cap,
        trailing_pe=row.trailing_pe,
        forward_pe=row.forward_pe,
        price_to_book=row.price_to_book,
        dividend_yield=row.dividend_yield,
        profit_margins=row.profit_margins,
        gross_margins=row.gross_margins,
        revenue=row.revenue,
        shares_outstanding=row.shares_outstanding,
        return_on_equity=row.return_on_equity,
        debt_to_equity=row.debt_to_equity,
        eps=row.eps,
        book_value_per_share=row.book_value_per_share,
        net_income=row.net_income,
        debt_to_asset=row.debt_to_asset,
        as_of_report=row.as_of_report,
        accounting_standard=row.accounting_standard,
    )
