"""B059 F001 — SymbolPriceCacheRepository.

Wraps the isolated ``symbol_price_cache`` table (research-only on-demand
symbol-lookup OHLCV) with the operations the symbol-lookup service needs:

- :meth:`save_if_new` — idempotent insert by ``(symbol, obs_date)``; returns
  ``None`` when that bar already exists, so re-fetching a symbol on a later
  day never duplicates the overlapping bars (same contract as
  ``PriceHistoryRepository``).
- :meth:`bars_since` — the per-symbol OHLCV series on ``obs_date >= since``,
  oldest first, for the chart + the derived 52-week range / window returns.
- :meth:`latest_fetched_at` — the most recent ``fetched_at`` for a symbol,
  driving the EOD-day cache TTL (the service refetches at most once per UTC
  day; the lookup path always writes the full window, so a fresh
  ``fetched_at`` guarantees full coverage).

The repository never touches the network — the provider fetches bars and the
service passes them in. That split keeps the cache table single-purpose and
lets tests exercise the repo against in-memory SQLite without any network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.symbol_price_cache import SymbolPriceCache
from workbench_api.db.repositories.base import Repository


class SymbolPriceCacheRepository(Repository[SymbolPriceCache, UUID]):
    model = SymbolPriceCache
    primary_key_attr = "id"

    def get_by_symbol_and_date(
        self, symbol: str, obs_date: date
    ) -> SymbolPriceCache | None:
        stmt = select(SymbolPriceCache).where(
            SymbolPriceCache.symbol == symbol,
            SymbolPriceCache.obs_date == obs_date,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save_if_new(
        self,
        *,
        symbol: str,
        obs_date: date,
        open: float,
        high: float,
        low: float,
        close: float,
        adj_close: float,
        volume: int,
        source: str,
        market: str = "US",
        currency: str = "USD",
        fetched_at: datetime | None = None,
    ) -> SymbolPriceCache | None:
        """Insert an OHLCV bar if absent; return ``None`` if a row with the
        same ``(symbol, obs_date)`` already exists.

        ``market`` / ``currency`` default to ``US`` / ``USD`` (B061 F002) so
        existing US callers stay byte-identical; the CN provider path passes
        ``CN`` / ``CNY``. ``fetched_at`` defaults to ``datetime.now(UTC)`` and
        is overridable so tests pin a deterministic timestamp (and seed
        cache-freshness state).
        """

        if self.get_by_symbol_and_date(symbol, obs_date) is not None:
            return None
        row = SymbolPriceCache(
            id=uuid4(),
            symbol=symbol,
            obs_date=obs_date,
            open=open,
            high=high,
            low=low,
            close=close,
            adj_close=adj_close,
            volume=volume,
            source=source,
            market=market,
            currency=currency,
            fetched_at=fetched_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def bars_since(self, symbol: str, since: date) -> list[SymbolPriceCache]:
        """Return ``symbol``'s cached bars on ``obs_date >= since``, oldest
        first — the OHLCV series the detail page + stats consume."""

        stmt = (
            select(SymbolPriceCache)
            .where(
                SymbolPriceCache.symbol == symbol,
                SymbolPriceCache.obs_date >= since,
            )
            .order_by(SymbolPriceCache.obs_date.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def latest_fetched_at(self, symbol: str) -> datetime | None:
        """Return the most recent ``fetched_at`` across ``symbol``'s cached
        bars, or ``None`` when the symbol has never been cached."""

        stmt = (
            select(SymbolPriceCache.fetched_at)
            .where(SymbolPriceCache.symbol == symbol)
            .order_by(SymbolPriceCache.fetched_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()
