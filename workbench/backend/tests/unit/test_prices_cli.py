"""B037 F001 — price-snapshot ingest CLI.

Drives ``fetch_main`` with a fake loader (no real Tiingo key) over the
held symbols, asserting idempotent persistence into ``price_snapshot``
and the no-holdings short-circuit.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.prices.cli import fetch_main, parse_args


def _bar(ticker: str, d: date, close: float) -> PriceBar:
    return PriceBar(
        ticker=ticker, bar_date=d, open=close, high=close, low=close,
        close=close, adj_close=close, volume=1000,
    )


class _FakeLoader:
    def __init__(self, bars: dict[str, list[PriceBar]]) -> None:
        self._bars = bars

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        return self._bars.get(ticker.upper(), [])


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


def test_fetch_main_persists_closes_idempotently(initialised_db: str) -> None:
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
    assert summary.symbols == 2
    assert summary.saved == 3
    assert summary.errors == 0

    # Re-run is a no-op (idempotent by (symbol, obs_date)).
    again = fetch_main(args, loader_factory=lambda: loader, today=date(2026, 6, 5))
    assert again.saved == 0
    with Session(get_engine()) as session:
        assert PriceSnapshotRepository(session).count() == 3


def test_fetch_main_no_holdings_short_circuits(initialised_db: str) -> None:
    args = parse_args(["fetch"])
    summary = fetch_main(
        args, loader_factory=lambda: _FakeLoader({}), today=date(2026, 6, 5)
    )
    assert summary == type(summary)(symbols=0, saved=0, errors=0)
