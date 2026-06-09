"""B043 F003 — risk_explanation_snapshot table.

One row per ``as_of_date`` with the grounded LLM "why" for the current risk
state, written by the daily risk-explanation precompute job (off the request
path) and read-only by the risk panel. ``explanation`` is nullable (a refused /
over-budget / LLM-down run still records the row).

Revision ID: 0016_b043_risk_explanation_snapshot
Revises: 0015_b043_backtest_run_explanation
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_b043_risk_explanation_snapshot"
down_revision: str | Sequence[str] | None = "0015_b043_backtest_run_explanation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_explanation_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("master_dd", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("as_of_date", name="uq_risk_explanation_snapshot_as_of_date"),
    )


def downgrade() -> None:
    op.drop_table("risk_explanation_snapshot")
