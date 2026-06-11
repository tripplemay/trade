"""B056 F002 — daily paper MTM job + nav history + per-asset P&L.

Covers the daily job (rebalance-if-due → mark-to-market → record point), forward
accumulation across days, same-day idempotency, the per-asset P&L breakdown, the
SPY benchmark capture, and the pure ``compute_position_pnl`` helper.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import PaperNavHistoryRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.mtm import run_daily_mtm
from workbench_api.paper.pnl import compute_position_pnl
from workbench_api.paper.service import activate_paper_account
from workbench_api.services.prices_provider import PriceMark

NOW = datetime(2026, 6, 12, 21, 0, tzinfo=UTC)
DAY1 = date(2026, 6, 12)
DAY2 = date(2026, 6, 13)


class _FakeProvider:
    def __init__(self, marks: dict[str, float]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        out: dict[str, PriceMark] = {}
        for s in {x.upper() for x in symbols if x}:
            if s in self._marks:
                out[s] = PriceMark(self._marks[s], self._marks[s])
        return out


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _seed_targets(session: Session, rows: list[dict[str, object]], *, as_of: date) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        as_of_date=as_of, rows=rows, master_meta={"data_source": "real"}
    )
    session.commit()


def _activate(session: Session, provider: _FakeProvider):
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=DAY1, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()
    return account


def test_mtm_records_a_nav_point_with_breakdown_and_benchmark(session: Session) -> None:
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0, "SPY": 400.0})
    account = _activate(session, provider)

    summary = run_daily_mtm(session, on_date=DAY1, now=NOW, provider=provider)
    assert summary.accounts == 1 and summary.points == 1

    points = PaperNavHistoryRepository(session).list_by_account(account.id)
    assert len(points) == 1
    pt = points[0]
    # NAV = cash + 599.4*100 + 799.2*50 = 0.1 + 59940 + 39960 = 99900.1
    # (initial 100000 minus the 99.9 activation cost — the honest cost drag).
    assert pt.nav == pytest.approx(99_900.1)
    assert pt.benchmark_close == pytest.approx(400.0)
    assert pt.as_of_date == DAY1
    by = {p["symbol"]: p for p in pt.positions}
    assert by["AAA"]["market_value"] == pytest.approx(59_940.0)


def test_mtm_accumulates_forward_across_days(session: Session) -> None:
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0, "SPY": 400.0})
    account = _activate(session, provider)
    run_daily_mtm(session, on_date=DAY1, now=NOW, provider=provider)
    # Day 2: AAA rallies to 110.
    provider2 = _FakeProvider({"AAA": 110.0, "BBB": 50.0, "SPY": 404.0})
    run_daily_mtm(session, on_date=DAY2, now=NOW, provider=provider2)

    points = PaperNavHistoryRepository(session).list_by_account(account.id)
    assert [p.as_of_date for p in points] == [DAY1, DAY2]  # oldest-first
    # Day2 NAV rose: AAA +10/share * 599.4 sh = +5994 vs day1.
    assert points[1].nav == pytest.approx(points[0].nav + 5_994.0)


def test_mtm_is_idempotent_same_day(session: Session) -> None:
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0, "SPY": 400.0})
    account = _activate(session, provider)
    run_daily_mtm(session, on_date=DAY1, now=NOW, provider=provider)
    run_daily_mtm(session, on_date=DAY1, now=NOW, provider=provider)
    points = PaperNavHistoryRepository(session).list_by_account(account.id)
    assert len(points) == 1  # overwritten, not duplicated


def test_mtm_rebalances_when_allocation_changes(session: Session) -> None:
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0, "SPY": 400.0})
    _activate(session, provider)
    run_daily_mtm(session, on_date=DAY1, now=NOW, provider=provider)

    # New quarter allocation.
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.2},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.8},
        ],
        as_of=date(2026, 6, 30),
    )
    summary = run_daily_mtm(session, on_date=DAY2, now=NOW, provider=provider)
    assert summary.rebalanced == 1


def test_per_asset_pnl_pure_helper() -> None:
    out = compute_position_pnl(
        [("AAA", 10.0, 80.0), ("NOPRICE", 5.0, 20.0)],
        {"AAA": 100.0},
    )
    by = {p.symbol: p for p in out}
    # AAA: cost 800, value 1000 → +200 (+25%).
    assert by["AAA"].unrealized_pnl == pytest.approx(200.0)
    assert by["AAA"].unrealized_pnl_pct == pytest.approx(0.25)
    # Unmarkable symbol degrades to None (no guessed price).
    assert by["NOPRICE"].close is None
    assert by["NOPRICE"].unrealized_pnl is None
