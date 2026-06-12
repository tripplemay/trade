"""B037 F001 / B058 F002 — price-snapshot ingest CLI.

Drives ``fetch_main`` with a fake loader (no real Tiingo key) over the held
symbols **and the strategy target universe**, asserting idempotent persistence
into ``price_snapshot``, that the target universe (incl. the regime ETFs) is
priced + markable, and that an uncovered target symbol is reported loudly.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.prices.cli import (
    fetch_main,
    parse_args,
    symbols_to_fetch,
    target_universe,
)
from workbench_api.services.prices_provider import DbPriceProvider

# A handful of regime-mode ETFs that live in the target universe but a user does
# NOT necessarily hold — the exact symbols that were unmarkable before B058 F002.
_REGIME_ETFS = ("DBC", "IEF", "QQQ", "TLT", "VWO")


def _bar(ticker: str, d: date, close: float) -> PriceBar:
    return PriceBar(
        ticker=ticker, bar_date=d, open=close, high=close, low=close,
        close=close, adj_close=close, volume=1000,
    )


def _two_bars(ticker: str, close: float) -> list[PriceBar]:
    """Two consecutive closes so ``latest_two_by_symbol`` yields a mark."""

    return [
        _bar(ticker, date(2026, 6, 3), close),
        _bar(ticker, date(2026, 6, 4), close),
    ]


class _FakeLoader:
    def __init__(self, bars: dict[str, list[PriceBar]]) -> None:
        self._bars = bars

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        return self._bars.get(ticker.upper(), [])


class _UniverseLoader:
    """Returns two closes for EVERY requested symbol (full coverage)."""

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        return _two_bars(ticker.upper(), 100.0)


def _seed_snapshot(positions: list[dict[str, object]]) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id="snap-1", snapshot_at=datetime(2026, 6, 5), cash=0.0,
                base_currency="USD", positions=positions, source="bootstrap",
                created_at=datetime(2026, 6, 5),
            )
        )
        session.commit()


def test_fetch_main_persists_held_symbol_closes_idempotently(
    initialised_db: str,
) -> None:
    """Held symbols are still priced (Day P&L), now alongside the universe."""

    _seed_snapshot(
        [
            {"symbol": "AAPL", "shares": 10, "avg_cost": 150},
            {"symbol": "MSFT", "shares": 5, "avg_cost": 300},
        ]
    )
    loader = _FakeLoader(
        {
            "AAPL": [_bar("AAPL", date(2026, 6, 3), 192.0), _bar("AAPL", date(2026, 6, 4), 195.0)],
            "MSFT": [_bar("MSFT", date(2026, 6, 4), 410.0)],
        }
    )
    args = parse_args(["fetch"])
    summary = fetch_main(args, loader_factory=lambda: loader, today=date(2026, 6, 5))

    # Every held symbol + the whole target universe is fetched.
    with Session(get_engine()) as session:
        expected = symbols_to_fetch(session)
    assert summary.symbols == len(expected)
    assert {"AAPL", "MSFT"} <= set(expected)
    assert summary.saved == 3  # only AAPL(2)+MSFT(1) have bars in this loader
    assert summary.errors == 0

    # Re-run is a no-op (idempotent by (symbol, obs_date)).
    again = fetch_main(args, loader_factory=lambda: loader, today=date(2026, 6, 5))
    assert again.saved == 0
    with Session(get_engine()) as session:
        assert PriceSnapshotRepository(session).count() == 3


def test_fetch_main_covers_target_universe_including_regime_etfs(
    initialised_db: str,
) -> None:
    """B058 F002 (S2 upstream fix): with NO holdings, the CLI still prices the
    whole strategy target universe, and the regime ETFs become MARKABLE via the
    same ``DbPriceProvider`` the paper engine uses — so a paper book targeting
    them can build instead of stranding in cash."""

    args = parse_args(["fetch"])
    summary = fetch_main(
        args, loader_factory=_UniverseLoader, today=date(2026, 6, 5)
    )

    assert summary.symbols == len(target_universe())
    assert summary.errors == 0
    assert summary.uncovered_targets == ()  # full coverage → nothing uncovered

    # The exact symbols that were unmarkable before this fix now resolve marks
    # through the production paper mark source.
    with Session(get_engine()) as session:
        marks = DbPriceProvider(session).get_marks(_REGIME_ETFS)
    assert set(marks) == set(_REGIME_ETFS)


def test_fetch_main_reports_uncovered_target_symbols(initialised_db: str) -> None:
    """A target symbol with no closes is reported in ``uncovered_targets`` (loud
    coverage gap), not silently dropped."""

    universe = sorted(target_universe())
    covered, missing = universe[:-1], universe[-1]
    loader = _FakeLoader({sym: _two_bars(sym, 100.0) for sym in covered})

    args = parse_args(["fetch"])
    summary = fetch_main(args, loader_factory=lambda: loader, today=date(2026, 6, 5))

    assert missing in summary.uncovered_targets
    assert all(sym not in summary.uncovered_targets for sym in covered)


def test_coverage_check_rejects_nonpositive_closes(initialised_db: str) -> None:
    """A target with two stored closes that are NOT positive is reported as
    uncovered — the coverage check matches the engine's 'usable = positive close'
    definition, so a bad (zero) snapshot cannot produce a false all-clear (review
    finding: the check must not diverge from paper/engine._usable)."""

    universe = sorted(target_universe())
    good, bad = universe[:-1], universe[-1]
    bars: dict[str, list[PriceBar]] = {sym: _two_bars(sym, 100.0) for sym in good}
    bars[bad] = _two_bars(bad, 0.0)  # two closes, but both 0.0 → not buildable
    loader = _FakeLoader(bars)

    args = parse_args(["fetch"])
    summary = fetch_main(args, loader_factory=lambda: loader, today=date(2026, 6, 5))

    # Two rows exist for `bad`, yet it is correctly flagged uncovered (close ≤ 0).
    assert bad in summary.uncovered_targets
    assert all(sym not in summary.uncovered_targets for sym in good)
    # And the engine's mark source agrees it is not buildable.
    with Session(get_engine()) as session:
        marks = DbPriceProvider(session).get_marks([bad])
    # get_marks yields a (non-positive) mark, but the engine's _usable drops it —
    # the coverage check sided with the engine, not the raw row count.
    assert marks[bad].latest_close == 0.0


def test_target_universe_includes_regime_etfs() -> None:
    """The target universe covers the B057 regime ETFs (the symbols whose
    missing marks caused S2)."""

    assert set(_REGIME_ETFS) <= target_universe()
