"""B047 F004 — investment_report table.

Adds the ``investment_report`` table — canonical Master/sleeve backtest reports
(``kind='investment'``) that back the user-facing Reports page. Upserted by
``(strategy_id, as_of_date)``.

Revision ID: 0013_b047_investment_report
Revises: 0012_b047_backtest_run
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_b047_investment_report"
down_revision: str | Sequence[str] | None = "0012_b047_backtest_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_report",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "strategy_id", "as_of_date", name="uq_investment_report_strategy_date"
        ),
    )
    op.create_index("ix_investment_report_slug", "investment_report", ["slug"])
    op.create_index(
        "ix_investment_report_as_of_date", "investment_report", ["as_of_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_investment_report_as_of_date", table_name="investment_report")
    op.drop_index("ix_investment_report_slug", table_name="investment_report")
    op.drop_table("investment_report")
