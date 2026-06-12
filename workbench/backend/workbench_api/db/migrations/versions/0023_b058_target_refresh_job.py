"""B058 F003 — target_refresh_job table (manual target-refresh queue + result).

The generic "refresh this mode's target on demand" primitive. The request path
enqueues a ``queued`` row (no ``trade`` import, §12.10.2); the worker daemon runs
the mode's target producer off-path and records the terminal state here. Lets the
regime mode generate its target immediately instead of waiting for the monthly
timer (S1 fix), and Master / future modes reuse the same flow.

Revision ID: 0023_b058_target_refresh_job
Revises: 0022_b058_paper_build_complete
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_b058_target_refresh_job"
down_revision: str | Sequence[str] | None = "0022_b058_paper_build_complete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "target_refresh_job",
        sa.Column("job_id", sa.String(length=40), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.String(length=10), nullable=True),
        sa.Column("saved_count", sa.Integer(), nullable=True),
        sa.Column("data_source", sa.String(length=16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_kind", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_target_refresh_job_status_created",
        "target_refresh_job",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_target_refresh_job_strategy_status",
        "target_refresh_job",
        ["strategy_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_target_refresh_job_strategy_status", table_name="target_refresh_job")
    op.drop_index("ix_target_refresh_job_status_created", table_name="target_refresh_job")
    op.drop_table("target_refresh_job")
