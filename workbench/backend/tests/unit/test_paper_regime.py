"""B057 F003 — regime-adaptive paper account (forward simulation).

The B056 paper engine is parameterised by ``strategy_id`` and resolves a
strategy's target through the F001 generic target layer (``get_target``). So the
regime mode lights up its own forward-simulation account with no engine change:
seed the regime target → activate → the engine builds a virtual book that
faithfully tracks the *regime* allocation, independent of Master, and the daily
MTM job marks every account. These tests pin that, plus the monthly
rebalance-day hint (vs Master's quarterly).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperNavHistoryRepository,
    PaperPositionRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.mtm import run_daily_mtm
from workbench_api.paper.service import activate_paper_account
from workbench_api.services.paper import build_paper_view, list_paper_strategies
from workbench_api.services.prices_provider import PriceMark
from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID, REGIME_STRATEGY_ID

NOW = datetime(2026, 6, 12, 21, 0, tzinfo=UTC)
ON_DATE = date(2026, 6, 12)
_MARKS = {"SPY": 100.0, "SGOV": 50.0, "AAA": 100.0, "BBB": 50.0}
_REGIME_ROWS: list[dict[str, object]] = [
    {"symbol": "SPY", "sleeve": "risk_core", "target_weight": 0.6},
    {"symbol": "SGOV", "sleeve": "defensive", "target_weight": 0.4},
]
_MASTER_ROWS: list[dict[str, object]] = [
    {"symbol": "AAA", "sleeve": "momentum", "target_weight": 0.6},
    {"symbol": "BBB", "sleeve": "momentum", "target_weight": 0.4},
]


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


def _seed(
    session: Session, strategy_id: str, rows: list[dict[str, object]], *, as_of: date
) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=strategy_id,
        as_of_date=as_of,
        rows=rows,
        master_meta={"data_source": "real"},
    )
    session.commit()


def test_activate_regime_builds_book_from_regime_target(session: Session) -> None:
    _seed(session, REGIME_STRATEGY_ID, _REGIME_ROWS, as_of=date(2026, 5, 31))
    account, plan = activate_paper_account(
        session,
        strategy_id=REGIME_STRATEGY_ID,
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
        provider=_FakeProvider(_MARKS),
    )
    session.commit()

    assert plan is not None and plan.traded is True
    assert account.strategy_id == REGIME_STRATEGY_ID
    positions = {
        p.symbol: p for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    # Faithfully tracks the regime allocation (0.6 SPY @100, 0.4 SGOV @50),
    # net of the same cost the engine applies to Master.
    assert set(positions) == {"SPY", "SGOV"}
    assert positions["SPY"].shares == pytest.approx(599.4)
    assert positions["SGOV"].shares == pytest.approx(799.2)


def test_regime_and_master_are_independent_accounts(session: Session) -> None:
    _seed(session, MASTER_STRATEGY_ID, _MASTER_ROWS, as_of=date(2026, 3, 31))
    _seed(session, REGIME_STRATEGY_ID, _REGIME_ROWS, as_of=date(2026, 5, 31))
    provider = _FakeProvider(_MARKS)
    master_acc, _ = activate_paper_account(
        session, strategy_id=MASTER_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    regime_acc, _ = activate_paper_account(
        session, strategy_id=REGIME_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()

    assert master_acc.id != regime_acc.id
    pos_repo = PaperPositionRepository(session)
    master_syms = {p.symbol for p in pos_repo.list_by_account(master_acc.id)}
    regime_syms = {p.symbol for p in pos_repo.list_by_account(regime_acc.id)}
    # Each account holds ONLY its own strategy's target — no cross-contamination.
    assert master_syms == {"AAA", "BBB"}
    assert regime_syms == {"SPY", "SGOV"}


def test_regime_next_rebalance_hint_is_month_end(session: Session) -> None:
    _seed(session, REGIME_STRATEGY_ID, _REGIME_ROWS, as_of=date(2026, 5, 31))
    provider = _FakeProvider(_MARKS)
    activate_paper_account(
        session, strategy_id=REGIME_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()
    view = build_paper_view(session, REGIME_STRATEGY_ID, provider=provider)
    # Monthly cadence → next month-end (2026-06-12 → 2026-07-31).
    assert view.summary is not None
    assert view.summary.next_rebalance == "2026-07-31"


def test_master_next_rebalance_hint_stays_quarter_end(session: Session) -> None:
    _seed(session, MASTER_STRATEGY_ID, _MASTER_ROWS, as_of=date(2026, 3, 31))
    provider = _FakeProvider(_MARKS)
    activate_paper_account(
        session, strategy_id=MASTER_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()
    view = build_paper_view(session, MASTER_STRATEGY_ID, provider=provider)
    # Quarterly cadence → next quarter-end (2026-06-12 → 2026-06-30). Master
    # behaviour is unchanged (backward compat).
    assert view.summary is not None
    assert view.summary.next_rebalance == "2026-06-30"


def test_daily_mtm_covers_both_regime_and_master(session: Session) -> None:
    _seed(session, MASTER_STRATEGY_ID, _MASTER_ROWS, as_of=date(2026, 3, 31))
    _seed(session, REGIME_STRATEGY_ID, _REGIME_ROWS, as_of=date(2026, 5, 31))
    provider = _FakeProvider(_MARKS)
    master_acc, _ = activate_paper_account(
        session, strategy_id=MASTER_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    regime_acc, _ = activate_paper_account(
        session, strategy_id=REGIME_STRATEGY_ID, on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()

    summary = run_daily_mtm(session, on_date=date(2026, 6, 13), now=NOW, provider=provider)
    # Every active account is marked, not just Master.
    assert summary.accounts == 2
    nav_repo = PaperNavHistoryRepository(session)
    assert nav_repo.list_by_account(master_acc.id), "master account got no nav point"
    assert nav_repo.list_by_account(regime_acc.id), "regime account got no nav point"


def test_list_paper_strategies_includes_regime(session: Session) -> None:
    resp = list_paper_strategies(session)
    ids = {s.strategy_id for s in resp.strategies}
    assert {MASTER_STRATEGY_ID, REGIME_STRATEGY_ID} <= ids
    # Regime has no account until activated.
    regime = next(s for s in resp.strategies if s.strategy_id == REGIME_STRATEGY_ID)
    assert regime.has_account is False
    assert regime.name == "智能择时组合"


def test_paper_account_repo_lists_all_strategies(session: Session) -> None:
    """list_active returns every strategy's account (the MTM job's scope)."""

    _seed(session, MASTER_STRATEGY_ID, _MASTER_ROWS, as_of=date(2026, 3, 31))
    _seed(session, REGIME_STRATEGY_ID, _REGIME_ROWS, as_of=date(2026, 5, 31))
    provider = _FakeProvider(_MARKS)
    for sid in (MASTER_STRATEGY_ID, REGIME_STRATEGY_ID):
        activate_paper_account(
            session, strategy_id=sid, on_date=ON_DATE, now=NOW,
            initial_capital=100_000.0, provider=provider,
        )
    session.commit()
    accounts = PaperAccountRepository(session).list_active()
    assert {a.strategy_id for a in accounts} == {MASTER_STRATEGY_ID, REGIME_STRATEGY_ID}
