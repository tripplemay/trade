"""B059 F001 — symbol_price_cache table (on-demand symbol-lookup EOD cache).

Isolated research-only OHLCV cache for the "look up any ticker" surface
(free yfinance EOD feed). Deliberately separate from price_snapshot (B037)
and price_history (B048) so arbitrary-ticker lookups can never perturb the
funded strategies' price math (Master / B058 不破). Mirrors the
``(symbol, obs_date)`` idempotency key + explicit index naming convention,
but carries full OHLCV (candlesticks + true 52-week intraday high/low).

Revision ID: 0024_b059_symbol_price_cache
Revises: 0023_b058_target_refresh_job
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_b059_symbol_price_cache"
down_revision: str | Sequence[str] | None = "0023_b058_target_refresh_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbol_price_cache",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("adj_close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "symbol", "obs_date", name="uq_symbol_price_cache_symbol_date"
        ),
    )
    op.create_index(
        "ix_symbol_price_cache_symbol", "symbol_price_cache", ["symbol"]
    )
    op.create_index(
        "ix_symbol_price_cache_obs_date", "symbol_price_cache", ["obs_date"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_symbol_price_cache_obs_date", table_name="symbol_price_cache"
    )
    op.drop_index(
        "ix_symbol_price_cache_symbol", table_name="symbol_price_cache"
    )
    op.drop_table("symbol_price_cache")
