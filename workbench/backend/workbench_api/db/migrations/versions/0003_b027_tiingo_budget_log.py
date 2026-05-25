"""B027 F002 — tiingo_budget_log table.

Adds the per-day Tiingo API call counter that
:class:`workbench_api.data.cost_guard.MonthlyBudgetGuard` consults
before every request. One row per UTC date; ``month_year`` is
denormalised onto the row so the per-month total is a single indexed
scan rather than a substring match on ``date``.

Revision ID: 0003_b027_tiingo_budget_log
Revises: 0002_b023_execution_workflow
Create Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_b027_tiingo_budget_log"
down_revision: str | Sequence[str] | None = "0002_b023_execution_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tiingo_budget_log",
        sa.Column("date", sa.Date(), primary_key=True, nullable=False),
        sa.Column("month_year", sa.String(length=7), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd_est", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_tiingo_budget_log_month_year",
        "tiingo_budget_log",
        ["month_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_tiingo_budget_log_month_year", table_name="tiingo_budget_log")
    op.drop_table("tiingo_budget_log")
