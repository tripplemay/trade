"""B056 F002 — paper_nav_history table (daily forward MTM points).

One mark-to-market point per (paper account, date): forward NAV, cash,
per-position breakdown (JSON), and the benchmark (SPY) close. Written by the
daily ``workbench-paper-mtm`` timer; idempotent on (account_id, as_of_date).

Revision ID: 0019_b056_paper_nav_history
Revises: 0018_b056_paper_trading
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_b056_paper_nav_history"
down_revision: str | Sequence[str] | None = "0018_b056_paper_trading"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_nav_history",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column("benchmark_close", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["paper_account.id"]),
        sa.UniqueConstraint(
            "account_id", "as_of_date", name="uq_paper_nav_history_account_date"
        ),
    )
    op.create_index(
        "ix_paper_nav_history_account_id", "paper_nav_history", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_nav_history_account_id", table_name="paper_nav_history"
    )
    op.drop_table("paper_nav_history")
