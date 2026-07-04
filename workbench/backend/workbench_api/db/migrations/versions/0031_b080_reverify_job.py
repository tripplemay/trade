"""B080 F003 — reverify_job table (frozen re-validation async job status).

Structural only: the request-path enqueues + the reverify worker claims/updates.

Revision ID: 0031_b080_reverify_job
Revises: 0030_b080_monitoring_metric
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_b080_reverify_job"
down_revision: str | Sequence[str] | None = "0030_b080_monitoring_metric"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reverify_job",
        sa.Column("job_id", sa.String(length=40), primary_key=True, nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("as_of", sa.String(length=10), nullable=True),
        sa.Column("report_ref", sa.String(length=256), nullable=True),
        sa.Column("verdict", sa.String(length=16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_kind", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_reverify_job_status_created", "reverify_job", ["status", "created_at"]
    )
    op.create_index(
        "ix_reverify_job_strategy_status", "reverify_job", ["strategy_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_reverify_job_strategy_status", table_name="reverify_job")
    op.drop_index("ix_reverify_job_status_created", table_name="reverify_job")
    op.drop_table("reverify_job")
