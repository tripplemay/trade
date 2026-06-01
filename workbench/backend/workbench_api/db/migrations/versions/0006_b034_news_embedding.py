"""B034 F001 — news_embedding table (one dense vector per news × model).

Adds the ``news_embedding`` table that stores the bge-m3 embedding of
each news row's ``title + summary`` as a JSON list of floats (JSONB on
PostgreSQL via the model's ``with_variant`` decorator). The vector is
the only payload — raw body still lives on disk under
``data/snapshots/news/`` (B033 permanent boundary **(p)**). The unique
constraint ``uq_news_embedding_news_model (news_id, model)`` makes the
repository's ``save_if_new`` idempotent and leaves room to re-embed
under a new model without dropping old vectors.

The ``news_id`` foreign key is ``ON DELETE CASCADE`` so removing a
news row drops its embeddings too. SQLite only enforces this when
``PRAGMA foreign_keys=ON`` is set (the workbench engine enables it),
but the constraint is declared portably for the Postgres path.

Revision ID: 0006_b034_news_embedding
Revises: 0005_b033_news
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_b034_news_embedding"
down_revision: str | Sequence[str] | None = "0005_b033_news"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_embedding",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("news_id", sa.String(length=36), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["news_id"],
            ["news.id"],
            name="fk_news_embedding_news_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "news_id", "model", name="uq_news_embedding_news_model"
        ),
    )
    op.create_index(
        "ix_news_embedding_news_id", "news_embedding", ["news_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_news_embedding_news_id", table_name="news_embedding")
    op.drop_table("news_embedding")
