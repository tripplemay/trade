"""B048 F001 — price_history table.

Adds the ``price_history`` table storing the **deep** daily close history
(one row per ``(symbol, obs_date)``) the safety / risk layer needs to
reconstruct a mark-to-market NAV time series and compute master +
per-sleeve drawdown over time (B048 F003). A backfill job materialises it
from the B045 unified prices CSV
(``snapshots/prices/unified/prices_daily.csv``).

Distinct from ``price_snapshot`` (B037 / 0009), which stays shallow
(latest + prior close only) for the Home Day P&L. Same column shape +
``(symbol, obs_date)`` idempotency key + two indexes.

Revision ID: 0011_b048_price_history
Revises: 0010_b044_recommendation_snapshot
Create Date: 2026-06-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_b048_price_history"
down_revision: str | Sequence[str] | None = "0010_b044_recommendation_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", "obs_date", name="uq_price_history_symbol_date"),
    )
    op.create_index("ix_price_history_symbol", "price_history", ["symbol"])
    op.create_index("ix_price_history_obs_date", "price_history", ["obs_date"])


def downgrade() -> None:
    op.drop_index("ix_price_history_obs_date", table_name="price_history")
    op.drop_index("ix_price_history_symbol", table_name="price_history")
    op.drop_table("price_history")
