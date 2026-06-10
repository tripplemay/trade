"""Repository CRUD round-trip tests.

B021 F002 introduced the first three repositories (Account, BacklogEntry,
SnapshotMeta). B023 F001 adds the execution-workflow trio (OrderTicket,
FillJournalEntry, AccountSnapshot) plus a few bespoke helpers; each new
repository has its own round-trip test below.
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
from decimal import Decimal

from workbench_api.db.engine import get_engine
from workbench_api.db.models import (
    Account,
    AccountSnapshot,
    BacklogEntry,
    FillJournalEntry,
    OrderTicket,
    SnapshotMeta,
)
from workbench_api.db.repositories import (
    AccountRepository,
    AccountSnapshotRepository,
    BacklogRepository,
    FillJournalEntryRepository,
    OrderTicketRepository,
    SnapshotMetaRepository,
)
from workbench_api.db.session import get_session


def _make_account(account_id: str = "research-mvp", cash: str = "250000") -> Account:
    return Account(
        account_id=account_id,
        name="Research MVP",
        base_currency="USD",
        cash=Decimal(cash),
        equity_value=Decimal("0"),
        as_of_date=date(2026, 5, 15),
    )


def test_account_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = AccountRepository(session)

    assert repo.count() == 0
    assert repo.get_by_id("research-mvp") is None

    repo.upsert(_make_account())
    assert repo.count() == 1
    fetched = repo.get_by_id("research-mvp")
    assert fetched is not None
    assert fetched.name == "Research MVP"
    assert fetched.cash == Decimal("250000")

    repo.upsert(_make_account(cash="300000"))
    refetched = repo.get_by_id("research-mvp")
    assert refetched is not None
    assert refetched.cash == Decimal("300000")
    assert repo.count() == 1  # upsert did not duplicate

    assert repo.delete("research-mvp") is True
    assert repo.count() == 0
    assert repo.delete("research-mvp") is False  # second delete is no-op
    with contextlib.suppress(StopIteration):
        next(gen)


def test_backlog_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = BacklogRepository(session)

    entry = BacklogEntry(
        id="BL-TEST-1",
        title="title",
        description="desc",
        priority="low",
        decisions=["a", "b"],
        confirmed_at="2026-05-15",
        source="unit-test",
    )
    repo.upsert(entry)
    fetched = repo.get_by_id("BL-TEST-1")
    assert fetched is not None
    assert fetched.decisions == ["a", "b"]
    assert fetched.priority == "low"

    entry.priority = "high"
    entry.decisions = ["c"]
    repo.upsert(entry)
    refetched = repo.get_by_id("BL-TEST-1")
    assert refetched is not None
    assert refetched.priority == "high"
    assert refetched.decisions == ["c"]

    assert {row.id for row in repo.list_all()} == {"BL-TEST-1"}
    assert repo.delete("BL-TEST-1") is True
    with contextlib.suppress(StopIteration):
        next(gen)


def test_snapshot_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = SnapshotMetaRepository(session)

    snap = SnapshotMeta(
        snapshot_id="2026-05-15-public",
        manifest_path="data/public-cache/2026-05-15/manifest.json",
        quality_status="ok",
        created_at=datetime(2026, 5, 15, 10, 30, 0),
    )
    repo.upsert(snap)
    fetched = repo.get_by_id("2026-05-15-public")
    assert fetched is not None
    assert fetched.quality_status == "ok"
    assert fetched.manifest_path.endswith("manifest.json")

    snap.quality_status = "degraded:gap"
    repo.upsert(snap)
    refetched = repo.get_by_id("2026-05-15-public")
    assert refetched is not None
    assert refetched.quality_status == "degraded:gap"

    assert repo.delete("2026-05-15-public") is True
    assert repo.count() == 0
    with contextlib.suppress(StopIteration):
        next(gen)


def test_order_ticket_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = OrderTicketRepository(session)

    assert repo.count() == 0
    assert repo.latest() is None

    older = OrderTicket(
        id="TKT-001",
        ticket_date=date(2026, 5, 17),
        snapshot_id="2026-05-17-public",
        target_positions_id="tp-2026-05-17",
        markdown_path="docs/runs/2026-05-17/order-ticket-TKT-001.md",
        status="generated",
        created_at=datetime(2026, 5, 17, 12, 0, 0),
    )
    newer = OrderTicket(
        id="TKT-002",
        ticket_date=date(2026, 5, 18),
        snapshot_id="2026-05-18-public",
        target_positions_id="tp-2026-05-18",
        markdown_path="docs/runs/2026-05-18/order-ticket-TKT-002.md",
        status="generated",
        created_at=datetime(2026, 5, 18, 13, 30, 0),
    )
    repo.upsert(older)
    repo.upsert(newer)
    assert repo.count() == 2

    latest = repo.latest()
    assert latest is not None
    assert latest.id == "TKT-002"

    reconciled = repo.reconcile("TKT-001", datetime(2026, 5, 17, 16, 0, 0))
    assert reconciled is not None
    assert reconciled.status == "executed"
    assert reconciled.executed_at == datetime(2026, 5, 17, 16, 0, 0)

    # Idempotency: second reconcile is a no-op on the executed ticket.
    again = repo.reconcile("TKT-001", datetime(2026, 5, 17, 17, 0, 0))
    assert again is not None
    assert again.status == "executed"
    assert again.executed_at == datetime(2026, 5, 17, 16, 0, 0)

    voided = repo.void("TKT-002")
    assert voided is not None
    assert voided.status == "voided"
    # void on already-executed ticket returns None (not a generated row).
    assert repo.void("TKT-001") is None
    # reconcile on already-voided ticket returns None.
    assert repo.reconcile("TKT-002", datetime(2026, 5, 18, 20, 0, 0)) is None
    # Unknown ticket id round-trips to None on both helpers.
    assert repo.reconcile("TKT-MISSING", datetime(2026, 5, 18, 0, 0, 0)) is None
    assert repo.void("TKT-MISSING") is None

    with contextlib.suppress(StopIteration):
        next(gen)


def test_fill_journal_entry_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = FillJournalEntryRepository(session)

    assert repo.list_by_ticket("TKT-001") == []

    fills = [
        FillJournalEntry(
            id="F-001",
            ticket_id="TKT-001",
            order_seq=2,
            symbol="IEF",
            side="sell",
            shares=Decimal("45"),
            fill_price=Decimal("94.18"),
            commission=Decimal("0"),
            fees=Decimal("0"),
            currency="USD",
            filled_at=datetime(2026, 5, 30, 13, 32, 15),
            source="csv_upload",
            notes=None,
            created_at=datetime(2026, 5, 30, 14, 0, 0),
        ),
        FillJournalEntry(
            id="F-002",
            ticket_id="TKT-001",
            order_seq=1,
            symbol="SPY",
            side="buy",
            shares=Decimal("72"),
            fill_price=Decimal("501.85"),
            commission=Decimal("0"),
            fees=Decimal("0"),
            currency="USD",
            filled_at=datetime(2026, 5, 30, 13, 31, 42),
            source="csv_upload",
            notes=None,
            created_at=datetime(2026, 5, 30, 14, 0, 0),
        ),
        FillJournalEntry(
            id="F-003",
            ticket_id="TKT-002",
            order_seq=1,
            symbol="QQQ",
            side="buy",
            shares=Decimal("10"),
            fill_price=Decimal("450.10"),
            commission=Decimal("0.65"),
            fees=Decimal("0.01"),
            currency="USD",
            filled_at=datetime(2026, 5, 30, 13, 35, 0),
            source="manual_entry",
            notes="late add",
            created_at=datetime(2026, 5, 30, 14, 0, 0),
        ),
    ]
    for f in fills:
        repo.upsert(f)
    assert repo.count() == 3

    by_001 = repo.list_by_ticket("TKT-001")
    assert [row.id for row in by_001] == ["F-002", "F-001"]
    assert [row.order_seq for row in by_001] == [1, 2]

    by_002 = repo.list_by_ticket("TKT-002")
    assert [row.id for row in by_002] == ["F-003"]

    # An order_seq=null fill sorts last for the same ticket.
    unmatched = FillJournalEntry(
        id="F-004",
        ticket_id="TKT-001",
        order_seq=None,
        symbol="VOO",
        side="buy",
        shares=Decimal("3"),
        fill_price=Decimal("520.00"),
        commission=Decimal("0"),
        fees=Decimal("0"),
        currency="USD",
        filled_at=datetime(2026, 5, 30, 13, 40, 0),
        source="manual_entry",
        notes="unmatched",
        created_at=datetime(2026, 5, 30, 14, 0, 0),
    )
    repo.upsert(unmatched)
    by_001 = repo.list_by_ticket("TKT-001")
    assert [row.id for row in by_001] == ["F-002", "F-001", "F-004"]

    with contextlib.suppress(StopIteration):
        next(gen)


def test_account_snapshot_repository_round_trip(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    repo = AccountSnapshotRepository(session)

    assert repo.latest() is None
    older = AccountSnapshot(
        id="S-001",
        snapshot_at=datetime(2026, 5, 15, 8, 0, 0),
        cash=Decimal("250000"),
        base_currency="USD",
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500.0}],
        source="bootstrap",
        created_at=datetime(2026, 5, 15, 8, 0, 0),
    )
    newer = AccountSnapshot(
        id="S-002",
        snapshot_at=datetime(2026, 5, 17, 10, 0, 0),
        cash=Decimal("220000"),
        base_currency="USD",
        positions=[
            {"symbol": "SPY", "shares": 100, "avg_cost": 500.0},
            {"symbol": "IEF", "shares": 50, "avg_cost": 94.0},
        ],
        source="ui_edit",
        created_at=datetime(2026, 5, 17, 10, 0, 0),
    )
    repo.upsert(older)
    repo.upsert(newer)

    latest = repo.latest()
    assert latest is not None
    assert latest.id == "S-002"
    assert latest.source == "ui_edit"
    assert len(latest.positions) == 2

    # Round-trip JSON positions to confirm the column survives upsert.
    refetched = repo.get_by_id("S-002")
    assert refetched is not None
    assert refetched.positions[1]["symbol"] == "IEF"

    with contextlib.suppress(StopIteration):
        next(gen)


def test_account_snapshot_latest_tie_breaker_is_deterministic(
    initialised_db: str,
) -> None:
    """B053 F002 — two snapshots saved in the same instant (same snapshot_at,
    e.g. a double-click on the account form) must resolve to a STABLE latest().
    Here snapshot_at AND created_at are identical, so only the unique ``id``
    can break the tie — ordering must not flip between queries or depend on
    insertion order."""

    gen = get_session()
    session = next(gen)
    repo = AccountSnapshotRepository(session)

    same = datetime(2026, 6, 1, 9, 0, 0)
    a = AccountSnapshot(
        id="S-tie-a", snapshot_at=same, cash=Decimal("50000"),
        base_currency="USD", positions=[], source="ui_edit", created_at=same,
    )
    b = AccountSnapshot(
        id="S-tie-b", snapshot_at=same, cash=Decimal("60000"),
        base_currency="USD", positions=[], source="ui_edit", created_at=same,
    )
    # Insert in "wrong" order to prove ordering is not insertion-dependent.
    repo.upsert(b)
    repo.upsert(a)

    first = repo.latest()
    second = repo.latest()
    assert first is not None and second is not None
    assert first.id == "S-tie-b"  # id desc breaks the full tie deterministically
    assert first.id == second.id  # stable across repeated queries

    with contextlib.suppress(StopIteration):
        next(gen)


def test_alembic_upgrade_creates_tables(tmp_db_url: str) -> None:
    """End-to-end: drive Alembic itself against a fresh DB and confirm
    every workbench table exists via raw SQL. B023 F001 extends the
    asserted set from the original 3 B021/B022 tables to the full 6.
    """

    from alembic import command
    from alembic.config import Config

    backend_root = (__file__.rsplit("/tests/", 1)[0])
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)
    command.upgrade(cfg, "head")

    from sqlalchemy import inspect

    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    assert {
        "account",
        "backlog_entry",
        "snapshot_meta",
        "order_ticket",
        "fill_journal_entry",
        "account_snapshot",
    }.issubset(tables)

    # Re-running upgrade is a no-op (idempotent).
    command.upgrade(cfg, "head")
    inspector = inspect(get_engine())
    tables_again = set(inspector.get_table_names())
    assert tables_again == tables
