"""B034 F001 — NewsEmbedder.

Turns :class:`~workbench_api.db.models.news.News` rows into dense
vectors via the LLM gateway's embedding model (bge-m3, dim=1024) and
persists them through :class:`NewsEmbeddingRepository`. This is the
project's **first** AI-boundary touch (B034 spec §3) but a strictly
**non-generative** one: the embedder calls ``gateway.embed`` only,
never the gateway's chat-completion path, so it produces vectors —
never user-facing AI text. The guard test
``tests/safety/test_b034_no_generative_ai.py`` enforces that.

The embed text is ``title + ' ' + (summary or '')`` — the same
metadata the News table already holds. Raw filing / article body is
never read here (it lives on disk; B033 boundary **(p)**), so the
embedder needs no filesystem access.

Offline by default: production runs the gateway, but CI injects a
recorded-vector / stub gateway (fixture
``data/fixtures/news/embeddings-bge-m3-sample.json``) so the test path
never bills a real embedding call. ``embed_pending`` is idempotent —
news that already have a vector under ``model`` are skipped — so a
re-run after ingesting more news only embeds the new rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from workbench_api.db.models.news import News
from workbench_api.db.repositories.news_embedding import NewsEmbeddingRepository

DEFAULT_EMBED_MODEL = "bge-m3"
"""The only multilingual embedding model the aigc-gateway exposes
(``llm/routing.py`` task ``"embedding"`` → bge-m3). Pinned here as the
default so callers never hardcode a model name elsewhere — permanent
boundary **(l)**. Live-validated dim=1024 against the production
gateway (B034 F001, see ``tests/unit/test_news_embedder.py``)."""


class _EmbeddingGateway(Protocol):
    """Subset of :class:`~workbench_api.llm.gateway.LLMGateway` the
    embedder uses.

    Declared as a Protocol so unit tests inject a hand-rolled fake
    that returns recorded vectors without standing up the HTTP client
    or the cost-guard DB. The fake exposes **only** ``embed`` —
    deliberately not the chat-completion method — so a test that
    accidentally wires a generative call would fail to type-check /
    attribute-error, reinforcing the non-generative boundary at the seam.
    """

    def embed(self, texts: list[str], task: str = ...) -> list[list[float]]: ...


def embed_text_for(news: News) -> str:
    """Build the text fed to the embedding model for one news row.

    ``title + ' ' + summary`` — summary is optional (Yahoo RSS items
    and bare filings may lack one), so an absent summary collapses to
    just the title rather than a trailing space.
    """

    summary = (news.summary or "").strip()
    title = news.title.strip()
    return f"{title} {summary}".strip()


class NewsEmbedder:
    """Embed news rows and persist the vectors idempotently."""

    def __init__(
        self,
        gateway: _EmbeddingGateway,
        repo: NewsEmbeddingRepository,
    ) -> None:
        self._gateway = gateway
        self._repo = repo

    def embed_pending(
        self,
        news: Sequence[News],
        *,
        model: str = DEFAULT_EMBED_MODEL,
    ) -> int:
        """Embed every news row in ``news`` that lacks a vector under
        ``model``; return the number newly persisted.

        News that already have a stored vector are filtered out before
        the gateway call, so a re-run embeds only the new rows and
        spends nothing on the rest. When everything is already embedded
        the gateway is not called at all.
        """

        pending = [
            row
            for row in news
            if self._repo.get_by_news_and_model(row.id, model) is None
        ]
        if not pending:
            return 0

        texts = [embed_text_for(row) for row in pending]
        vectors = self._gateway.embed(texts, task="embedding")
        if len(vectors) != len(pending):
            raise ValueError(
                "embedding count mismatch: gateway returned "
                f"{len(vectors)} vectors for {len(pending)} news items"
            )

        saved = 0
        for row, vector in zip(pending, vectors, strict=True):
            if self._repo.save_if_new(
                news_id=row.id, model=model, vector=vector
            ) is not None:
                saved += 1
        return saved
