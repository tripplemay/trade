"""B044 F002 — recommendation_snapshot table.

Adds the ``recommendation_snapshot`` table storing one precomputed Master
Portfolio target-weight row per ``(as_of_date, symbol)``. The daily
``workbench-recommendations`` timer imports the ``trade`` package, runs the
real Master Portfolio scoring "as of today", and persists the resulting
per-symbol target weights here (with run-level ``master_meta`` JSON carrying
the sleeve planning weights + a ``data_source`` real/fixture marker). The
``GET /api/recommendations/current`` request path reads the latest as_of_date
from this table — it never imports ``trade`` (v0.9.32 §12.10, AST guard).

The unique constraint ``uq_recommendation_snapshot_date_symbol`` makes the
daily precompute idempotent (save_batch overwrites a date); the
``ix_recommendation_snapshot_as_of_date`` index backs the latest-snapshot read.
Mirrors B037 0009 / B035 0007.

Revision ID: 0010_b044_recommendation_snapshot
Revises: 0009_b037_price_snapshot
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_b044_recommendation_snapshot"
down_revision: str | Sequence[str] | None = "0009_b037_price_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("sleeve", sa.String(length=64), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("master_meta", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "as_of_date", "symbol", name="uq_recommendation_snapshot_date_symbol"
        ),
    )
    op.create_index(
        "ix_recommendation_snapshot_as_of_date",
        "recommendation_snapshot",
        ["as_of_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_snapshot_as_of_date", table_name="recommendation_snapshot"
    )
    op.drop_table("recommendation_snapshot")
