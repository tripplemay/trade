"""B074 F002 — cn_attack A-share paper account builds (the two-blocker fix).

The two cn_attack paper books (``cn_attack_quality_momentum`` /
``cn_attack_pure_momentum``) activated but never built: their A-share targets had
no mark in ``price_snapshot`` (root cause #1, fixed by the F001 CSV→snapshot sync),
AND their published target carries a literal ``CASH`` buffer row that the paper
engine skipped for want of a mark, pinning ``build_complete`` False forever (root
cause #2, fixed by stripping the cash sentinel in ``load_strategy_targets``).

These tests pin the downstream half: given A-share marks, a cn_attack book builds
its securities and leaves the cash weight as residual cash; a stranded all-cash
book heals once the marks arrive; and Master/regime targets (no cash sentinel) are
untouched (zero-regression).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import PaperPositionRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.service import activate_paper_account, rebalance_if_due
from workbench_api.paper.targets import CASH_SENTINEL_SYMBOLS, load_strategy_targets
from workbench_api.services.prices_provider import PriceMark
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
    MASTER_STRATEGY_ID,
)

NOW = datetime(2026, 6, 18, 21, 0, tzinfo=UTC)
ON_DATE = date(2026, 6, 18)

# A cn_attack-shaped published target: two A-share securities + a CASH buffer row
# (the precompute appends it so the snapshot sums to 1.0).
_CN_ATTACK_ROWS: list[dict[str, object]] = [
    {"symbol": "600519.SH", "sleeve": "cn_attack", "target_weight": 0.4},
    {"symbol": "000858.SZ", "sleeve": "cn_attack", "target_weight": 0.4},
    {"symbol": "CASH", "sleeve": "cash", "target_weight": 0.2},
]
_CN_MARKS = {"600519.SH": 1500.0, "000858.SZ": 140.0}
# A Master-shaped target: marked securities, NO cash sentinel (SGOV is the proxy).
_MASTER_ROWS: list[dict[str, object]] = [
    {"symbol": "AAA", "sleeve": "momentum", "target_weight": 0.6},
    {"symbol": "SGOV", "sleeve": "defensive", "target_weight": 0.4},
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


def test_cash_sentinel_stripped_from_paper_targets(session: Session) -> None:
    """``load_strategy_targets`` drops the CASH pseudo-symbol but keeps the
    securities; the full-target fingerprint (incl. cash) is preserved."""

    _seed(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        _CN_ATTACK_ROWS,
        as_of=date(2026, 6, 17),
    )
    targets = load_strategy_targets(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID)
    assert targets is not None
    assert set(targets.weights) == {"600519.SH", "000858.SZ"}
    assert not (CASH_SENTINEL_SYMBOLS & set(targets.weights))
    assert targets.target_key  # full-target fingerprint still present


def test_activate_cn_attack_builds_when_ashares_marked(session: Session) -> None:
    """With A-share marks present, the cn_attack book builds its securities and
    reaches build_complete — the cash weight lands as residual cash (the buffer)."""

    _seed(
        session,
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        _CN_ATTACK_ROWS,
        as_of=date(2026, 6, 17),
    )
    account, plan = activate_paper_account(
        session,
        strategy_id=CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
        provider=_FakeProvider(_CN_MARKS),
    )
    session.commit()

    assert plan is not None and plan.traded is True
    # CASH is NOT a skipped target (it was stripped) → the build completes.
    assert plan.skipped_symbols == ()
    assert account.build_complete is True
    positions = {
        p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert positions == {"600519.SH", "000858.SZ"}  # no CASH position
    # ~20% cash buffer preserved as residual cash, less the honest rebalance cost.
    assert account.cash == pytest.approx(20_000.0, rel=0.02)


def test_cn_attack_stranded_without_marks_heals_after_sync(session: Session) -> None:
    """The exact production bug → heal: a cn_attack book activated with NO A-share
    marks strands all-cash (build_complete False); once the marks land (the F001
    sync), the daily rebalance finishes the build (B058 finish-only retry)."""

    _seed(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        _CN_ATTACK_ROWS,
        as_of=date(2026, 6, 17),
    )
    # Activate with no marks → stranded all-cash, never built.
    account, _ = activate_paper_account(
        session,
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
        provider=_FakeProvider({}),
    )
    session.commit()
    assert account.build_complete is False
    assert account.cash == pytest.approx(100_000.0)
    assert PaperPositionRepository(session).list_by_account(account.id) == []

    # Marks arrive (A-share closes synced) → the daily job finishes the build.
    plan = rebalance_if_due(
        session,
        account,
        on_date=date(2026, 6, 19),
        now=NOW,
        provider=_FakeProvider(_CN_MARKS),
    )
    session.commit()
    assert plan is not None and plan.traded is True and plan.skipped_symbols == ()
    assert account.build_complete is True
    held = {
        p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert held == {"600519.SH", "000858.SZ"}


def test_master_target_without_cash_sentinel_is_unchanged(session: Session) -> None:
    """A target with no cash sentinel (Master / regime) is untouched by the strip —
    every published symbol stays in the paper weights (US/Master zero-regression)."""

    _seed(session, MASTER_STRATEGY_ID, _MASTER_ROWS, as_of=date(2026, 3, 31))
    targets = load_strategy_targets(session, MASTER_STRATEGY_ID)
    assert targets is not None
    assert set(targets.weights) == {"AAA", "SGOV"}
