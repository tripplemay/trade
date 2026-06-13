"""B059 F001 — SymbolPriceCacheRepository against in-memory-ish SQLite.

Exercises the idempotent insert, the ordered per-symbol series read, and the
``latest_fetched_at`` TTL signal the service's cache-freshness check relies
on. Uses the ``initialised_db`` fixture (ORM-metadata schema, fresh per test).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_price_cache import SymbolPriceCacheRepository


def _save(
    repo: SymbolPriceCacheRepository,
    symbol: str,
    obs_date: date,
    close: float,
    *,
    fetched_at: datetime,
) -> None:
    repo.save_if_new(
        symbol=symbol,
        obs_date=obs_date,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        adj_close=close,
        volume=1_000,
        source="yfinance",
        fetched_at=fetched_at,
    )


def test_save_if_new_is_idempotent_by_symbol_and_date(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolPriceCacheRepository(session)
        stamp = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)
        first = repo.save_if_new(
            symbol="NVDA",
            obs_date=date(2026, 6, 12),
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            adj_close=101.0,
            volume=5_000,
            source="yfinance",
            fetched_at=stamp,
        )
        assert first is not None
        # Same (symbol, obs_date) → no duplicate, returns None.
        again = repo.save_if_new(
            symbol="NVDA",
            obs_date=date(2026, 6, 12),
            open=999.0,
            high=999.0,
            low=999.0,
            close=999.0,
            adj_close=999.0,
            volume=1,
            source="yfinance",
            fetched_at=stamp,
        )
        assert again is None
        session.commit()
        assert repo.count() == 1


def test_bars_since_filters_and_orders_ascending(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolPriceCacheRepository(session)
        stamp = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)
        _save(repo, "AAPL", date(2026, 1, 5), 150.0, fetched_at=stamp)
        _save(repo, "AAPL", date(2026, 3, 5), 160.0, fetched_at=stamp)
        _save(repo, "AAPL", date(2026, 6, 5), 170.0, fetched_at=stamp)
        # A different symbol must not leak into the AAPL series.
        _save(repo, "MSFT", date(2026, 6, 5), 400.0, fetched_at=stamp)
        session.commit()

        rows = repo.bars_since("AAPL", date(2026, 2, 1))
        assert [r.obs_date for r in rows] == [date(2026, 3, 5), date(2026, 6, 5)]
        assert [r.close for r in rows] == [160.0, 170.0]


def test_latest_fetched_at_returns_max_or_none(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolPriceCacheRepository(session)
        assert repo.latest_fetched_at("TSLA") is None

        older = datetime(2026, 6, 12, 8, 0, tzinfo=UTC)
        newer = datetime(2026, 6, 13, 8, 0, tzinfo=UTC)
        _save(repo, "TSLA", date(2026, 6, 11), 200.0, fetched_at=older)
        _save(repo, "TSLA", date(2026, 6, 12), 210.0, fetched_at=newer)
        session.commit()

        latest = repo.latest_fetched_at("TSLA")
        assert latest is not None
        # Tolerate SQLite handing back a naive datetime.
        normalised = latest if latest.tzinfo else latest.replace(tzinfo=UTC)
        assert normalised.astimezone(UTC) == newer
