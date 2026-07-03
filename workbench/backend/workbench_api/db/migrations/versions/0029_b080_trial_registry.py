"""B080 F001 — trial_registry table (structured backtest-trial log for DSR N).

Structural only: the historical B063–B077 backfill is seeded idempotently by
``workbench-bootstrap`` (from the in-code HISTORICAL_TRIALS constant), and the
B050 worker auto-registers new rows — neither belongs in a migration.

Revision ID: 0029_b080_trial_registry
Revises: 0028_b080_oos_verification_card
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_b080_trial_registry"
down_revision: str | Sequence[str] | None = "0028_b080_oos_verification_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trial_registry",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("batch", sa.String(length=32), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("parameter_hash", sa.String(length=64), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("universe", sa.String(length=256), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("oos_split", sa.String(length=256), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=256), nullable=False),
        sa.Column("notes", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "ix_trial_registry_strategy_id", "trial_registry", ["strategy_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_trial_registry_strategy_id", table_name="trial_registry")
    op.drop_table("trial_registry")
