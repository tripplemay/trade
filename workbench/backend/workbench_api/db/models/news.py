"""B033 F001 — news table (metadata + snapshot path).

One row per ingested news / filing item. Raw filing or article body
**never** lives in the DB — it lands on disk under
``data/snapshots/news/{source}/{YYYY-MM-DD}/`` and the row points at
that file via ``snapshot_path`` + ``content_sha256``. This is permanent
product boundary **(p)** in ``framework/proposed-learnings.md``; the
guard test ``tests/safety/test_news_schema_metadata_only.py`` greps
this table's columns to make sure no future ``raw_text`` / ``body`` /
``content`` TEXT column sneaks back in.

The unique key is ``(source, source_id)`` so ``NewsRepository.save_if_new``
can de-duplicate idempotently — the same SEC EDGAR accession number
or Yahoo RSS GUID is never persisted twice.

``ticker_mentions`` is reserved for B034 (Stream 2.B News↔ticker +
Cohere embedding); this batch always writes it as ``NULL``. The
single primary ``ticker`` column is populated by adapters that already
know which symbol triggered the fetch.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from workbench_api.db.models.base import Base


class _UuidString(TypeDecorator[UUID]):
    """Portable UUID column — text in SQLite, native ``uuid`` on PostgreSQL.

    SQLAlchemy 2.0 ships a ``Uuid`` type but the project's tests run on
    SQLite and SQLite stores UUIDs as 36-character text strings by default.
    Round-tripping through this decorator keeps the Python attribute typed
    as :class:`uuid.UUID` regardless of dialect.
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: UUID | str | None, dialect: Any) -> str | None:  # noqa: ARG002
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        return str(UUID(value))

    def process_result_value(self, value: str | None, dialect: Any) -> UUID | None:  # noqa: ARG002
        if value is None:
            return None
        return UUID(value)


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_news_source_source_id"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    form_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ticker_mentions: Mapped[list[Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"News(id={self.id!r}, source={self.source!r}, "
            f"source_id={self.source_id!r}, ticker={self.ticker!r})"
        )
