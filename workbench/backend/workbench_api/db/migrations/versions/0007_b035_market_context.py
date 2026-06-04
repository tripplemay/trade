"""B035 F001 — market_context_observation table.

Adds the ``market_context_observation`` table storing one numeric data
point per ``(series_id, obs_date)`` for the B035 market-context series
(FRED macro + Alpha Vantage indices). Raw provider responses live on
disk under ``data/snapshots/market-context/`` (B027/B029 snapshot
foundation); the row carries only the value + metadata + snapshot_path.

The unique constraint ``uq_market_context_series_date`` makes the daily
fetch idempotent; ``ix_market_context_series`` / ``ix_market_context_obs_date``
back the latest-by-series + history reads.

Revision ID: 0007_b035_market_context
Revises: 0006_b034_news_embedding
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_b035_market_context"
down_revision: str | Sequence[str] | None = "0006_b034_news_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_context_observation",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("series_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("snapshot_path", sa.String(length=512), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "series_id", "obs_date", name="uq_market_context_series_date"
        ),
    )
    op.create_index(
        "ix_market_context_series", "market_context_observation", ["series_id"]
    )
    op.create_index(
        "ix_market_context_obs_date", "market_context_observation", ["obs_date"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_context_obs_date", table_name="market_context_observation"
    )
    op.drop_index(
        "ix_market_context_series", table_name="market_context_observation"
    )
    op.drop_table("market_context_observation")
