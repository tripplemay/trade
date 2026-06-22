"""B074 F002 — permanent acceptance guard: active paper targets are markable.

The bug class this batch fixes (a paper account whose target holdings have no mark
in its price source ``price_snapshot`` → the engine skips them → the book strands
in cash) is turned into a permanent CI regression here: for every ACTIVE paper
account, each target security must be markable through the same ``DbPriceProvider``
the paper engine builds from. If a future change drops the A-share CSV→snapshot sync
(or otherwise leaves a target unmarked), this guard goes red.

End-to-end (the full F001 + F002 loop, no network / no golden — golden carries no
A-shares): write a unified-shape A-share CSV → ``sync_cn_closes_from_csv`` →
``price_snapshot`` → seed a cn_attack target → ``activate_paper_account`` builds the
book → assert it built AND every active account's targets are covered. A sibling
"teeth" test deliberately leaves a target unmarked and asserts the guard catches it.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperPositionRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.service import activate_paper_account
from workbench_api.paper.targets import load_strategy_targets
from workbench_api.prices.cn_snapshot_sync import sync_cn_closes_from_csv
from workbench_api.services.prices_provider import DbPriceProvider
from workbench_api.strategy_modes.registry import CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID

NOW = datetime(2026, 6, 18, 21, 0, tzinfo=UTC)
ON_DATE = date(2026, 6, 18)
_CN_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
_CN_ATTACK_ROWS: list[dict[str, object]] = [
    {"symbol": "600519.SH", "sleeve": "cn_attack", "target_weight": 0.4},
    {"symbol": "000858.SZ", "sleeve": "cn_attack", "target_weight": 0.4},
    {"symbol": "CASH", "sleeve": "cash", "target_weight": 0.2},
]


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _write_cn_csv(path: Path, rows: list[tuple[str, str, float]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_CN_HEADER)
        for d, ticker, close in rows:
            writer.writerow([d, ticker, close, close, close, close, close, 1000])
    return path


def _seed_cn_attack_target(session: Session) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        as_of_date=date(2026, 6, 17),
        rows=_CN_ATTACK_ROWS,
        master_meta={"data_source": "real"},
    )
    session.commit()


def uncovered_paper_targets(session: Session) -> dict[str, list[str]]:
    """``{strategy_id: [unmarkable target symbols]}`` over every ACTIVE paper account.

    The permanent invariant: this must be empty. Targets are the paper weights
    (cash sentinel already stripped by ``load_strategy_targets``); a symbol is
    covered iff ``DbPriceProvider`` (the paper mark source) yields a mark."""

    provider = DbPriceProvider(session)
    uncovered: dict[str, list[str]] = {}
    for account in PaperAccountRepository(session).list_active():
        targets = load_strategy_targets(session, account.strategy_id)
        if targets is None:
            continue
        wanted = {s for s, w in targets.weights.items() if w > 0}
        marked = set(provider.get_marks(wanted))
        missing = sorted(wanted - marked)
        if missing:
            uncovered[account.strategy_id] = missing
    return uncovered


def test_active_paper_targets_all_markable_after_sync(
    session: Session, tmp_path: Path
) -> None:
    """Full loop: unified CSV → snapshot sync → cn_attack book builds → every active
    paper account's targets are covered (the bug class cannot recur silently)."""

    cn_csv = _write_cn_csv(
        tmp_path / "prices_daily.csv",
        [
            ("2026-06-17", "600519.SH", 1500.0),
            ("2026-06-18", "600519.SH", 1520.0),
            ("2026-06-17", "000858.SZ", 140.0),
            ("2026-06-18", "000858.SZ", 142.0),
        ],
    )
    sync_cn_closes_from_csv(session, prices_path=cn_csv)
    _seed_cn_attack_target(session)

    account, plan = activate_paper_account(
        session,
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
    )
    session.commit()

    # The book actually built (positions non-empty, cash reduced from the buffer).
    assert plan is not None and plan.traded is True
    assert account.build_complete is True
    assert PaperPositionRepository(session).list_by_account(account.id)

    # The permanent guard: no active paper account has an unmarkable target.
    assert uncovered_paper_targets(session) == {}


def test_guard_has_teeth_unmarked_target_is_detected(
    session: Session, tmp_path: Path
) -> None:
    """Deliberately leave one A-share target unmarked (sync covers only the other);
    the guard must flag it — proving it would go red if the sync regresses."""

    cn_csv = _write_cn_csv(
        tmp_path / "prices_daily.csv",
        [
            ("2026-06-17", "600519.SH", 1500.0),
            ("2026-06-18", "600519.SH", 1520.0),
            # 000858.SZ is intentionally absent from the CSV → no mark.
        ],
    )
    sync_cn_closes_from_csv(session, prices_path=cn_csv)
    _seed_cn_attack_target(session)
    activate_paper_account(
        session,
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        on_date=ON_DATE,
        now=NOW,
        initial_capital=100_000.0,
    )
    session.commit()

    uncovered = uncovered_paper_targets(session)
    assert uncovered == {CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID: ["000858.SZ"]}
