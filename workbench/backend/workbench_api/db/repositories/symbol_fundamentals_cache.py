"""B064 F001 — SymbolFundamentalsCacheRepository.

Wraps the isolated ``symbol_fundamentals_cache`` table (research-only,
one-snapshot-per-symbol) with the three operations the fundamentals service
needs:

- :meth:`get_by_symbol` — the cached snapshot for a symbol (the EOD-day TTL
  read + the served payload).
- :meth:`upsert_snapshot` — replace the symbol's snapshot from a freshly
  fetched :class:`ProviderStats` (insert if absent, field-update if present).
- :meth:`latest_fetched_at` — the snapshot's ``fetched_at`` driving the
  once-per-UTC-day TTL.

The repository never touches the network — the provider fetches the stats and
the service passes them in (same split as ``SymbolPriceCacheRepository``), so
tests exercise it against in-memory SQLite without any network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.symbol_fundamentals_cache import SymbolFundamentalsCache
from workbench_api.db.repositories.base import Repository
from workbench_api.symbols.provider import ProviderStats

# ProviderStats field names persisted verbatim onto the cache row (identity +
# metrics). market / currency / source are written separately (market is not a
# ProviderStats field; currency / source may be overridden by the caller).
_SNAPSHOT_FIELDS = (
    "accounting_standard",
    "long_name",
    "sector",
    "industry",
    "quote_type",
    "country",
    "as_of_report",
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


class SymbolFundamentalsCacheRepository(Repository[SymbolFundamentalsCache, UUID]):
    model = SymbolFundamentalsCache
    primary_key_attr = "id"

    def get_by_symbol(self, symbol: str) -> SymbolFundamentalsCache | None:
        stmt = select(SymbolFundamentalsCache).where(
            SymbolFundamentalsCache.symbol == symbol
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert_snapshot(
        self,
        *,
        symbol: str,
        market: str,
        stats: ProviderStats,
        fetched_at: datetime | None = None,
    ) -> SymbolFundamentalsCache:
        """Insert / replace ``symbol``'s fundamentals snapshot from ``stats``.

        ``currency`` / ``source`` come from ``stats`` (the provider's honest
        provenance — e.g. akshare's CURRENCY=HKD). ``fetched_at`` defaults to
        now (UTC) and is overridable so tests pin a deterministic timestamp +
        seed cache-freshness state.
        """

        stamp = fetched_at or datetime.now(UTC)
        existing = self.get_by_symbol(symbol)
        target = existing or SymbolFundamentalsCache(id=uuid4(), symbol=symbol)
        target.market = market
        target.currency = stats.currency or "USD"
        target.source = stats.source
        target.fetched_at = stamp
        for field in _SNAPSHOT_FIELDS:
            setattr(target, field, getattr(stats, field))
        if existing is None:
            self._session.add(target)
        self._session.flush()
        return target

    def latest_fetched_at(self, symbol: str) -> datetime | None:
        """The snapshot's ``fetched_at`` (the EOD-day TTL signal), or None when
        the symbol has never been cached."""
        stmt = select(SymbolFundamentalsCache.fetched_at).where(
            SymbolFundamentalsCache.symbol == symbol
        )
        return self._session.execute(stmt).scalar_one_or_none()
