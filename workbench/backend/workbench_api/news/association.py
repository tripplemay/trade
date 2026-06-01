"""B034 F002 — NewsAssociationService (hard match + cosine soft-rank).

Answers "which recent news affect this sleeve?" by combining the two
B034 association halves (spec §4.4):

* **Hard association** — a news item is relevant to a sleeve when the
  sleeve's constituent tickers intersect the news's tickers (the
  triggering ``News.ticker`` plus any ``ticker_mentions`` the F002
  matcher recorded). This is precise and deterministic.
* **Soft rank** — among the hard-matched news, cosine similarity between
  the news's bge-m3 embedding and the sleeve's query-vector orders the
  most semantically relevant filings first. Pure-Python cosine over the
  small universe (no numpy dependency — B034 spec §4.7).

``score = (number of matched tickers) + cosine``: the hard match count
dominates, cosine breaks ties / orders within a match level, so a news
mentioning two sleeve tickers always outranks one mentioning a single
ticker, and within a tier the semantically-closest comes first.

The service is read-only over the ``news`` + ``news_embedding`` tables.
The sleeve query vector is supplied by an injectable provider so the
offline test path passes recorded fixture vectors and production passes
a gateway-backed embedder — the service never calls the gateway itself.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.news import News
from workbench_api.db.repositories.news_embedding import NewsEmbeddingRepository
from workbench_api.news.embedder import DEFAULT_EMBED_MODEL
from workbench_api.news.sleeve_tickers import tickers_for_sleeve
from workbench_api.news.topics import tag_topics

# Upper bound on candidate news scanned before ranking. The B034 news
# universe is small (31 tickers, manual ingest), so this is generous;
# it caps the in-Python hard-match scan so a future runaway corpus
# can't load unbounded rows. ``limit`` then truncates the ranked output.
_CANDIDATE_CAP = 1000

SleeveQueryProvider = Callable[[str], list[float] | None]
"""``sleeve -> query vector | None``. ``None`` means "no semantic
vector available" → cosine contributes 0 and ordering falls back to
match-count then recency."""


@dataclass(frozen=True, slots=True)
class SleeveNewsRelevance:
    """One sleeve-relevant news item with its association metadata.

    F003 maps this to the ``SleeveNewsItem`` pydantic response model;
    keeping it a plain frozen dataclass keeps the service free of the
    HTTP-schema dependency."""

    news_id: UUID
    title: str
    source: str
    url: str
    published_at: datetime
    content_sha256: str
    topics: list[str]
    matched_tickers: list[str]
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity; ``0.0`` for empty / mismatched /
    zero-magnitude vectors (so a missing embedding never blows up the
    ranker)."""

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _news_tickers(news: News) -> set[str]:
    """All tickers associated with a news row: the triggering ticker plus
    any recorded mentions, upper-cased."""

    tickers: set[str] = set()
    if news.ticker:
        tickers.add(news.ticker.upper())
    for mention in news.ticker_mentions or []:
        if isinstance(mention, str):
            tickers.add(mention.upper())
    return tickers


class NewsAssociationService:
    def __init__(
        self,
        session: Session,
        *,
        model: str = DEFAULT_EMBED_MODEL,
        sleeve_query_provider: SleeveQueryProvider | None = None,
    ) -> None:
        self._session = session
        self._emb_repo = NewsEmbeddingRepository(session)
        self._model = model
        self._sleeve_query_provider = sleeve_query_provider

    def news_for_sleeve(
        self,
        sleeve: str,
        *,
        limit: int = 20,
        since: datetime | None = None,
        topic: str | None = None,
        source: str | None = None,
        form_type: str | None = None,
    ) -> list[SleeveNewsRelevance]:
        """Return the sleeve-relevant news, most relevant first.

        Empty when the sleeve has no news-universe constituents (unknown
        sleeve, or a sleeve whose instruments the news CLI doesn't
        ingest). ``topic`` filters on the deterministic topic tags;
        ``source`` / ``form_type`` / ``since`` filter at the SQL level."""

        sleeve_tickers = {t.upper() for t in tickers_for_sleeve(sleeve)}
        if not sleeve_tickers:
            return []

        candidates = self._candidate_news(
            since=since, source=source, form_type=form_type
        )

        # Hard match first so we only embed-rank the relevant subset.
        matched: list[tuple[News, list[str], list[str]]] = []
        for news in candidates:
            hits = sorted(_news_tickers(news) & sleeve_tickers)
            if not hits:
                continue
            topics = tag_topics(news)
            if topic is not None and topic not in topics:
                continue
            matched.append((news, hits, topics))

        query_vector = self._resolve_sleeve_query(sleeve)
        vectors = self._emb_repo.list_vectors_by_news_ids(
            [news.id for news, _, _ in matched], self._model
        )

        results = [
            SleeveNewsRelevance(
                news_id=news.id,
                title=news.title,
                source=news.source,
                url=news.url,
                published_at=news.published_at,
                content_sha256=news.content_sha256,
                topics=topics,
                matched_tickers=hits,
                score=round(
                    len(hits)
                    + self._cosine_for(news.id, vectors, query_vector),
                    6,
                ),
            )
            for news, hits, topics in matched
        ]

        # Highest score first; ties broken by recency (newest first).
        results.sort(key=lambda r: (r.score, r.published_at), reverse=True)
        return results[:limit]

    # --- internals --------------------------------------------------------

    def _candidate_news(
        self,
        *,
        since: datetime | None,
        source: str | None,
        form_type: str | None,
    ) -> list[News]:
        stmt = select(News)
        if since is not None:
            stmt = stmt.where(News.published_at >= since)
        if source is not None:
            stmt = stmt.where(News.source == source)
        if form_type is not None:
            stmt = stmt.where(News.form_type == form_type)
        stmt = stmt.order_by(News.published_at.desc()).limit(_CANDIDATE_CAP)
        return list(self._session.execute(stmt).scalars().all())

    def _resolve_sleeve_query(self, sleeve: str) -> list[float] | None:
        if self._sleeve_query_provider is None:
            return None
        return self._sleeve_query_provider(sleeve)

    def _cosine_for(
        self,
        news_id: UUID,
        vectors: dict[UUID, list[float]],
        query_vector: list[float] | None,
    ) -> float:
        if query_vector is None:
            return 0.0
        news_vector = vectors.get(news_id)
        if news_vector is None:
            return 0.0
        return cosine_similarity(news_vector, query_vector)
