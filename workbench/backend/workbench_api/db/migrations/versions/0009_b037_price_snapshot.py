"""B037 F001 — price_snapshot table.

Adds the ``price_snapshot`` table storing one daily close per
``(symbol, obs_date)`` for the symbols the research account holds. The
B037 Home page marks the latest ``AccountSnapshot`` positions to market
with these closes (today vs prior trading day) to compute a read-only
Day P&L. A daily ``workbench-prices`` timer fetches the closes through
the B027 Tiingo loader and persists them here so the Home request path
stays self-contained (v0.9.32 §12.10) — it never reads the repo-root
price-bar snapshot files.

The unique constraint ``uq_price_snapshot_symbol_date`` makes the daily
fetch idempotent; ``ix_price_snapshot_symbol`` / ``ix_price_snapshot_obs_date``
back the latest-close + prior-trading-day reads. Mirrors B035 0007.

Revision ID: 0009_b037_price_snapshot
Revises: 0008_b036_advisor
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_b037_price_snapshot"
down_revision: str | Sequence[str] | None = "0008_b036_advisor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", "obs_date", name="uq_price_snapshot_symbol_date"),
    )
    op.create_index("ix_price_snapshot_symbol", "price_snapshot", ["symbol"])
    op.create_index("ix_price_snapshot_obs_date", "price_snapshot", ["obs_date"])


def downgrade() -> None:
    op.drop_index("ix_price_snapshot_obs_date", table_name="price_snapshot")
    op.drop_index("ix_price_snapshot_symbol", table_name="price_snapshot")
    op.drop_table("price_snapshot")
