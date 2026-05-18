"""B023 F001 — execution-workflow tables.

Adds the three tables that record the manual rebalance loop (Generate
Ticket → User executes in broker app → Upload fills → Reconcile):

* ``order_ticket``        — one row per ticket generation
* ``fill_journal_entry``  — append-only per-fill journal
* ``account_snapshot``    — point-in-time account state, source-tagged

Two non-PK indexes accompany the schema for the most common access
patterns:

* ``ix_fill_journal_entry_ticket_id`` — every fills/reconcile query
  filters by ``ticket_id``.
* ``ix_account_snapshot_snapshot_at`` — ``latest()`` and slippage
  analytics scan the snapshot timeline in time order.

Revision ID: 0002_b023_execution_workflow
Revises: 0001_initial
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_b023_execution_workflow"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_ticket",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("ticket_date", sa.Date(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("target_positions_id", sa.String(length=64), nullable=False),
        sa.Column("markdown_path", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "fill_journal_entry",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("order_seq", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("shares", sa.Numeric(20, 6), nullable=False),
        sa.Column("fill_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("commission", sa.Numeric(20, 4), nullable=False),
        sa.Column("fees", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("filled_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_fill_journal_entry_ticket_id",
        "fill_journal_entry",
        ["ticket_id"],
    )
    op.create_table(
        "account_snapshot",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False),
        sa.Column("cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_account_snapshot_snapshot_at",
        "account_snapshot",
        [sa.text("snapshot_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_account_snapshot_snapshot_at", table_name="account_snapshot")
    op.drop_table("account_snapshot")
    op.drop_index("ix_fill_journal_entry_ticket_id", table_name="fill_journal_entry")
    op.drop_table("fill_journal_entry")
    op.drop_table("order_ticket")
