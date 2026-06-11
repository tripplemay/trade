"""B056 F001 — paper-trading orchestration service (DB-backed).

Covers activation (builds the first book from the Master target + persists
positions / cash / rebalance log), the all-cash path when no target exists yet,
the one-account-per-strategy guard, and ``rebalance_if_due`` (no churn on a
stable target, rebalance on a changed allocation).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import (
    PaperPositionRepository,
    PaperRebalanceRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.service import (
    PaperAccountExistsError,
    activate_paper_account,
    rebalance_if_due,
)
from workbench_api.services.prices_provider import PriceMark

NOW = datetime(2026, 6, 12, 21, 0, tzinfo=UTC)
ON_DATE = date(2026, 6, 12)


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


def _seed_targets(
    session: Session, rows: list[dict[str, object]], *, as_of: date
) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        as_of_date=as_of, rows=rows, master_meta={"data_source": "real"}
    )
    session.commit()


def test_activate_builds_first_book_from_master_target(session: Session) -> None:
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "momentum", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "momentum", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
        provider=_FakeProvider({"AAA": 100.0, "BBB": 50.0}),
    )
    session.commit()

    assert plan is not None and plan.traded is True
    assert account.cash == pytest.approx(0.1)
    assert account.last_rebalanced_on == ON_DATE
    assert account.target_key is not None

    positions = {
        p.symbol: p for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert positions["AAA"].shares == pytest.approx(599.4)
    assert positions["BBB"].shares == pytest.approx(799.2)

    rebals = PaperRebalanceRepository(session).list_by_account(account.id)
    assert len(rebals) == 1
    assert rebals[0].cost == pytest.approx(99.9)
    assert rebals[0].rebalance_date == ON_DATE


def test_activate_with_no_target_is_all_cash(session: Session) -> None:
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        initial_capital=50_000.0,
        provider=_FakeProvider({}),
    )
    session.commit()
    assert plan is None
    assert account.cash == pytest.approx(50_000.0)
    assert account.target_key is None
    assert PaperPositionRepository(session).list_by_account(account.id) == []


def test_activate_twice_raises(session: Session) -> None:
    _seed_targets(
        session,
        [{"symbol": "AAA", "sleeve": "m", "target_weight": 1.0}],
        as_of=date(2026, 3, 31),
    )
    activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        provider=_FakeProvider({"AAA": 100.0}),
    )
    session.commit()
    with pytest.raises(PaperAccountExistsError):
        activate_paper_account(
            session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
            provider=_FakeProvider({"AAA": 100.0}),
        )


def test_rebalance_if_due_noop_on_unchanged_target(session: Session) -> None:
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0})
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        provider=provider,
    )
    session.commit()
    # Same target set still latest → no rebalance.
    plan = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW, provider=provider
    )
    assert plan is None


def test_rebalance_if_due_rebalances_on_changed_allocation(session: Session) -> None:
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0})
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        provider=provider,
    )
    session.commit()

    # New quarter publishes a different allocation (later as_of_date → latest).
    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.3},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.7},
        ],
        as_of=date(2026, 6, 30),
    )
    plan = rebalance_if_due(
        session, account, on_date=date(2026, 6, 30), now=NOW, provider=provider
    )
    session.commit()
    assert plan is not None and plan.traded is True
    # Two rebalance rows now (activation + this one).
    assert len(PaperRebalanceRepository(session).list_by_account(account.id)) == 2
    # BBB weight rose → BBB shares should now exceed AAA's market value share.
    positions = {
        p.symbol: p for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert positions["BBB"].shares * 50.0 > positions["AAA"].shares * 100.0
