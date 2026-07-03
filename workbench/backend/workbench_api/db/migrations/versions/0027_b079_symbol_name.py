"""B079 F001 — symbol_name table (lightweight symbol → display-name store).

One row per canonical ``symbol`` mapping a ticker to its human-readable display
name + the feed that supplied it (``curated`` static seed / ``akshare_spot``
live A-share capture). Minimal, isolated (mirrors symbol_price_cache /
symbol_fundamentals_cache): written by the data-refresh job + an idempotent
seed, never read by a strategy. ``symbol`` is the natural PK (unique + indexed);
``updated_at`` is stamped in Python on upsert.

Revision ID: 0027_b079_symbol_name
Revises: 0026_b064_symbol_fundamentals_cache
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_b079_symbol_name"
down_revision: str | Sequence[str] | None = "0026_b064_symbol_fundamentals_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbol_name",
        sa.Column("symbol", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("symbol_name")
