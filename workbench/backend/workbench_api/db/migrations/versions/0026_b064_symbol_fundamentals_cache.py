"""B064 F001 — symbol_fundamentals_cache table (on-demand fundamentals cache).

Isolated research-only fundamentals snapshot for the "look up any ticker"
detail page — US (yfinance / US-GAAP) + A-share (akshare / CAS) + Hong Kong
(akshare / HKFRS). Deliberately separate from every trading / risk / scoring
store (mirrors B059 symbol_price_cache): arbitrary-ticker fundamentals are
written on the request path from free feeds and never feed a strategy
(B064 红线). One row per ``symbol`` (latest snapshot, upserted);
``fetched_at`` drives the EOD-day TTL; ``as_of_report`` is the statements'
reporting date and ``accounting_standard`` stamps the口径.

Revision ID: 0026_b064_symbol_fundamentals_cache
Revises: 0025_b061_symbol_cache_market_currency
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_b064_symbol_fundamentals_cache"
down_revision: str | Sequence[str] | None = "0025_b061_symbol_cache_market_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbol_fundamentals_cache",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False, server_default="US"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("accounting_standard", sa.String(length=16), nullable=True),
        sa.Column("long_name", sa.String(length=128), nullable=True),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("industry", sa.String(length=64), nullable=True),
        sa.Column("quote_type", sa.String(length=16), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("as_of_report", sa.Date(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),
        sa.Column("trailing_pe", sa.Numeric(), nullable=True),
        sa.Column("forward_pe", sa.Numeric(), nullable=True),
        sa.Column("price_to_book", sa.Numeric(), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(), nullable=True),
        sa.Column("profit_margins", sa.Numeric(), nullable=True),
        sa.Column("gross_margins", sa.Numeric(), nullable=True),
        sa.Column("revenue", sa.Numeric(), nullable=True),
        sa.Column("shares_outstanding", sa.Numeric(), nullable=True),
        sa.Column("return_on_equity", sa.Numeric(), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(), nullable=True),
        sa.Column("eps", sa.Numeric(), nullable=True),
        sa.Column("book_value_per_share", sa.Numeric(), nullable=True),
        sa.Column("net_income", sa.Numeric(), nullable=True),
        sa.Column("debt_to_asset", sa.Numeric(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", name="uq_symbol_fundamentals_cache_symbol"),
    )
    op.create_index(
        "ix_symbol_fundamentals_cache_symbol",
        "symbol_fundamentals_cache",
        ["symbol"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_symbol_fundamentals_cache_symbol",
        table_name="symbol_fundamentals_cache",
    )
    op.drop_table("symbol_fundamentals_cache")
