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
    PaperAccountRepository,
    PaperPositionRepository,
    PaperRebalanceRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.mtm import run_daily_mtm
from workbench_api.paper.service import (
    PaperAccountExistsError,
    activate_paper_account,
    align_to_current_target,
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


# --- B058 F001: degraded build does not lock the account; daily job retries ---


def test_activate_with_target_but_no_marks_does_not_lock_account(session: Session) -> None:
    """S2 stuck-bug reproduction: target exists but no marks at activation.

    The account builds nothing (all cash) yet MUST NOT be marked built — else
    the daily job (keyed on a target_key change) never retries and the account
    is stranded in cash forever. The fix leaves ``build_complete`` False so the
    next daily job rebuilds once the marks arrive."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    # Activate while the price source covers NONE of the target symbols.
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({}),
    )
    session.commit()

    # Degraded: all cash, target recorded but NOT marked built.
    assert plan is not None and plan.traded is False
    assert PaperPositionRepository(session).list_by_account(account.id) == []
    assert account.target_key is not None
    assert account.build_complete is False
    # The old bug: target_key committed + keyed daily check → permanent no-op.
    # The fix: marks arrive next day → the daily job rebuilds the book.
    marks = _FakeProvider({"AAA": 100.0, "BBB": 50.0})
    plan2 = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW, provider=marks
    )
    session.commit()
    assert plan2 is not None and plan2.traded is True
    assert account.build_complete is True
    positions = {
        p.symbol: p for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert set(positions) == {"AAA", "BBB"}
    assert positions["AAA"].shares == pytest.approx(599.4)
    assert positions["BBB"].shares == pytest.approx(799.2)


def test_partial_skip_retries_until_complete(session: Session) -> None:
    """A partly-markable target builds the markable part, stays pending, and is
    completed once the skipped symbol's mark arrives."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    # Only AAA is markable at activation → AAA built, BBB skipped, pending.
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({"AAA": 100.0}),
    )
    session.commit()
    assert plan is not None and plan.traded is True
    assert plan.skipped_symbols == ("BBB",)
    assert account.build_complete is False
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"AAA"}

    # BBB's mark arrives → the daily job finishes the build.
    both = _FakeProvider({"AAA": 100.0, "BBB": 50.0})
    plan2 = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW, provider=both
    )
    session.commit()
    assert plan2 is not None and plan2.skipped_symbols == ()
    assert account.build_complete is True
    held2 = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held2 == {"AAA", "BBB"}


def test_pending_build_does_not_churn_without_new_marks(session: Session) -> None:
    """A persistently-missing mark must NOT churn the partial book daily.

    While the skipped symbol stays unmarkable, ``rebalance_if_due`` is a no-op
    (no new rebalance row, no position change) — spec §3: no daily forced
    re-alignment, only retry when there is real build progress to make."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    only_aaa = _FakeProvider({"AAA": 100.0})
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=only_aaa,
    )
    session.commit()
    rebal_repo = PaperRebalanceRepository(session)
    rows_before = len(rebal_repo.list_by_account(account.id))
    shares_before = {
        p.symbol: p.shares
        for p in PaperPositionRepository(session).list_by_account(account.id)
    }

    # BBB still has no mark the next day → no progress → no-op, no churn.
    plan = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW, provider=only_aaa
    )
    session.commit()
    assert plan is None
    assert account.build_complete is False
    assert len(rebal_repo.list_by_account(account.id)) == rows_before
    shares_after = {
        p.symbol: p.shares
        for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert shares_after == shares_before


def test_full_build_marks_complete_and_does_not_churn(session: Session) -> None:
    """Master normal path (all marks present): one full build, then stable — no
    retry, no churn (backward-compatible behaviour)."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    provider = _FakeProvider({"AAA": 100.0, "BBB": 50.0})
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()
    assert plan is not None and plan.traded is True and plan.skipped_symbols == ()
    assert account.build_complete is True

    rebal_repo = PaperRebalanceRepository(session)
    assert len(rebal_repo.list_by_account(account.id)) == 1
    # Same target, fully built → daily job is a pure no-op (no second row).
    plan2 = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW, provider=provider
    )
    assert plan2 is None
    assert len(rebal_repo.list_by_account(account.id)) == 1


# --- B058 F004: manual "align to current target" primitive ------------------


def test_align_forces_rebalance_even_when_already_built(session: Session) -> None:
    """Align is UNCONDITIONAL: it re-pins a fully-built book to target on demand,
    where ``rebalance_if_due`` would be a no-op (the daily/manual distinction)."""

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
        initial_capital=100_000.0, provider=provider,
    )
    session.commit()
    rebal_repo = PaperRebalanceRepository(session)
    assert len(rebal_repo.list_by_account(account.id)) == 1
    assert account.build_complete is True

    # The daily job would no-op here; align FORCES a rebalance.
    acc, plan = align_to_current_target(
        session, "master_portfolio", on_date=date(2026, 6, 13), now=NOW, provider=provider
    )
    session.commit()
    assert acc is not None and plan is not None and plan.traded is True
    assert len(rebal_repo.list_by_account(account.id)) == 2  # forced a 2nd event


