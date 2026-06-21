"""B071 F004 — permanent acceptance invariants (backend: DB + recommendation chain).

The DB / recommendation-chain half of "验收即代码": recurring real-data behaviour
invariants frozen as permanent CI regressions. Each has teeth (F005
mutation-checks it). The pure-engine invariants live in the repo-root
``tests/acceptance/``.

Invariants covered here:
  ② weights sum to 1 — precompute Master target on golden + save_batch guard
  ③ no negative cash — reconcile rejects an overdraw with 409
  ④ single account source — NAV aggregates only the account snapshot
  ⑥ defensive shares × mark ≈ equity — golden SGOV mark, never dollars-as-shares
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.recommendations.precompute import score_master_target
from workbench_api.services.nav import aggregate_account_state, aggregate_nav
from workbench_api.services.prices_provider import PriceMark
from workbench_api.services.reconcile import reconcile_ticket
from workbench_api.services.tickets import _defensive_diff_rows
from workbench_api.strategy_modes.registry import REGIME_STRATEGY_ID

# workbench/backend/tests/acceptance/<this> → parents[4] is the repo root.
GOLDEN_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures" / "golden"
_NOW = datetime(2026, 6, 12, 12, 0, 0)
_EARLIER = datetime(2026, 6, 10, 9, 0, 0)


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _golden_sgov_mark() -> float:
    """The latest real SGOV close in the golden fixture (golden-backed ⑥)."""
    last = None
    with (GOLDEN_DIR / "prices_daily.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] == "SGOV":
                last = float(row["close"])
    assert last is not None, "golden fixture has no SGOV price"
    return last


# ── ② weights sum to 1 ───────────────────────────────────────────────────────
def test_precompute_master_target_on_golden_sums_to_one() -> None:
    result = score_master_target(fixture_dir=GOLDEN_DIR)
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-4)


def test_save_batch_rejects_weights_not_summing_to_one(session: Session) -> None:
    """The persistence guard: a target set whose weights don't sum to 1.0 is
    refused (engine-drift tripwire). Mutation check: relax the guard → red."""
    repo = RecommendationSnapshotRepository(session)
    bad_rows = [
        {"symbol": "SPY", "sleeve": "momentum", "target_weight": 0.2},
        {"symbol": "SGOV", "sleeve": "risk_parity", "target_weight": 0.5},  # sums to 0.7
    ]
    with pytest.raises(ValueError, match="not 1.0"):
        repo.save_batch(
            as_of_date=date(2024, 12, 31),
            rows=bad_rows,
            master_meta={"data_source": "fixture", "planning_weights": {"momentum": 0.4}},
        )
    assert repo.latest_snapshot() == []


# ── ⑥ defensive shares × mark ≈ equity ───────────────────────────────────────
def test_defensive_sgov_shares_sized_from_golden_mark_not_dollars() -> None:
    """The ~100× over-buy regression (B050 F005): the defensive SGOV line must
    size shares from the real mark (equity / mark), never put the dollar amount
    in the share column. Driven by the real golden SGOV mark."""
    sgov_mark = _golden_sgov_mark()
    total_equity = 35_000.0
    snap = SimpleNamespace(positions=[{"symbol": "SPY", "shares": 50.0, "avg_cost": 500.0}])

    rows = _defensive_diff_rows(total_equity, snap, sgov_mark)
    sgov = next(r for r in rows if r["symbol"] == "SGOV")

    assert sgov["delta_shares"] != total_equity  # NOT dollars-as-shares
    assert abs(sgov["delta_shares"] * sgov_mark - total_equity) < 1e-6
    assert sgov["reference_price"] == sgov_mark


# ── ④ single account source ──────────────────────────────────────────────────
class _FakeProvider:
    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {s.upper(): self._marks[s.upper()] for s in symbols if s.upper() in self._marks}


def test_nav_aggregates_only_the_account_snapshot(session: Session) -> None:
    """NAV / account state come from the single account-snapshot source, marked
    to market — not from cost basis, not double-counted. Mutation check: add a
    second source or use cost basis → red."""
    session.add(
        AccountSnapshot(
            id="b071-acc-snap",
            snapshot_at=_EARLIER,
            cash=5_000.0,
            base_currency="USD",
            positions=[{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}],
            source="ui_edit",
            created_at=_EARLIER,
        )
    )
    session.commit()
    provider = _FakeProvider({"AAPL": PriceMark(latest_close=195.0, prior_close=192.0)})

    present, nav = aggregate_account_state(session, provider)
    assert present is True
    # 5000 cash + 10 × 195 market = 6950 (NOT 10 × 150 cost).
    assert nav == pytest.approx(6_950.0)
    assert aggregate_nav(session, provider) == pytest.approx(6_950.0)


# ── ③ no negative cash ───────────────────────────────────────────────────────
def test_reconcile_rejects_negative_cash_overdraw(session: Session) -> None:
    """An overdrawing fill set (buy > available cash) must fail-fast with 409,
    never persist a negative-cash account. Mutation check: drop the guard → red."""
    session.add(
        AccountSnapshot(
            id="b071-snap-regime",
            snapshot_at=_EARLIER,
            strategy_id=REGIME_STRATEGY_ID,
            cash=Decimal("500"),
            base_currency="USD",
            positions=[],
            source="ui_edit",
            created_at=_EARLIER,
        )
    )
    session.add(
        OrderTicket(
            id="b071-tkt-regime",
            ticket_date=date(2026, 6, 12),
            strategy_id=REGIME_STRATEGY_ID,
            snapshot_id="b071-snap-regime",
            target_positions_id="tp-b071-tkt-regime",
            markdown_path="docs/runs/2026-06-12/b071-tkt-regime.md",
            status="generated",
            created_at=_NOW,
        )
    )
    session.add(
        FillJournalEntry(
            id="b071-fill-regime-0",
            ticket_id="b071-tkt-regime",
            order_seq=1,
            symbol="SPY",
            side="buy",
            shares=Decimal("100"),
            fill_price=Decimal("100"),  # 100 × 100 = $10,000 buy vs $500 cash
            commission=Decimal("0"),
            fees=Decimal("0"),
            currency="USD",
            filled_at=_NOW,
            source="manual_entry",
            notes=None,
            created_at=_NOW,
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc:
        reconcile_ticket(session, "b071-tkt-regime", now=_NOW)
    assert exc.value.status_code == 409
