"""Repository CRUD round-trip tests for all three B021 F002 models."""

from __future__ import annotations

import contextlib
from datetime import date, datetime
from decimal import Decimal

from workbench_api.db.engine import get_engine
from workbench_api.db.models import Account, BacklogEntry, SnapshotMeta
from workbench_api.db.repositories import (
    AccountRepository,
    BacklogRepository,
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


def test_alembic_upgrade_creates_tables(tmp_db_url: str) -> None:
    """End-to-end: drive Alembic itself against a fresh DB and confirm
    the three tables exist via raw SQL.
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
    assert {"account", "backlog_entry", "snapshot_meta"}.issubset(tables)
