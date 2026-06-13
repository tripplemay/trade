"""B059 F001 — get_symbol_price_detail: cache, guard, validation, errors.

Uses a fake provider (records calls, returns canned bars) + a counting /
raising rate-limit guard so the suite is offline and deterministic. Covers
the acceptance: provider abstraction is honoured, cache miss → fetch + write,
cache hit → no external call, stale → refetch, invalid ticker → 400-class
error, unknown ticker → 404-class error, and the guard fires once per fetch
(and can short-circuit a lookup storm).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_price_cache import SymbolPriceCacheRepository
from workbench_api.schemas.symbols import SymbolPriceDetail
from workbench_api.symbols.provider import (
    InvalidSymbolError,
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
    SymbolRateLimitedError,
)
from workbench_api.symbols.service import get_symbol_price_detail

_TODAY = date(2026, 6, 13)


def _series(end: date, *, n: int = 60, start_close: float = 100.0) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for i in range(n):
        d = end - timedelta(days=(n - 1 - i))
        close = start_close + i
        bars.append(
            PriceBar(
                ticker="X",
                bar_date=d,
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                adj_close=close,
                volume=1_000,
            )
        )
    return bars


class _FakeProvider(SymbolDataProvider):
    name = "fake"

    def __init__(
        self,
        bars: list[PriceBar] | None = None,
        *,
        raise_not_found: bool = False,
    ) -> None:
        self._bars = bars if bars is not None else _series(_TODAY)
        self._raise_not_found = raise_not_found
        self.history_calls: list[str] = []

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        self.history_calls.append(symbol)
        if self._raise_not_found:
            raise SymbolNotFoundError(symbol)
        return list(self._bars)

    def get_quote(self, symbol: str) -> ProviderQuote:  # pragma: no cover - unused here
        raise NotImplementedError

    def get_stats(self, symbol: str) -> ProviderStats:  # pragma: no cover - unused here
        raise NotImplementedError


class _CountingGuard:
    def __init__(self, *, raise_exc: Exception | None = None) -> None:
        self.calls = 0
        self._raise_exc = raise_exc

    def check_and_increment(self) -> None:
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc


def _detail(
    session: Session,
    provider: _FakeProvider,
    guard: _CountingGuard,
    symbol: str = "aapl",
) -> SymbolPriceDetail:
    return get_symbol_price_detail(
        session,
        symbol,
        provider=provider,
        guard=guard,
        today=lambda: _TODAY,
    )


def test_cache_miss_fetches_writes_and_normalises(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        provider = _FakeProvider()
        guard = _CountingGuard()
        detail = _detail(session, provider, guard, symbol="aapl")
        session.commit()

        # Symbol normalised, honest EOD labelling, latest close surfaced.
        assert detail.symbol == "AAPL"
        assert detail.is_eod is True
        assert detail.source == "yfinance"
        assert detail.as_of == _TODAY
        assert detail.close == provider._bars[-1].close
        assert len(detail.bars) == len(provider._bars)
        # Provider hit exactly once; guard fired exactly once (per fetch).
        assert provider.history_calls == ["AAPL"]
        assert guard.calls == 1
        # Bars were written to the isolated cache.
        repo = SymbolPriceCacheRepository(session)
        assert len(repo.bars_since("AAPL", _TODAY - timedelta(days=400))) == len(
            provider._bars
        )


def test_cache_hit_does_not_call_provider(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolPriceCacheRepository(session)
        # Seed a fresh (fetched today) full series directly into the cache.
        stamp = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)
        for bar in _series(_TODAY):
            repo.save_if_new(
                symbol="AAPL",
                obs_date=bar.bar_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adj_close=bar.adj_close,
                volume=bar.volume,
                source="yfinance",
                fetched_at=stamp,
            )
        session.commit()

        provider = _FakeProvider()
        guard = _CountingGuard()
        detail = _detail(session, provider, guard, symbol="AAPL")

        # Served from cache: no external fetch, no guard increment.
        assert provider.history_calls == []
        assert guard.calls == 0
        assert detail.symbol == "AAPL"
        assert detail.as_of == _TODAY


def test_stale_cache_refetches(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolPriceCacheRepository(session)
        # Seed bars fetched YESTERDAY → stale under the EOD-day TTL.
        yesterday = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)
        for bar in _series(_TODAY - timedelta(days=1)):
            repo.save_if_new(
                symbol="AAPL",
                obs_date=bar.bar_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adj_close=bar.adj_close,
                volume=bar.volume,
                source="yfinance",
                fetched_at=yesterday,
            )
        session.commit()

        provider = _FakeProvider()
        guard = _CountingGuard()
        _detail(session, provider, guard, symbol="AAPL")

        # Stale → refetched once.
        assert provider.history_calls == ["AAPL"]
        assert guard.calls == 1


def test_invalid_symbol_raises_before_any_fetch(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        provider = _FakeProvider()
        guard = _CountingGuard()
        with pytest.raises(InvalidSymbolError):
            _detail(session, provider, guard, symbol="A" * 40)
        # No external call for junk input.
        assert provider.history_calls == []
        assert guard.calls == 0


def test_unknown_symbol_raises_symbol_not_found(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        provider = _FakeProvider(raise_not_found=True)
        guard = _CountingGuard()
        with pytest.raises(SymbolNotFoundError):
            _detail(session, provider, guard, symbol="ZZZZ")


def test_provider_returning_empty_raises_symbol_not_found(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        provider = _FakeProvider(bars=[])
        guard = _CountingGuard()
        with pytest.raises(SymbolNotFoundError):
            _detail(session, provider, guard, symbol="ZZZZ")


def test_stats_anchor_to_latest_bar_not_calendar_today(initialised_db: str) -> None:
    """Regression (B059 F001 review): the return windows must anchor to the
    latest EOD bar, not to calendar ``now_day``. On a weekend the two diverge
    and an off-by-a-day window base flips the reported return — pin the bar
    anchor so stats agree with the ``as_of`` we surface."""

    # today = Sunday 2026-06-14; the latest available bar is Friday 2026-06-12.
    now_day = date(2026, 6, 14)
    latest_day = date(2026, 6, 12)

    def _bar(d: date, close: float) -> PriceBar:
        return PriceBar(
            ticker="X",
            bar_date=d,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            adj_close=close,
            volume=1_000,
        )

    # 1M base differs by anchor: target(now=06-14) − 30d = 05-15 → base 100;
    # target(latest=06-12) − 30d = 05-13 → base 90. Only the latter is correct.
    bars = [_bar(date(2026, 5, 12), 90.0), _bar(date(2026, 5, 14), 100.0), _bar(latest_day, 120.0)]

    with Session(get_engine()) as session:
        provider = _FakeProvider(bars=bars)
        guard = _CountingGuard()
        detail = get_symbol_price_detail(
            session, "AAPL", provider=provider, guard=guard, today=lambda: now_day
        )
        # as_of reflects the latest bar, and the 1M window agrees with it.
        assert detail.as_of == latest_day
        assert detail.returns.one_month == pytest.approx(120.0 / 90.0 - 1.0)


def test_raising_guard_short_circuits_lookup(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        provider = _FakeProvider()
        guard = _CountingGuard(raise_exc=SymbolRateLimitedError("slow down"))
        with pytest.raises(SymbolRateLimitedError):
            _detail(session, provider, guard, symbol="AAPL")
        # Guard fired and blocked the external fetch.
        assert guard.calls == 1
        assert provider.history_calls == []
