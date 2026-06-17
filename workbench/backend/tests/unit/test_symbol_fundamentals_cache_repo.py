"""B064 F001 — SymbolFundamentalsCacheRepository (upsert + TTL signal).

Exercises the one-snapshot-per-symbol upsert (insert then field-replace), the
``get_by_symbol`` read, and the ``latest_fetched_at`` TTL signal the service's
cache-freshness check keys off. Uses the ``initialised_db`` fixture (ORM-metadata
schema, fresh per test); no network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_fundamentals_cache import (
    SymbolFundamentalsCacheRepository,
)
from workbench_api.symbols.provider import CHINA_GAAP, ProviderStats


def _cn_stats(*, market_cap: float = 1.55e12) -> ProviderStats:
    return ProviderStats(
        symbol="600519.SH",
        source="akshare",
        currency="CNY",
        quote_type="EQUITY",
        country="China",
        accounting_standard=CHINA_GAAP,
        long_name=None,
        market_cap=market_cap,
        trailing_pe=18.74,
        return_on_equity=0.1057,
        revenue=5.47e10,
        eps=21.76,
        as_of_report=date(2026, 3, 31),
    )


def test_upsert_inserts_then_replaces(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolFundamentalsCacheRepository(session)
        stamp = datetime(2026, 6, 18, 9, 0, tzinfo=UTC)
        row = repo.upsert_snapshot(
            symbol="600519.SH", market="CN", stats=_cn_stats(), fetched_at=stamp
        )
        session.commit()
        assert row.market == "CN"
        assert row.currency == "CNY"
        assert row.source == "akshare"
        assert row.market_cap == 1.55e12
        assert row.accounting_standard == "CAS"
        assert row.as_of_report == date(2026, 3, 31)
        assert repo.count() == 1

        # Same symbol again with a new value → replace, not duplicate.
        newer = datetime(2026, 6, 19, 9, 0, tzinfo=UTC)
        repo.upsert_snapshot(
            symbol="600519.SH",
            market="CN",
            stats=_cn_stats(market_cap=1.60e12),
            fetched_at=newer,
        )
        session.commit()
        assert repo.count() == 1
        fresh = repo.get_by_symbol("600519.SH")
        assert fresh is not None
        assert fresh.market_cap == 1.60e12


def test_get_by_symbol_and_latest_fetched_at(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolFundamentalsCacheRepository(session)
        assert repo.get_by_symbol("MISSING") is None
        assert repo.latest_fetched_at("MISSING") is None

        stamp = datetime(2026, 6, 18, 9, 0, tzinfo=UTC)
        repo.upsert_snapshot(
            symbol="600519.SH", market="CN", stats=_cn_stats(), fetched_at=stamp
        )
        session.commit()
        latest = repo.latest_fetched_at("600519.SH")
        assert latest is not None
        normalised = latest if latest.tzinfo else latest.replace(tzinfo=UTC)
        assert normalised.astimezone(UTC) == stamp


def test_currency_falls_back_when_stats_currency_none(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolFundamentalsCacheRepository(session)
        stats = ProviderStats(symbol="X", source="yfinance", currency=None)
        row = repo.upsert_snapshot(symbol="X", market="US", stats=stats)
        session.commit()
        assert row.currency == "USD"  # NOT NULL column → honest US default
