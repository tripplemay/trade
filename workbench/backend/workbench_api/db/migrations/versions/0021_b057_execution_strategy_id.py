"""B057 F004 — account_snapshot + order_ticket strategy_id (multi-account exec).

Promotes the execution chain from Master-only to per-strategy-mode real
accounts:

* ``account_snapshot.strategy_id`` (String(64), NOT NULL, server_default
  ``"master_portfolio"``) — every existing Master snapshot is backfilled to the
  flagship id, so the column addition is backward compatible and ``latest()``
  resolves per-mode; index ``(strategy_id, snapshot_at)`` for the lookup.
* ``order_ticket.strategy_id`` (same) — a ticket carries the mode it was
  generated for, so reconcile writes the SAME mode's account and the journal is
  filterable per mode; index ``(strategy_id, ticket_date)``.

The Master execution path (no mode param → ``master_portfolio``) is unchanged.

Revision ID: 0021_b057_execution_strategy_id
Revises: 0020_b057_recommendation_strategy_id
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_b057_execution_strategy_id"
down_revision: str | Sequence[str] | None = "0020_b057_recommendation_strategy_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_STRATEGY_ID = "master_portfolio"
_ACCT_IDX = "ix_account_snapshot_strategy_snapshot_at"
_TICKET_IDX = "ix_order_ticket_strategy_date"


def upgrade() -> None:
    with op.batch_alter_table("account_snapshot", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "strategy_id",
                sa.String(length=64),
                nullable=False,
                server_default=_DEFAULT_STRATEGY_ID,
            )
        )
        batch_op.create_index(_ACCT_IDX, ["strategy_id", "snapshot_at"])
    with op.batch_alter_table("order_ticket", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "strategy_id",
                sa.String(length=64),
                nullable=False,
                server_default=_DEFAULT_STRATEGY_ID,
            )
        )
        batch_op.create_index(_TICKET_IDX, ["strategy_id", "ticket_date"])


def downgrade() -> None:
    with op.batch_alter_table("order_ticket", schema=None) as batch_op:
        batch_op.drop_index(_TICKET_IDX)
        batch_op.drop_column("strategy_id")
    with op.batch_alter_table("account_snapshot", schema=None) as batch_op:
        batch_op.drop_index(_ACCT_IDX)
        batch_op.drop_column("strategy_id")
