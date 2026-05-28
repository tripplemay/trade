"""B031 F002 — LLMBudgetLogRepository CRUD + month-rollover behaviour
plus an end-to-end alembic upgrade/downgrade test for the new
``llm_budget_log`` table.

Mirrors :mod:`tests.unit.test_budget_log_repo` (Tiingo B027) so the
two budget-log surfaces share assertions / fixtures patterns — a
maintainer reading both can swap one for the other in their head.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.llm_budget_log import LLMBudgetLogRepository


@pytest.fixture
def repo(initialised_db: str) -> Iterator[LLMBudgetLogRepository]:  # noqa: ARG001
    """Bind an LLMBudgetLogRepository to a per-test SQLite DB."""

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    yield LLMBudgetLogRepository(session)
    session.close()


def test_get_month_total_usd_returns_zero_when_empty(
    repo: LLMBudgetLogRepository,
) -> None:
    assert repo.get_month_total_usd(date(2026, 5, 27)) == 0.0


def test_increment_inserts_first_row_then_accumulates(
    repo: LLMBudgetLogRepository,
) -> None:
    repo.increment(date(2026, 5, 27), 1.5)
    repo.increment(date(2026, 5, 27), 2.25)
    row = repo.get_by_id(date(2026, 5, 27))
    assert row is not None
    assert row.call_count == 2
    assert row.total_cost_usd_est == pytest.approx(3.75)
    assert row.month_year == "2026-05"


def test_get_month_total_sums_across_days_in_month(
    repo: LLMBudgetLogRepository,
) -> None:
    """Per-day rows must roll up to a single per-month total — that's
    what :class:`MonthlyBudgetGuard` checks before each request."""

    repo.increment(date(2026, 5, 24), 1.0)
    repo.increment(date(2026, 5, 25), 2.0)
    repo.increment(date(2026, 5, 26), 3.0)
    repo.increment(date(2026, 5, 27), 4.0)
    total = repo.get_month_total_usd(date(2026, 5, 27))
    assert total == pytest.approx(10.0)


def test_month_rollover_does_not_count_previous_month(
    repo: LLMBudgetLogRepository,
) -> None:
    """Spec §F002 (6): a new calendar month resets the running total
    to zero so the cap re-arms automatically."""

    for _ in range(3):
        repo.increment(date(2026, 5, 31), 50.0)
    # Switch to June 1.
    assert repo.get_month_total_usd(date(2026, 6, 1)) == 0.0
    repo.increment(date(2026, 6, 1), 5.0)
    assert repo.get_month_total_usd(date(2026, 6, 1)) == pytest.approx(5.0)
    # May's total is unchanged.
    assert repo.get_month_total_usd(date(2026, 5, 31)) == pytest.approx(150.0)


def test_alembic_upgrade_creates_llm_budget_log_table(tmp_db_url: str) -> None:
    """End-to-end alembic: revision 0004 must materialise the table +
    its month_year index, and downgrade removes them cleanly without
    touching the B021/B023/B027 baseline."""

    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    # Upgrade to B031's revision specifically rather than ``head``; later
    # batches (B033+) add migrations above 0004, so ``-1`` from head no
    # longer targets this batch's table. Pinning the revision keeps the
    # B031 contract test stable as new migrations land.
    command.upgrade(cfg, "0004_b031_llm_budget_log")
    inspector = inspect(get_engine())
    table_names = set(inspector.get_table_names())
    assert "llm_budget_log" in table_names
    columns = {col["name"] for col in inspector.get_columns("llm_budget_log")}
    assert {"date", "month_year", "call_count", "total_cost_usd_est"} == columns
    indexes = {idx["name"] for idx in inspector.get_indexes("llm_budget_log")}
    assert "ix_llm_budget_log_month_year" in indexes

    # Downgrade to the revision before B031 to verify this batch's
    # table + index are dropped cleanly. Same reasoning as the explicit
    # upgrade target above — ``-1`` from head moves with each new batch.
    command.downgrade(cfg, "0003_b027_tiingo_budget_log")
    inspector = inspect(get_engine())
    after_table_names = set(inspector.get_table_names())
    assert "llm_budget_log" not in after_table_names
    # Tiingo budget log (0003) + all earlier baseline tables stay.
    assert {
        "account",
        "backlog_entry",
        "snapshot_meta",
        "order_ticket",
        "fill_journal_entry",
        "account_snapshot",
        "tiingo_budget_log",
    }.issubset(after_table_names)


def test_repository_round_trip_matches_schema(
    repo: LLMBudgetLogRepository,
) -> None:
    """Pin the exact columns the model declares so a future schema
    edit cannot drift silently from the migration."""

    repo.increment(date(2026, 5, 27), 0.123456)
    row = repo.get_by_id(date(2026, 5, 27))
    assert row is not None
    # log_date column maps to the SQL column 'date' but the Python
    # attribute is ``log_date`` (matching Tiingo repo convention).
    assert row.log_date == date(2026, 5, 27)
    assert row.month_year == "2026-05"
    assert row.call_count == 1
    assert row.total_cost_usd_est == pytest.approx(0.123456)