def test_align_builds_all_cash_book_to_target(session: Session) -> None:
    """Align builds an all-cash (degraded-activation) book to target on demand."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    # Activate with no marks → all cash, nothing built.
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({}),
    )
    session.commit()
    assert PaperPositionRepository(session).list_by_account(account.id) == []

    acc, plan = align_to_current_target(
        session, "master_portfolio", on_date=date(2026, 6, 13), now=NOW,
        provider=_FakeProvider({"AAA": 100.0, "BBB": 50.0}),
    )
    session.commit()
    assert acc is not None and plan is not None and plan.traded is True
    assert acc.build_complete is True
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"AAA", "BBB"}


def test_align_no_account_returns_none(session: Session) -> None:
    acc, plan = align_to_current_target(
        session, "master_portfolio", on_date=ON_DATE, now=NOW, provider=_FakeProvider({})
    )
    assert acc is None and plan is None


def test_align_no_target_returns_account_without_plan(session: Session) -> None:
    # Activate with no target at all → account exists, all cash.
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=50_000.0, provider=_FakeProvider({}),
    )
    session.commit()
    acc, plan = align_to_current_target(
        session, "master_portfolio", on_date=ON_DATE, now=NOW, provider=_FakeProvider({})
    )
    assert acc is not None and acc.id == account.id
    assert plan is None  # no target to align to


# --- B058 F001 adversarial-audit regression tests (review findings F1–F4) ---


def test_zero_close_mark_is_unmarkable_and_retried(session: Session) -> None:
    """Finding 1: a present-but-zero close must NOT silently strand a target
    weight as a 0-share 'build'. It is treated as unmarkable → skipped →
    build_complete False → retried once a usable (positive) close arrives."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    # BBB has a snapshot, but its close is 0.0 (bad price) — not a usable mark.
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({"AAA": 100.0, "BBB": 0.0}),
    )
    session.commit()
    assert plan is not None and plan.skipped_symbols == ("BBB",)
    assert account.build_complete is False
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"AAA"}  # BBB NOT built as 0 shares

    # A real positive BBB close arrives → the build finishes.
    plan2 = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW,
        provider=_FakeProvider({"AAA": 100.0, "BBB": 50.0}),
    )
    session.commit()
    assert plan2 is not None and plan2.skipped_symbols == ()
    assert account.build_complete is True
    held2 = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held2 == {"AAA", "BBB"}


def test_persistent_zero_close_does_not_churn(session: Session) -> None:
    """Finding (re-review): a target symbol whose close stays 0.0 must NOT churn
    the book daily. The pending-build guard uses the SAME 'usable = positive
    close' definition as the engine, so a persistent zero close keeps the build
    pending-but-untouched instead of re-trading every day."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    bad = _FakeProvider({"AAA": 100.0, "BBB": 0.0})  # BBB close persistently 0.0
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=bad,
    )
    session.commit()
    assert plan is not None and plan.skipped_symbols == ("BBB",)
    assert account.build_complete is False

    rebal_repo = PaperRebalanceRepository(session)
    rows_before = len(rebal_repo.list_by_account(account.id))
    shares_before = {
        p.symbol: p.shares
        for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    # BBB's close stays 0.0 across multiple days → every run is a no-op, no churn.
    for day in (13, 14, 15):
        plan_d = rebalance_if_due(
            session, account, on_date=date(2026, 6, day), now=NOW, provider=bad
        )
        session.commit()
        assert plan_d is None
    assert account.build_complete is False
    assert len(rebal_repo.list_by_account(account.id)) == rows_before
    shares_after = {
        p.symbol: p.shares
        for p in PaperPositionRepository(session).list_by_account(account.id)
    }
    assert shares_after == shares_before


def test_dust_markable_plus_missing_mark_does_not_churn(session: Session) -> None:
    """Finding 4 (high): a markable target whose tiny weight rounds to ~0 shares
    (never held) combined with a separate unmarkable target must NOT force a
    rebalance every day. The old 'markable - held' progress signal churned here;
    the finish-only guard leaves the partial book untouched (spec §3)."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.5},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.3},
            {"symbol": "CCC", "sleeve": "m", "target_weight": 1e-12},  # dust → 0 shares
            {"symbol": "DDD", "sleeve": "m", "target_weight": 0.2},
        ],
        as_of=date(2026, 3, 31),
    )
    # AAA/BBB/CCC markable; DDD has no mark. CCC's dust weight → 0 shares dropped.
    partial = _FakeProvider({"AAA": 100.0, "BBB": 50.0, "CCC": 100.0})
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=partial,
    )
    session.commit()
    assert plan is not None and "DDD" in plan.skipped_symbols
    assert account.build_complete is False
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"AAA", "BBB"}  # CCC dust dropped, DDD skipped

    rebal_repo = PaperRebalanceRepository(session)
    rows_before = len(rebal_repo.list_by_account(account.id))
    # DDD's mark never arrives → each daily run is a no-op, NOT a daily churn.
    for day in (13, 14, 15):
        plan_d = rebalance_if_due(
            session, account, on_date=date(2026, 6, day), now=NOW, provider=partial
        )
        session.commit()
        assert plan_d is None
    assert len(rebal_repo.list_by_account(account.id)) == rows_before


