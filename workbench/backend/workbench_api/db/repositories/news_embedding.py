"""B034 F001 — NewsEmbeddingRepository.

Wraps the ``news_embedding`` table with the three operations the F001
embedder and the F002 association service need:

- :meth:`save_if_new` — idempotent insert by ``(news_id, model)``;
  returns ``None`` when a vector for that pair already exists. The
  embedder re-runs over the whole news corpus on demand, so this keeps
  a re-run a no-op rather than a duplicate insert.
- :meth:`get_by_news_and_model` — direct lookup used by
  :meth:`save_if_new` and by callers that want "do we already have a
  vector for this news under this model?" without inserting.
- :meth:`list_vectors_by_news_ids` — bulk fetch of ``{news_id: vector}``
  for a batch of news so the F002 cosine ranker can score many news
  against one sleeve query vector in a single round trip.

The repository never calls the gateway — :class:`NewsEmbedder` owns
that and hands the resulting vector in. That split keeps each layer
single-purpose and lets a test exercise the repo against in-memory
SQLite without any network.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.news_embedding import NewsEmbedding
from workbench_api.db.repositories.base import Repository


class NewsEmbeddingRepository(Repository[NewsEmbedding, UUID]):
    model = NewsEmbedding
    primary_key_attr = "id"

    def get_by_news_and_model(
        self, news_id: UUID, model: str
    ) -> NewsEmbedding | None:
        stmt = select(NewsEmbedding).where(
            NewsEmbedding.news_id == news_id,
            NewsEmbedding.model == model,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save_if_new(
        self,
        *,
        news_id: UUID,
        model: str,
        vector: list[float],
        created_at: datetime | None = None,
    ) -> NewsEmbedding | None:
        """Insert a vector if absent; return ``None`` if a row with the
        same ``(news_id, model)`` already exists.

        ``dim`` is derived from ``len(vector)`` so the column can never
        drift from the payload it describes. ``created_at`` defaults to
        ``datetime.now(timezone.utc)`` and is overridable so tests pin
        a deterministic timestamp.
        """

        if self.get_by_news_and_model(news_id, model) is not None:
            return None
        row = NewsEmbedding(
            id=uuid4(),
            news_id=news_id,
            model=model,
            dim=len(vector),
            vector=list(vector),
            created_at=created_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_vectors_by_news_ids(
        self, news_ids: Sequence[UUID], model: str
    ) -> dict[UUID, list[float]]:
        """Return ``{news_id: vector}`` for the supplied ids under ``model``.

        News ids with no stored vector are simply absent from the
        returned mapping — the caller decides whether a missing vector
        means "skip" (cosine soft-rank) or "embed first". An empty
        ``news_ids`` short-circuits to an empty dict without a query.
        """

        if not news_ids:
            return {}
        stmt = select(NewsEmbedding).where(
            NewsEmbedding.news_id.in_(list(news_ids)),
            NewsEmbedding.model == model,
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.news_id: list(row.vector) for row in rows}
