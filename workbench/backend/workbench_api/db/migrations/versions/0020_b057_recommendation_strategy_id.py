"""B057 F001 — recommendation_snapshot.strategy_id (generic target layer).

Promotes ``recommendation_snapshot`` from Master-only to per-strategy-mode:

* adds ``strategy_id`` (String(64), NOT NULL, server_default ``"master_portfolio"``)
  so every existing Master row is backfilled to the flagship id and the column
  addition is backward compatible;
* swaps the unique constraint from ``(as_of_date, symbol)`` to
  ``(as_of_date, symbol, strategy_id)`` so multiple modes share the table
  without colliding on the same date;
* adds an index on ``(strategy_id, as_of_date)`` for the generic target
  layer's per-strategy latest-snapshot lookup.

The Master read/write path is unchanged (it keeps writing/reading the
``master_portfolio`` rows); the regime precompute writes ``regime_adaptive``
rows into the same table.

Revision ID: 0020_b057_recommendation_strategy_id
Revises: 0019_b056_paper_nav_history
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_b057_recommendation_strategy_id"
down_revision: str | Sequence[str] | None = "0019_b056_paper_nav_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "recommendation_snapshot"
_OLD_UQ = "uq_recommendation_snapshot_date_symbol"
_NEW_UQ = "uq_recommendation_snapshot_date_symbol_strategy"
_STRATEGY_IDX = "ix_recommendation_snapshot_strategy_as_of"
_DEFAULT_STRATEGY_ID = "master_portfolio"


def upgrade() -> None:
    # Batch mode: SQLite cannot ALTER a constraint in place (copy-and-move
    # recreation), and it is a no-op wrapper on PostgreSQL — so the same
    # migration runs on the test SQLite and prod Postgres.
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "strategy_id",
                sa.String(length=64),
                nullable=False,
                server_default=_DEFAULT_STRATEGY_ID,
            )
        )
        batch_op.drop_constraint(_OLD_UQ, type_="unique")
        batch_op.create_unique_constraint(
            _NEW_UQ, ["as_of_date", "symbol", "strategy_id"]
        )
        batch_op.create_index(_STRATEGY_IDX, ["strategy_id", "as_of_date"])


def downgrade() -> None:
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.drop_index(_STRATEGY_IDX)
        batch_op.drop_constraint(_NEW_UQ, type_="unique")
        batch_op.create_unique_constraint(_OLD_UQ, ["as_of_date", "symbol"])
        batch_op.drop_column("strategy_id")