def test_pending_build_with_zero_equity_makes_no_progress(session: Session) -> None:
    """Finding 2 (defensive equity gate): a pending build with no equity to
    deploy makes no progress even when the target is fully markable — no spin,
    no churn, no spurious rebalance row."""

    _seed_targets(
        session,
        [{"symbol": "AAA", "sleeve": "m", "target_weight": 1.0}],
        as_of=date(2026, 3, 31),
    )
    # Activate with no marks → all-cash pending build.
    account, plan = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({}),
    )
    session.commit()
    assert plan is not None and plan.traded is False and account.build_complete is False

    # Drain cash to simulate "nothing to invest" (e.g. equity locked elsewhere).
    account.cash = 0.0
    PaperAccountRepository(session).upsert(account)
    session.commit()
    rebal_repo = PaperRebalanceRepository(session)
    rows_before = len(rebal_repo.list_by_account(account.id))

    # AAA is markable now, but equity is 0 → no progress, no rebalance.
    out = rebalance_if_due(
        session, account, on_date=date(2026, 6, 13), now=NOW,
        provider=_FakeProvider({"AAA": 100.0}),
    )
    session.commit()
    assert out is None
    assert account.build_complete is False
    assert len(rebal_repo.list_by_account(account.id)) == rows_before
    assert PaperPositionRepository(session).list_by_account(account.id) == []


def test_daily_mtm_heals_stuck_account_and_counts_only_real_rebalances(
    session: Session,
) -> None:
    """Finding 3 + production path: the daily job does not count a degraded no-op
    as a rebalance, and DOES heal a pending account once marks arrive — verified
    through the real ``run_daily_mtm`` entrypoint, not just ``rebalance_if_due``."""

    _seed_targets(
        session,
        [
            {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
            {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
        ],
        as_of=date(2026, 3, 31),
    )
    # Activate with no marks → stuck-in-cash pending (the S2 signature).
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({}),
    )
    session.commit()
    assert account.build_complete is False

    # Day 1 daily job, marks STILL missing → no rebalance counted, still pending.
    s1 = run_daily_mtm(
        session, on_date=date(2026, 6, 13), now=NOW, provider=_FakeProvider({"SPY": 100.0})
    )
    assert s1.rebalanced == 0
    session.refresh(account)
    assert account.build_complete is False

    # Day 2 daily job, marks arrive → the book is built, counted as 1 rebalance.
    s2 = run_daily_mtm(
        session, on_date=date(2026, 6, 14), now=NOW,
        provider=_FakeProvider({"AAA": 100.0, "BBB": 50.0, "SPY": 100.0}),
    )
    assert s2.rebalanced == 1
    session.refresh(account)
    assert account.build_complete is True
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"AAA", "BBB"}


def test_cadence_change_while_pending_attempts_new_allocation(session: Session) -> None:
    """A new allocation published while a build is still pending is attempted
    immediately (target_changed path), never blocked by the pending guard."""

    _seed_targets(
        session,
        [{"symbol": "AAA", "sleeve": "m", "target_weight": 1.0}],
        as_of=date(2026, 3, 31),
    )
    # Activate pending (AAA unmarkable at activation).
    account, _ = activate_paper_account(
        session, strategy_id="master_portfolio", on_date=ON_DATE, now=NOW,
        initial_capital=100_000.0, provider=_FakeProvider({}),
    )
    session.commit()
    assert account.build_complete is False

    # A new quarter publishes {BBB:1.0}; BBB is markable now.
    _seed_targets(
        session,
        [{"symbol": "BBB", "sleeve": "m", "target_weight": 1.0}],
        as_of=date(2026, 6, 30),
    )
    plan = rebalance_if_due(
        session, account, on_date=date(2026, 6, 30), now=NOW,
        provider=_FakeProvider({"BBB": 50.0}),
    )
    session.commit()
    assert plan is not None and plan.traded is True
    assert account.build_complete is True
    held = {p.symbol for p in PaperPositionRepository(session).list_by_account(account.id)}
    assert held == {"BBB"}
