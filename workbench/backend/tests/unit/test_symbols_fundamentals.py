"""B059 F003 / B064 F001 — get_symbol_fundamentals: market-aware + cache-first.

DB-backed (the isolated symbol_fundamentals_cache) with a fake provider so no
network is touched. Pins:

* **US** keeps B059's US-equity gate (non-US / ETF / no-data degrade honestly,
  ratios withheld);
* **CN / HK** (B064) are available whenever the akshare source returned any
  metric, stamped with the CAS / HKFRS accounting standard; an unreachable
  source degrades to ``source_unavailable``;
* **cache-first**: a successful snapshot is served for the rest of the UTC day
  (provider not re-hit); a stale snapshot refetches; a failed fetch is **not**
  cached (next request retries).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_fundamentals_cache import (
    SymbolFundamentalsCacheRepository,
)
from workbench_api.symbols.fundamentals import get_symbol_fundamentals
from workbench_api.symbols.provider import (
    CHINA_GAAP,
    HK_GAAP,
    US_GAAP,
    InvalidSymbolError,
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
)


class _StatsProvider(SymbolDataProvider):
    name = "fake"

    def __init__(self, stats: ProviderStats) -> None:
        self._stats = stats
        self.stats_calls = 0

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:  # pragma: no cover - unused here
        raise NotImplementedError

    def get_quote(self, symbol: str) -> ProviderQuote:  # pragma: no cover - unused
        raise NotImplementedError

    def get_stats(self, symbol: str) -> ProviderStats:
        self.stats_calls += 1
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
        accounting_standard=US_GAAP,
        market_cap=3.0e12,
        trailing_pe=30.5,
        profit_margins=0.25,
        gross_margins=0.44,
        revenue=4.0e11,
        return_on_equity=1.5,
        debt_to_equity=150.0,
        eps=6.5,
    )


# --- US (B059 gate preserved) --------------------------------------------- #


def test_us_equity_returns_available_fundamentals(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(
            session, "aapl", provider=_StatsProvider(_us_equity_stats())
        )
        assert result.symbol == "AAPL"  # normalised
        assert result.available is True
        assert result.reason is None
        assert result.is_us_equity is True
        assert result.accounting_standard == "US-GAAP"
        assert result.market_cap == 3.0e12
        assert result.eps == 6.5
        assert result.sector == "Technology"
        assert result.source == "yfinance"


def test_us_etf_degrades_with_not_equity_reason(initialised_db: str) -> None:
    stats = ProviderStats(
        symbol="SPY",
        source="yfinance",
        quote_type="ETF",
        country="United States",
        market_cap=5.0e11,
    )
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "SPY", provider=_StatsProvider(stats))
        assert result.available is False
        assert result.reason == "not_equity"
        assert result.market_cap is None


def test_us_equity_without_data_degrades_no_data(initialised_db: str) -> None:
    stats = ProviderStats(
        symbol="ZZZ", source="yfinance", quote_type="EQUITY", country="United States"
    )
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "ZZZ", provider=_StatsProvider(stats))
        assert result.available is False
        assert result.reason == "no_data"
        assert result.is_us_equity is True


def test_us_missing_quote_type_degrades_no_data(initialised_db: str) -> None:
    stats = ProviderStats(symbol="ZZZ", source="yfinance")
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "ZZZ", provider=_StatsProvider(stats))
        assert result.available is False
        assert result.reason == "no_data"
        assert result.is_us_equity is False


def test_us_bare_foreign_adr_still_non_us(initialised_db: str) -> None:
    # A bare ticker (US market) whose yfinance country is non-US keeps B059's
    # 'non_us' degradation — only .SH/.SZ/.HK route to the akshare path.
    stats = ProviderStats(
        symbol="BABA",
        source="yfinance",
        quote_type="EQUITY",
        country="China",
        market_cap=2.0e11,
    )
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "BABA", provider=_StatsProvider(stats))
        assert result.available is False
        assert result.reason == "non_us"
        assert result.market_cap is None


# --- CN / HK (B064 market-aware) ------------------------------------------ #


def _cn_stats() -> ProviderStats:
    return ProviderStats(
        symbol="600519.SH",
        source="akshare",
        currency="CNY",
        quote_type="EQUITY",
        country="China",
        accounting_standard=CHINA_GAAP,
        market_cap=1.55e12,
        trailing_pe=18.74,
        return_on_equity=0.1057,
        gross_margins=0.8976,
        revenue=5.47e10,
        eps=21.76,
        debt_to_asset=12.12,
        as_of_report=date(2026, 3, 31),
    )


def test_cn_equity_available_with_cas_standard(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "600519.sh", provider=_StatsProvider(_cn_stats()))
        assert result.symbol == "600519.SH"
        assert result.available is True
        assert result.reason is None
        assert result.is_us_equity is False
        assert result.accounting_standard == "CAS"
        assert result.currency == "CNY"
        assert result.market_cap == 1.55e12
        assert result.return_on_equity == 0.1057
        assert result.debt_to_asset == 12.12
        assert result.as_of == date(2026, 3, 31)


def test_hk_equity_available_with_hkfrs_standard(initialised_db: str) -> None:
    stats = ProviderStats(
        symbol="0700.HK",
        source="akshare",
        currency="HKD",
        quote_type="EQUITY",
        country="Hong Kong",
        long_name="腾讯控股",
        accounting_standard=HK_GAAP,
        market_cap=4.06e12,
        trailing_pe=15.23,
        revenue=7.51e11,
    )
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "0700.hk", provider=_StatsProvider(stats))
        assert result.available is True
        assert result.is_us_equity is False
        assert result.accounting_standard == "HKFRS"
        assert result.currency == "HKD"
        assert result.name == "腾讯控股"
        assert result.market_cap == 4.06e12


def test_cn_source_unavailable_degrades_honestly(initialised_db: str) -> None:
    # akshare unreachable → minimal identity, no metrics → source_unavailable.
    stats = ProviderStats(
        symbol="600519.SH",
        source="akshare",
        currency="CNY",
        quote_type="EQUITY",
        country="China",
        accounting_standard=CHINA_GAAP,
    )
    with Session(get_engine()) as session:
        result = get_symbol_fundamentals(session, "600519.SH", provider=_StatsProvider(stats))
        assert result.available is False
        assert result.reason == "source_unavailable"
        assert result.market_cap is None
        assert result.currency == "CNY"  # identity still honest


# --- cache-first behaviour ------------------------------------------------- #


def test_successful_snapshot_served_from_cache_same_day(initialised_db: str) -> None:
    provider = _StatsProvider(_cn_stats())
    with Session(get_engine()) as session:
        first = get_symbol_fundamentals(session, "600519.SH", provider=provider)
        session.commit()
        second = get_symbol_fundamentals(session, "600519.SH", provider=provider)
        assert first.market_cap == second.market_cap
        # Cache hit on the second lookup → provider fetched only once.
        assert provider.stats_calls == 1


def test_stale_snapshot_refetches(initialised_db: str) -> None:
    provider = _StatsProvider(_cn_stats())
    with Session(get_engine()) as session:
        repo = SymbolFundamentalsCacheRepository(session)
        # Seed a snapshot stamped yesterday → stale vs today.
        repo.upsert_snapshot(
            symbol="600519.SH",
            market="CN",
            stats=_cn_stats(),
            fetched_at=datetime.now(UTC) - timedelta(days=1),
        )
        session.commit()
        get_symbol_fundamentals(session, "600519.SH", provider=provider)
        assert provider.stats_calls == 1  # stale → refetched


def test_failed_fetch_is_not_cached(initialised_db: str) -> None:
    empty = ProviderStats(
        symbol="600519.SH",
        source="akshare",
        currency="CNY",
        quote_type="EQUITY",
        country="China",
    )
    provider = _StatsProvider(empty)
    with Session(get_engine()) as session:
        get_symbol_fundamentals(session, "600519.SH", provider=provider)
        session.commit()
        repo = SymbolFundamentalsCacheRepository(session)
        assert repo.get_by_symbol("600519.SH") is None  # failure not pinned
        # Next lookup retries the provider (no cache to serve).
        get_symbol_fundamentals(session, "600519.SH", provider=provider)
        assert provider.stats_calls == 2


def test_invalid_symbol_raises_before_provider(initialised_db: str) -> None:
    provider = _StatsProvider(_us_equity_stats())
    with Session(get_engine()) as session:
        with pytest.raises(InvalidSymbolError):
            get_symbol_fundamentals(session, "A" * 40, provider=provider)
        assert provider.stats_calls == 0
