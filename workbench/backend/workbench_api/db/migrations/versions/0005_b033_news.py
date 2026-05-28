"""B033 F001 — news table (metadata + snapshot path).

Adds the ``news`` table that stores SEC EDGAR filings and Yahoo
Finance RSS headlines as metadata only — raw filing / article body
lives on disk under ``data/snapshots/news/{source}/{YYYY-MM-DD}/``
and the row points at the file via ``snapshot_path`` +
``content_sha256``. Permanent product boundary **(p)** keeps the table
metadata-only; the safety guard test
``tests/safety/test_news_schema_metadata_only.py`` blocks any future
``raw_text`` / ``body`` / ``content`` TEXT column.

``ticker_mentions`` is reserved for B034 (Stream 2.B News↔ticker +
Cohere embedding). It is stored as ``JSON`` portably (becomes
``JSONB`` on PostgreSQL via the model's ``with_variant`` decorator)
so a future B034 migration can promote the variant without a data
rewrite — the column already round-trips list / dict values.

Revision ID: 0005_b033_news
Revises: 0004_b031_llm_budget_log
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_b033_news"
down_revision: str | Sequence[str] | None = "0004_b031_llm_budget_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("form_type", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_path", sa.String(length=512), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("ticker_mentions", sa.JSON(), nullable=True),
        sa.UniqueConstraint("source", "source_id", name="uq_news_source_source_id"),
    )
    op.create_index("ix_news_source", "news", ["source"])
    op.create_index("ix_news_ticker", "news", ["ticker"])
    op.create_index("ix_news_published_at", "news", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_news_published_at", table_name="news")
    op.drop_index("ix_news_ticker", table_name="news")
    op.drop_index("ix_news_source", table_name="news")
    op.drop_table("news")
