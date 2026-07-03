"""B080 F002 — monitoring_metric table (L0 strategy-lifecycle metrics store).

One row per ``(strategy_id, as_of, metric)`` written by the weekly monitoring
timer; read-only on the request path. Structural only — the timer/CLI upserts.

Revision ID: 0030_b080_monitoring_metric
Revises: 0029_b080_trial_registry
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_b080_monitoring_metric"
down_revision: str | Sequence[str] | None = "0029_b080_trial_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_metric",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "strategy_id",
            "as_of",
            "metric",
            name="uq_monitoring_metric_strategy_as_of_metric",
        ),
    )
    op.create_index(
        "ix_monitoring_metric_strategy_as_of",
        "monitoring_metric",
        ["strategy_id", "as_of"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monitoring_metric_strategy_as_of", table_name="monitoring_metric"
    )
    op.drop_table("monitoring_metric")
