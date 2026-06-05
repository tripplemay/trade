"""B037 F001 — build_home aggregation.

Covers NAV reuse, mark-to-market Day P&L (known closes → exact P&L), the
price-missing → null path, the empty-account state, and the per-sleeve
breakdown grouped by the positions' ``sleeve`` tag (incl. the
``unclassified`` bucket for legacy untagged holdings).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.services.home import build_home
from workbench_api.services.prices_provider import PriceMark
from workbench_api.settings import Settings

_NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
_SETTINGS = Settings(NEXTAUTH_SECRET="x", ALLOWED_USER_EMAIL="o@e.com")


class _FakeProvider:
    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {
            s.upper(): self._marks[s.upper()]
            for s in symbols
            if s.upper() in self._marks
        }


def _seed_account(session: Session, *, cash: float, equity: float) -> None:
    session.add(
        Account(
            account_id="research",
            name="Research",
            base_currency="USD",
            cash=cash,
            equity_value=equity,
            as_of_date=_NOW.date(),
        )
    )
    session.commit()


def _seed_snapshot(session: Session, positions: list[dict[str, object]]) -> None:
    session.add(
        AccountSnapshot(
            id="snap-1",
            snapshot_at=_NOW.replace(tzinfo=None),
            cash=1000.0,
            base_currency="USD",
            positions=positions,
            source="bootstrap",
            created_at=_NOW.replace(tzinfo=None),
        )
    )
    session.commit()


def test_nav_reuses_aggregate(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_account(session, cash=1000.0, equity=5000.0)
        home = build_home(session, _SETTINGS, _FakeProvider({}))
        assert home.nav == 6000.0


def test_day_pnl_mark_to_market_known_pnl(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_account(session, cash=0.0, equity=0.0)
        _seed_snapshot(
            session,
            [
                {"symbol": "AAPL", "shares": 10, "avg_cost": 150, "sleeve": "satellite_us_quality"},
                {"symbol": "MSFT", "shares": 5, "avg_cost": 300, "sleeve": "regime"},
            ],
        )
        provider = _FakeProvider(
            {
                "AAPL": PriceMark(latest_close=195.0, prior_close=192.0),
                "MSFT": PriceMark(latest_close=410.0, prior_close=400.0),
            }
        )
        home = build_home(session, _SETTINGS, provider)
        # 10*(195-192) + 5*(410-400) = 30 + 50 = 80; prior = 1920 + 2000 = 3920.
        assert home.day_pnl is not None
        assert home.day_pnl.value == pytest.approx(80.0)
        assert home.day_pnl.pct == pytest.approx(80.0 / 3920.0, rel=1e-4)


def test_day_pnl_null_when_no_prices(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_snapshot(
            session, [{"symbol": "AAPL", "shares": 10, "avg_cost": 150}]
        )
        home = build_home(session, _SETTINGS, _FakeProvider({}))
        assert home.day_pnl is None


def test_empty_account_nav_zero_day_pnl_null(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        home = build_home(session, _SETTINGS, _FakeProvider({}))
        assert home.nav == 0.0
        assert home.day_pnl is None
        # Registry sleeves still render (stable skeleton), all empty.
        assert {s.sleeve for s in home.sleeves} == {
            "regime",
            "risk_parity",
            "satellite_us_quality",
        }
        assert all(s.day_pnl is None and s.positions_summary == "—" for s in home.sleeves)


def test_sleeve_breakdown_groups_and_shares(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_snapshot(
            session,
            [
                {"symbol": "AAPL", "shares": 10, "avg_cost": 150, "sleeve": "satellite_us_quality"},
                {"symbol": "MSFT", "shares": 5, "avg_cost": 300, "sleeve": "regime"},
            ],
        )
        provider = _FakeProvider(
            {
                "AAPL": PriceMark(latest_close=195.0, prior_close=192.0),
                "MSFT": PriceMark(latest_close=410.0, prior_close=400.0),
            }
        )
        home = build_home(session, _SETTINGS, provider)
        by = {s.sleeve: s for s in home.sleeves}
        # marked latest: satellite=1950, regime=2050(5*410)=2050 → total=4000.
        assert by["satellite_us_quality"].nav_share == pytest.approx(1950.0 / 4000.0)
        assert by["regime"].nav_share == pytest.approx(2050.0 / 4000.0)
        assert by["satellite_us_quality"].day_pnl is not None
        assert by["satellite_us_quality"].day_pnl.value == pytest.approx(30.0)
        assert by["regime"].day_pnl is not None
        assert by["regime"].day_pnl.value == pytest.approx(50.0)
        # A registry sleeve with no positions: 0 share, null Day P&L, "—".
        assert by["risk_parity"].nav_share == pytest.approx(0.0)
        assert by["risk_parity"].day_pnl is None
        assert by["risk_parity"].positions_summary == "—"
        assert by["satellite_us_quality"].positions_summary == "1 position"


def test_untagged_position_falls_into_unclassified(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_snapshot(
            session,
            [
                {"symbol": "AAPL", "shares": 10, "avg_cost": 150},  # no sleeve tag
                {"symbol": "GOOG", "shares": 2, "avg_cost": 100, "sleeve": "regime"},
            ],
        )
        provider = _FakeProvider(
            {
                "AAPL": PriceMark(latest_close=195.0, prior_close=192.0),
                "GOOG": PriceMark(latest_close=150.0, prior_close=148.0),
            }
        )
        home = build_home(session, _SETTINGS, provider)
        by = {s.sleeve: s for s in home.sleeves}
        assert "unclassified" in by
        assert by["unclassified"].positions_summary == "1 position"
        assert by["unclassified"].day_pnl is not None
        assert by["unclassified"].day_pnl.value == pytest.approx(30.0)
