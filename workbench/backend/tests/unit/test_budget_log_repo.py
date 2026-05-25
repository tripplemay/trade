"""B027 F002 — BudgetLogRepository CRUD + month-rollover behaviour
plus an end-to-end alembic upgrade/downgrade test for the new
``tiingo_budget_log`` table.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.budget_log import BudgetLogRepository


@pytest.fixture
def repo(initialised_db: str) -> Iterator[BudgetLogRepository]:  # noqa: ARG001
    """Bind a BudgetLogRepository to a per-test SQLite DB."""

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    yield BudgetLogRepository(session)
    session.close()


def test_get_month_total_calls_returns_zero_when_empty(repo: BudgetLogRepository) -> None:
    assert repo.get_month_total_calls(date(2026, 5, 26)) == 0


def test_increment_inserts_first_row_then_accumulates(
    repo: BudgetLogRepository,
) -> None:
    repo.increment(date(2026, 5, 26), 0.00005)
    repo.increment(date(2026, 5, 26), 0.00005)
    row = repo.get_by_id(date(2026, 5, 26))
    assert row is not None
    assert row.call_count == 2
    assert row.total_cost_usd_est == pytest.approx(0.0001, rel=1e-6)
    assert row.month_year == "2026-05"


def test_get_month_total_sums_across_days_in_month(repo: BudgetLogRepository) -> None:
    for day in (date(2026, 5, 24), date(2026, 5, 25), date(2026, 5, 26)):
        repo.increment(day, 0.00005)
        repo.increment(day, 0.00005)
    total = repo.get_month_total_calls(date(2026, 5, 26))
    assert total == 6


def test_month_rollover_does_not_count_previous_month(
    repo: BudgetLogRepository,
) -> None:
    """Spec §4.4: a new calendar month re-counts from zero."""

    for _ in range(5):
        repo.increment(date(2026, 5, 31), 0.00005)
    # Switch to June 1.
    assert repo.get_month_total_calls(date(2026, 6, 1)) == 0
    repo.increment(date(2026, 6, 1), 0.00005)
    assert repo.get_month_total_calls(date(2026, 6, 1)) == 1
    # May's total is unchanged.
    assert repo.get_month_total_calls(date(2026, 5, 31)) == 5


def test_alembic_upgrade_creates_tiingo_budget_log_table(tmp_db_url: str) -> None:
    """End-to-end alembic: revision 0003 must materialise the table +
    its month_year index, and downgrade removes them cleanly."""

    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    command.upgrade(cfg, "head")
    inspector = inspect(get_engine())
    assert "tiingo_budget_log" in set(inspector.get_table_names())
    columns = {col["name"] for col in inspector.get_columns("tiingo_budget_log")}
    assert {"date", "month_year", "call_count", "total_cost_usd_est"} == columns
    indexes = {idx["name"] for idx in inspector.get_indexes("tiingo_budget_log")}
    assert "ix_tiingo_budget_log_month_year" in indexes

    # Downgrade strips the table + its index without touching B021/B023.
    command.downgrade(cfg, "-1")
    inspector = inspect(get_engine())
    assert "tiingo_budget_log" not in set(inspector.get_table_names())
    assert {
        "account",
        "backlog_entry",
        "snapshot_meta",
        "order_ticket",
        "fill_journal_entry",
        "account_snapshot",
    }.issubset(set(inspector.get_table_names()))
