"""B057 F004 — multi-account model + parameterized execution chain.

Each strategy mode has its OWN real account (account_snapshot.strategy_id), and
the execution chain (position-diff / ticket / fills / reconcile / journal) reads
and writes the mode's own account + target. Master is the default mode, so the
existing single-account path is byte-identical (the no-arg calls below pin that).

The safety-critical pins:
* per-mode account isolation (a regime write never touches the Master account);
* ★ Master backward compatibility (default strategy_id → master_portfolio);
* B053 reconcile fail-fast (oversell / negative-cash 409) holds PER MODE;
* reconcile writes back to the ticket's OWN mode + scopes idempotency by it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any

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
from workbench_api.schemas.execution import AccountUpdateRequest, PositionEntry
from workbench_api.services.execution import (
    get_latest_account,
    get_position_diff,
    update_account,
)
from workbench_api.services.prices_provider import PriceMark
from workbench_api.services.reconcile import get_journal_history, reconcile_ticket
from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID, REGIME_STRATEGY_ID

_NOW = datetime(2026, 6, 12, 12, 0, 0)
# Prior snapshots are seeded EARLIER than the reconcile (now=_NOW), so the new
# fill_reconcile snapshot genuinely wins latest() (mirrors the real timeline:
# the account existed before the user reconciled today's fills).
_EARLIER = datetime(2026, 6, 10, 9, 0, 0)
_MARKS = {"SPY": 100.0, "SGOV": 50.0, "AAA": 100.0}


class _FakeProvider:
    def __init__(self, marks: dict[str, float]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {
            s: PriceMark(self._marks[s], self._marks[s])
            for s in {x.upper() for x in symbols if x}
            if s in self._marks
        }


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _seed_account(
    session: Session,
    *,
    snap_id: str,
    strategy_id: str,
    cash: float,
    positions: list[dict[str, Any]],
    source: str = "ui_edit",
    at: datetime = _EARLIER,
) -> None:
    session.add(
        AccountSnapshot(
            id=snap_id,
            snapshot_at=at,
            strategy_id=strategy_id,
            cash=Decimal(str(cash)),
            base_currency="USD",
            positions=positions,
            source=source,
            created_at=at,
        )
    )
    session.commit()


def _seed_ticket(
    session: Session, *, ticket_id: str, strategy_id: str, snapshot_id: str
) -> None:
    session.add(
        OrderTicket(
            id=ticket_id,
            ticket_date=date(2026, 6, 12),
            strategy_id=strategy_id,
            snapshot_id=snapshot_id,
            target_positions_id=f"tp-{ticket_id}",
            markdown_path=f"docs/runs/2026-06-12/{ticket_id}.md",
            status="generated",
            created_at=_NOW,
        )
    )
    session.commit()


def _seed_fills(session: Session, *, ticket_id: str, rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows):
        session.add(
            FillJournalEntry(
                id=f"fill-{ticket_id}-{index}",
                ticket_id=ticket_id,
                order_seq=index + 1,
                symbol=row["symbol"],
                side=row["side"],
                shares=Decimal(str(row["shares"])),
                fill_price=Decimal(str(row["fill_price"])),
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


def _seed_target(session: Session, *, strategy_id: str, weights: dict[str, float]) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=strategy_id,
        as_of_date=date(2026, 5, 31),
        rows=[
            {"symbol": s, "sleeve": "test", "target_weight": w} for s, w in weights.items()
        ],
        master_meta={"data_source": "real"},
    )
    session.commit()


# --- per-mode account isolation -----------------------------------------------


def test_accounts_are_isolated_per_mode(session: Session) -> None:
    update_account(
        session,
        AccountUpdateRequest(cash=10_000, base_currency="USD",
                             positions=[PositionEntry(symbol="AAA", shares=5, avg_cost=100)]),
        strategy_id=MASTER_STRATEGY_ID, now=_NOW,
    )
    update_account(
        session,
        AccountUpdateRequest(cash=99_999, base_currency="USD",
                             positions=[PositionEntry(symbol="SPY", shares=1, avg_cost=100)]),
        strategy_id=REGIME_STRATEGY_ID, now=_NOW,
    )
    master = get_latest_account(session, MASTER_STRATEGY_ID)
    regime = get_latest_account(session, REGIME_STRATEGY_ID)
    assert master is not None and regime is not None
    assert float(master.cash) == 10_000 and {p.symbol for p in master.positions} == {"AAA"}
    assert float(regime.cash) == 99_999 and {p.symbol for p in regime.positions} == {"SPY"}


def test_get_latest_account_defaults_to_master(session: Session) -> None:
    update_account(
        session,
        AccountUpdateRequest(cash=10_000, base_currency="USD", positions=[]),
        strategy_id=MASTER_STRATEGY_ID, now=_NOW,
    )
    update_account(
        session,
        AccountUpdateRequest(cash=42, base_currency="USD", positions=[]),
        strategy_id=REGIME_STRATEGY_ID, now=_NOW,
    )
    # No strategy_id → Master (backward compatible).
    default = get_latest_account(session)
    assert default is not None and float(default.cash) == 10_000


# --- per-mode position diff ---------------------------------------------------


def test_position_diff_reads_mode_account_and_target(session: Session) -> None:
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=100_000, positions=[])
    _seed_target(session, strategy_id=REGIME_STRATEGY_ID, weights={"SPY": 0.6, "SGOV": 0.4})
    diff = get_position_diff(
        session, strategy_id=REGIME_STRATEGY_ID, provider=_FakeProvider(_MARKS)
    )
    by_symbol = {e.symbol: e for e in diff.diff}
    assert set(by_symbol) == {"SPY", "SGOV"}
    assert by_symbol["SPY"].target_weight == 0.6
    # 0.6 × 100k / $100 = 600 target shares, from a flat (all-cash) regime account.
    assert by_symbol["SPY"].target_shares == pytest.approx(600.0)


def test_position_diff_master_unaffected_by_regime_data(session: Session) -> None:
    # Only regime has an account + target; Master sees its own empty state.
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=100_000, positions=[])
    _seed_target(session, strategy_id=REGIME_STRATEGY_ID, weights={"SPY": 1.0})
    master_diff = get_position_diff(session, provider=_FakeProvider(_MARKS))  # default master
    assert master_diff.current is None  # no master account
    assert master_diff.diff == []  # no master target


# --- per-mode reconcile + B053 fail-fast --------------------------------------


def test_reconcile_writes_back_to_ticket_mode_account(session: Session) -> None:
    _seed_account(session, snap_id="snap-master", strategy_id=MASTER_STRATEGY_ID,
                  cash=50_000, positions=[{"symbol": "AAA", "shares": 100.0, "avg_cost": 90.0}])
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=100_000, positions=[])
    _seed_ticket(session, ticket_id="tkt-regime", strategy_id=REGIME_STRATEGY_ID,
                 snapshot_id="snap-regime")
    _seed_fills(session, ticket_id="tkt-regime",
                rows=[{"symbol": "SPY", "side": "buy", "shares": 600, "fill_price": 100}])

    result = reconcile_ticket(session, "tkt-regime", now=_NOW)
    assert result.already_reconciled is False

    # The NEW snapshot belongs to regime and becomes regime's latest().
    regime = get_latest_account(session, REGIME_STRATEGY_ID)
    assert regime is not None and regime.source == "fill_reconcile"
    assert {p.symbol for p in regime.positions} == {"SPY"}
    # Master account is completely untouched (backward-compat / isolation).
    master = get_latest_account(session, MASTER_STRATEGY_ID)
    assert master is not None and master.id == "snap-master"
    assert {p.symbol for p in master.positions} == {"AAA"}


def test_reconcile_oversell_409_per_mode(session: Session) -> None:
    # Regime account holds 10 SPY; a fill sells 50 → impossible state.
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=1_000, positions=[{"symbol": "SPY", "shares": 10.0, "avg_cost": 100.0}])
    _seed_ticket(session, ticket_id="tkt-regime", strategy_id=REGIME_STRATEGY_ID,
                 snapshot_id="snap-regime")
    _seed_fills(session, ticket_id="tkt-regime",
                rows=[{"symbol": "SPY", "side": "sell", "shares": 50, "fill_price": 100}])
    with pytest.raises(HTTPException) as exc:
        reconcile_ticket(session, "tkt-regime", now=_NOW)
    assert exc.value.status_code == 409  # B053 fail-fast holds on the regime account


def test_reconcile_negative_cash_409_per_mode(session: Session) -> None:
    # Regime account has $500; a $10,000 buy overdraws it.
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=500, positions=[])
    _seed_ticket(session, ticket_id="tkt-regime", strategy_id=REGIME_STRATEGY_ID,
                 snapshot_id="snap-regime")
    _seed_fills(session, ticket_id="tkt-regime",
                rows=[{"symbol": "SPY", "side": "buy", "shares": 100, "fill_price": 100}])
    with pytest.raises(HTTPException) as exc:
        reconcile_ticket(session, "tkt-regime", now=_NOW)
    assert exc.value.status_code == 409


def test_reconcile_idempotency_is_scoped_per_mode(session: Session) -> None:
    # A regime ticket and a master ticket, both reconciled. Re-running the regime
    # reconcile must resolve to the REGIME post-reconcile snapshot, not master's.
    _seed_account(session, snap_id="snap-master", strategy_id=MASTER_STRATEGY_ID,
                  cash=50_000, positions=[])
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=100_000, positions=[])
    for sid, tkt, snap in (
        (MASTER_STRATEGY_ID, "tkt-master", "snap-master"),
        (REGIME_STRATEGY_ID, "tkt-regime", "snap-regime"),
    ):
        _seed_ticket(session, ticket_id=tkt, strategy_id=sid, snapshot_id=snap)
        _seed_fills(session, ticket_id=tkt,
                    rows=[{"symbol": "SPY", "side": "buy", "shares": 1, "fill_price": 100}])
    first = reconcile_ticket(session, "tkt-regime", now=_NOW)
    second = reconcile_ticket(session, "tkt-regime", now=_NOW)
    assert second.already_reconciled is True
    # The idempotent re-run returns the SAME regime snapshot, not a master one.
    regime_snap = get_latest_account(session, REGIME_STRATEGY_ID)
    assert regime_snap is not None
    assert second.snapshot_id == first.snapshot_id == regime_snap.id


# --- per-mode journal ---------------------------------------------------------


def test_journal_history_is_filtered_per_mode(session: Session) -> None:
    _seed_account(session, snap_id="snap-master", strategy_id=MASTER_STRATEGY_ID,
                  cash=1, positions=[])
    _seed_account(session, snap_id="snap-regime", strategy_id=REGIME_STRATEGY_ID,
                  cash=1, positions=[])
    _seed_ticket(session, ticket_id="tkt-master", strategy_id=MASTER_STRATEGY_ID,
                 snapshot_id="snap-master")
    _seed_ticket(session, ticket_id="tkt-regime", strategy_id=REGIME_STRATEGY_ID,
                 snapshot_id="snap-regime")

    master_journal = get_journal_history(session)  # default master
    regime_journal = get_journal_history(session, strategy_id=REGIME_STRATEGY_ID)
    assert {i.ticket_id for i in master_journal.items} == {"tkt-master"}
    assert {i.ticket_id for i in regime_journal.items} == {"tkt-regime"}
