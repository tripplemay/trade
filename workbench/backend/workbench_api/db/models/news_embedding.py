"""B034 F001 — news_embedding table (one vector per news × model).

Stores the dense embedding of a :class:`~workbench_api.db.models.news.News`
row produced by the LLM gateway's embedding model (bge-m3, dim=1024).
The vector is the **only** payload — raw filing / article body never
lands here, so the B033 permanent product boundary **(p)**
(metadata-only News table + on-disk snapshots) is preserved. The
guard test ``tests/safety/test_news_schema_metadata_only.py`` greps
this table to make sure ``vector`` stays a numeric ``JSON`` column and
no ``raw_text`` / ``body`` / ``content`` TEXT column sneaks in.

One row per ``(news_id, model)`` — the unique constraint
``uq_news_embedding_news_model`` lets
:meth:`~workbench_api.db.repositories.news_embedding.NewsEmbeddingRepository.save_if_new`
de-duplicate idempotently, so re-running the embedder over the same
news with the same model is a no-op rather than a duplicate insert.
Keeping ``model`` in the key also leaves room to re-embed under a new
model (e.g. a future bge-m3 upgrade) without dropping the old vectors.

Vector storage is ``JSON().with_variant(JSONB, 'postgresql')`` — the
production DB is SQLite (permanent boundary forbids Cloud SQL /
pgvector), so cosine similarity runs in application code over the
small universe (B034 spec §2 decision 2). The portable variant means
a future Postgres deployment stores JSONB without a data rewrite.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class NewsEmbedding(Base):
    __tablename__ = "news_embedding"
    __table_args__ = (
        UniqueConstraint("news_id", "model", name="uq_news_embedding_news_model"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    news_id: Mapped[UUID] = mapped_column(
        _UuidString(),
        ForeignKey("news.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list[float]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"NewsEmbedding(id={self.id!r}, news_id={self.news_id!r}, "
            f"model={self.model!r}, dim={self.dim!r})"
        )
