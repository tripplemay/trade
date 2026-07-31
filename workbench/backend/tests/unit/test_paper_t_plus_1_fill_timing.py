"""B111 F004 fix-round — paper fill-timing unification regression tests.

Evaluator finding B111-F006-1: pre-fix the paper engine filled at the
SIGNAL SESSION's own close (the recommendations job computes the target
from session-T closes; filling at the session-T close is a same-session
fill the live manual workflow can never achieve), while the backtest
filled at T+1 open. The unified caliber bans same-session fills: the
paper side fills at the first close strictly after the signal session
(>= T+1 close). These tests pin:

  ① same-session marks → the fill defers (per-symbol filter: symbols surface
    as skipped, build_complete=False, the daily job retries)
  ② post-signal marks → the fill happens
  ③ a deferred build fills on the later run once marks postdate
  ④ the manual align_to_current_target repair primitive bypasses the guard
  ⑤ marks with unknown dates / targets with no signal date keep legacy behaviour
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperPositionRepository,
    PaperRebalanceRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.service import (
    activate_paper_account,
    align_to_current_target,
    rebalance_if_due,
)
from workbench_api.services.prices_provider import PriceMark

NOW = datetime(2026, 7, 1, 21, 0, tzinfo=UTC)
ON_DATE = date(2026, 7, 1)
SIGNAL_DATE = date(2026, 6, 30)


class _DatedProvider:
    """Fake provider whose marks carry an obs_date (the fill-timing input)."""

    def __init__(self, marks: dict[str, tuple[float, date]]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        out: dict[str, PriceMark] = {}
        for s in {x.upper() for x in symbols if x}:
            if s in self._marks:
                close, obs = self._marks[s]
                out[s] = PriceMark(close, close, latest_date=obs)
        return out


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _seed_targets(session: Session, *, as_of: date = SIGNAL_DATE) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        as_of_date=as_of,
        rows=[
            {"symbol": "AAA", "sleeve": "momentum", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "momentum", "target_weight": 0.4},
        ],
        master_meta={"data_source": "real"},
    )
    session.commit()


def _seed_changed_targets(session: Session, *, as_of: date) -> None:
    """A DIFFERENT allocation (flips target_key, so a rebalance is due)."""
    RecommendationSnapshotRepository(session).save_batch(
        as_of_date=as_of,
        rows=[
            {"symbol": "AAA", "sleeve": "momentum", "target_weight": 0.5},
            {"symbol": "BBB", "sleeve": "momentum", "target_weight": 0.5},
        ],
        master_meta={"data_source": "real"},
    )
    session.commit()


def _same_session_provider() -> _DatedProvider:
    # Marks dated ON the signal session — the pre-fix (same-session) fill.
    return _DatedProvider(
        {"AAA": (100.0, SIGNAL_DATE), "BBB": (50.0, SIGNAL_DATE)}
    )


def _post_signal_provider() -> _DatedProvider:
    # Marks dated strictly after the signal session (>= T+1 close).
    return _DatedProvider(
        {"AAA": (101.0, date(2026, 7, 1)), "BBB": (51.0, date(2026, 7, 1))}
    )


# ── ① same-session marks defer ───────────────────────────────────────────────
def test_activation_defers_on_same_session_marks(session: Session) -> None:
    _seed_targets(session)
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_same_session_provider(),
    )
    session.commit()

    # The caliber filter dropped every same-session mark → graceful no-op:
    # nothing traded, every target symbol surfaced as skipped (visible, H4),
    # and the book stays pending for the daily retry.
    assert plan is not None and plan.traded is False
    assert plan.skipped_symbols == ("AAA", "BBB")
    assert PaperPositionRepository(session).list_by_account(account.id) == []
    assert PaperRebalanceRepository(session).list_by_account(account.id) == []
    assert account.build_complete is False


def test_rebalance_defers_on_same_session_marks(session: Session) -> None:
    _seed_targets(session)
    account, _ = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_post_signal_provider(),
    )
    session.commit()
    assert account.target_key is not None

    # Publish a NEW allocation (later as_of, different weights → new key),
    # then offer only marks dated ON the new signal session.
    _seed_changed_targets(session, as_of=date(2026, 7, 1))
    plan = rebalance_if_due(
        session,
        account,
        on_date=date(2026, 7, 2),
        now=NOW,
        provider=_DatedProvider(
            {"AAA": (100.0, date(2026, 7, 1)), "BBB": (50.0, date(2026, 7, 1))}
        ),
    )
    session.commit()

    assert plan is None  # degraded no-op → not a rebalance event
    assert len(PaperRebalanceRepository(session).list_by_account(account.id)) == 1
    refreshed = PaperAccountRepository(session).get_by_strategy("master_portfolio")
    assert refreshed is not None and refreshed.build_complete is False


# ── ②③ post-signal marks fill (incl. the deferred-then-filled flow) ─────────
def test_deferred_rebalance_fills_once_marks_postdate(session: Session) -> None:
    _seed_targets(session)
    account, _ = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_post_signal_provider(),
    )
    session.commit()

    _seed_changed_targets(session, as_of=date(2026, 7, 1))
    defer = rebalance_if_due(
        session,
        account,
        on_date=date(2026, 7, 2),
        now=NOW,
        provider=_DatedProvider(
            {"AAA": (100.0, date(2026, 7, 1)), "BBB": (50.0, date(2026, 7, 1))}
        ),
    )
    assert defer is None

    filled = rebalance_if_due(
        session,
        account,
        on_date=date(2026, 7, 3),
        now=NOW,
        provider=_DatedProvider(
            {"AAA": (102.0, date(2026, 7, 2)), "BBB": (52.0, date(2026, 7, 2))}
        ),
    )
    session.commit()

    assert filled is not None and filled.traded is True
    rebals = PaperRebalanceRepository(session).list_by_account(account.id)
    assert len(rebals) == 2  # activation + this rebalance


def test_partial_defer_lets_postdated_names_fill(session: Session) -> None:
    """Per-symbol filtering (not a whole-book gate): with only AAA's mark still
    same-session, BBB fills at the post-signal close and AAA is surfaced as
    skipped (the daily job retries it) instead of paralysing the book."""
    _seed_targets(session)
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_DatedProvider(
            {
                "AAA": (100.0, SIGNAL_DATE),  # same-session → dropped
                "BBB": (51.0, date(2026, 7, 1)),  # post-signal → fills
            }
        ),
    )
    session.commit()

    assert plan is not None and plan.traded is True
    assert plan.skipped_symbols == ("AAA",)
    assert account.build_complete is False  # pending daily retry for AAA
    symbols = {
        p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert symbols == {"BBB"}


def test_activation_fills_on_post_signal_marks(session: Session) -> None:
    _seed_targets(session)
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
        provider=_post_signal_provider(),
    )
    session.commit()

    assert plan is not None and plan.traded is True
    assert account.target_key is not None
    positions = PaperPositionRepository(session).list_by_account(account.id)
    assert {p.symbol for p in positions} == {"AAA", "BBB"}


# ── ④ manual align bypasses the guard ────────────────────────────────────────
def test_manual_align_bypasses_fill_timing_guard(session: Session) -> None:
    _seed_targets(session)
    account, _ = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_post_signal_provider(),
    )
    session.commit()

    # The user-invoked repair primitive snaps the book to target on demand —
    # outside the forward-simulation cadence, so the timing guard does not
    # apply even with same-session marks.
    aligned, plan = align_to_current_target(
        session,
        "master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_same_session_provider(),
    )
    session.commit()

    assert aligned is not None and plan is not None and plan.traded is True


# ── ⑤ legacy fallbacks stay open ─────────────────────────────────────────────
def test_undated_marks_do_not_block(session: Session) -> None:
    """Synthetic providers without dates (unknown fill date) do not block —
    production DbPriceProvider marks always carry obs_date."""

    class _UndatedProvider:
        def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
            return {
                s.upper(): PriceMark(100.0, 100.0)
                for s in symbols
                if s.upper() in {"AAA", "BBB"}
            }

    _seed_targets(session)
    account, plan = activate_paper_account(
        session,
        strategy_id="master_portfolio",
        on_date=ON_DATE,
        now=NOW,
        provider=_UndatedProvider(),
    )
    session.commit()

    assert account is not None and plan is not None and plan.traded is True
