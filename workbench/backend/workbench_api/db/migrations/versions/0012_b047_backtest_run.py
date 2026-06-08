"""B047 F001 — backtest_run table.

Adds the ``backtest_run`` table that is both the on-demand backtest work queue
and the result store (status ``queued → running → done|error``). The request
path enqueues + reads it; the async worker (B047 F002) claims + writes it, so
the request path never imports ``trade`` (§12.10.2).

Revision ID: 0012_b047_backtest_run
Revises: 0011_b048_price_history
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_b047_backtest_run"
down_revision: str | Sequence[str] | None = "0011_b048_price_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_run",
        sa.Column("run_id", sa.String(length=40), primary_key=True, nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("equity", sa.JSON(), nullable=True),
        sa.Column("allocations", sa.JSON(), nullable=True),
        sa.Column("trades", sa.JSON(), nullable=True),
        sa.Column("report_markdown", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_backtest_run_status_created", "backtest_run", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_run_status_created", table_name="backtest_run")
    op.drop_table("backtest_run")
