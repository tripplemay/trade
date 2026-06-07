"""B048 F003 — mark-to-market NAV history reconstruction.

Pins that drawdown is computed from a NAV series valued at the
``price_history`` close on-or-before each snapshot date (not cost basis),
that per-sleeve series are independent, and that a snapshot date predating
price coverage degrades to cost basis with the symbol flagged.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.price_history import PriceHistoryRepository
from workbench_api.services.nav_history import (
    master_drawdown,
    per_sleeve_drawdowns,
    reconstruct_nav_history,
)

_FETCHED = datetime(2026, 6, 7, tzinfo=UTC)


def _seed_snapshot(
    *, snap_id: str, cash: float, positions: list[dict[str, Any]], at: datetime
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=snap_id,
                snapshot_at=at,
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions,
                source="bootstrap",
                created_at=at,
            )
        )
        session.commit()


def _seed_prices(rows: list[tuple[str, date, float]]) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        for symbol, obs_date, close in rows:
            repo.save_if_new(
                symbol=symbol, obs_date=obs_date, close=close,
                source="b045_unified_csv", fetched_at=_FETCHED,
            )
        session.commit()


def test_master_dd_marks_positions_to_market(initialised_db: str) -> None:
    """A flat share count whose market price falls produces a real master
    drawdown — cost basis (avg_cost flat) would have shown 0."""

    _seed_snapshot(
        snap_id="s1", cash=0.0,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500.0}],
        at=datetime(2026, 5, 1, 10, 0, 0),
    )
    _seed_snapshot(
        snap_id="s2", cash=0.0,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500.0}],
        at=datetime(2026, 5, 2, 10, 0, 0),
    )
    _seed_prices([("SPY", date(2026, 5, 1), 500.0), ("SPY", date(2026, 5, 2), 450.0)])

    with Session(get_engine()) as session:
        nav = reconstruct_nav_history(session)
        assert nav.master_series == (50_000.0, 45_000.0)
        assert master_drawdown(nav) == 0.10
        assert nav.degraded is False
        assert nav.degraded_symbols == ()


def test_per_sleeve_dd_is_independent(initialised_db: str) -> None:
    """Each sleeve's drawdown comes from its own marked NAV series; a flat
    sleeve stays at 0 while a falling sleeve shows its real drawdown."""

    positions = [
        {"symbol": "SPY", "shares": 100, "avg_cost": 500.0, "sleeve": "momentum"},
        {"symbol": "GLD", "shares": 100, "avg_cost": 180.0, "sleeve": "risk_parity"},
    ]
    _seed_snapshot(snap_id="s1", cash=0.0, positions=positions, at=datetime(2026, 5, 1, 10, 0, 0))
    _seed_snapshot(snap_id="s2", cash=0.0, positions=positions, at=datetime(2026, 5, 2, 10, 0, 0))
    _seed_prices(
        [
            ("SPY", date(2026, 5, 1), 500.0),
            ("SPY", date(2026, 5, 2), 400.0),  # momentum −20%
            ("GLD", date(2026, 5, 1), 180.0),
            ("GLD", date(2026, 5, 2), 180.0),  # risk_parity flat
        ]
    )

    with Session(get_engine()) as session:
        dd = per_sleeve_drawdowns(reconstruct_nav_history(session))
        assert dd["momentum"] == 0.20
        assert dd["risk_parity"] == 0.0


def test_degrades_to_cost_when_no_price_history(initialised_db: str) -> None:
    """A snapshot date with no price_history coverage falls back to cost
    basis for that holding and flags the symbol (v0.9.21 — annotate)."""

    _seed_snapshot(
        snap_id="s1", cash=1_000.0,
        positions=[{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}],
        at=datetime(2026, 5, 1, 10, 0, 0),
    )
    _seed_snapshot(
        snap_id="s2", cash=1_000.0,
        positions=[{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}],
        at=datetime(2026, 5, 2, 10, 0, 0),
    )
    # No price_history rows seeded at all.
    with Session(get_engine()) as session:
        nav = reconstruct_nav_history(session)
        # Both points degrade to cost: 1000 + 10×150 = 2500, flat → dd 0.
        assert nav.master_series == (2_500.0, 2_500.0)
        assert master_drawdown(nav) == 0.0
        assert nav.degraded is True
        assert "AAPL" in nav.degraded_symbols


def test_fewer_than_two_snapshots_zero_drawdown(initialised_db: str) -> None:
    _seed_snapshot(
        snap_id="s1", cash=0.0,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500.0}],
        at=datetime(2026, 5, 1, 10, 0, 0),
    )
    _seed_prices([("SPY", date(2026, 5, 1), 500.0)])
    with Session(get_engine()) as session:
        nav = reconstruct_nav_history(session)
        assert master_drawdown(nav) == 0.0
