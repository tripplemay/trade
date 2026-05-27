"""B031 F002 — llm_budget_log table.

Adds the per-day LLM USD cost counter that
:class:`workbench_api.llm.cost_guard.MonthlyBudgetGuard` consults
before every aigc-gateway request. One row per UTC date;
``month_year`` is denormalised onto the row so the per-month total
is a single indexed scan rather than a substring match on ``date``
(B027 0003 pattern).

The guard's monthly cap is ¥1500 ≈ $200 USD
(``docs/product/llm-provider-evaluation-2026-05.md`` §6). Permanent
boundary **(m)** ties the cap to this table — every advise / embed
call writes its estimated cost here before issuing the HTTP request,
and a tripped cap raises :class:`workbench_api.llm.cost_guard.BudgetExceeded`
before billing reality.

Revision ID: 0004_b031_llm_budget_log
Revises: 0003_b027_tiingo_budget_log
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_b031_llm_budget_log"
down_revision: str | Sequence[str] | None = "0003_b027_tiingo_budget_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_budget_log",
        sa.Column("date", sa.Date(), primary_key=True, nullable=False),
        sa.Column("month_year", sa.String(length=7), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd_est", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_llm_budget_log_month_year",
        "llm_budget_log",
        ["month_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_budget_log_month_year", table_name="llm_budget_log")
    op.drop_table("llm_budget_log")
