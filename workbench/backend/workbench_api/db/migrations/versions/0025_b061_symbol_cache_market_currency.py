"""B061 F002 — symbol_price_cache market + currency columns.

Adds the market dimension (``US`` / ``CN``) + display currency (``USD`` /
``CNY``) to the isolated symbol-lookup price cache so A-share rows co-exist
with US rows in the same table (path-doc §9.5). Both columns carry a server
default (``US`` / ``USD``) so the existing US rows backfill correctly and any
caller that omits them stays backward-compatible. The market dimension is
derivable from the canonical symbol (SymbolRef) — these columns are stored for
query efficiency + explicit provenance, not as a new identity key.

Revision ID: 0025_b061_symbol_cache_market_currency
Revises: 0024_b059_symbol_price_cache
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_b061_symbol_cache_market_currency"
down_revision: str | Sequence[str] | None = "0024_b059_symbol_price_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "symbol_price_cache",
        sa.Column("market", sa.String(length=8), nullable=False, server_default="US"),
    )
    op.add_column(
        "symbol_price_cache",
        sa.Column(
            "currency", sa.String(length=8), nullable=False, server_default="USD"
        ),
    )


def downgrade() -> None:
    op.drop_column("symbol_price_cache", "currency")
    op.drop_column("symbol_price_cache", "market")
