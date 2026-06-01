"""B034 F001 — NewsEmbedder (offline, fake gateway) + bge-m3 dim lock.

The embedder is the project's first AI-boundary touch but a strictly
non-generative one: it calls ``gateway.embed`` only. These tests inject
a fake gateway that exposes **only** ``embed`` (no chat-completion
method), so a future regression that wired a generative call would
break here as well as in ``tests/safety/test_b034_no_generative_ai.py``.

``test_bge_m3_dim_is_locked`` records the live-validation result: the
production aigc-gateway bge-m3 model returns dim=1024 vectors
(validated 2026-06-01 via the ``GET /v1/embeddings`` envelope). The
fixture is dimensioned to match.

All sessions opened here are closed before per-test teardown so the
SQLite file DB is never locked when ``initialised_db`` drops the schema.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.db.repositories.news_embedding import NewsEmbeddingRepository
from workbench_api.llm.routing import route_task
from workbench_api.news.adapters.base import NewsItem
from workbench_api.news.embedder import (
    DEFAULT_EMBED_MODEL,
    NewsEmbedder,
    embed_text_for,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "fixtures"
    / "news"
    / "embeddings-bge-m3-sample.json"
)
BGE_M3_DIM = 1024


class _FakeEmbeddingGateway:
    """Records the texts it was asked to embed and returns canned vectors.

    Deliberately exposes only ``embed`` so the non-generative boundary is
    structural, not just a convention."""

    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str], task: str = "embedding") -> list[list[float]]:
        assert task == "embedding"
        self.calls.append(list(texts))
        return self._vectors[: len(texts)]


def _news_item(source_id: str, *, summary: str | None = "summary") -> NewsItem:
    return NewsItem(
        source="sec_edgar",
        source_id=source_id,
        url="https://www.sec.gov/x",
        title=f"Headline {source_id}",
        summary=summary,
        ticker="AAPL",
        form_type="10-K",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        raw_body=b"<html></html>",
        raw_ext="htm",
    )


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    news_repo = NewsRepository(session)
    rows = []
    for i in range(2):
        row = news_repo.save_if_new(
            _news_item(f"acc-{i}"),
            snapshot_path=f"sec_edgar/2026-05-01/acc-{i}.htm",
            content_sha256=f"{i:02d}" * 32,
        )
        assert row is not None
        rows.append(row)
    session.commit()
    yield SimpleNamespace(
        rows=rows, session=session, repo=NewsEmbeddingRepository(session)
    )
    session.close()


def test_embed_text_for_combines_title_and_summary() -> None:
    news = News(title="Headline x", summary="Annual report")
    assert embed_text_for(news) == "Headline x Annual report"


def test_embed_text_for_handles_missing_summary() -> None:
    news = News(title="Headline x", summary=None)
    assert embed_text_for(news) == "Headline x"


def test_embed_pending_persists_vectors(ctx: SimpleNamespace) -> None:
    gateway = _FakeEmbeddingGateway([[1.0, 0.0], [0.0, 1.0]])
    embedder = NewsEmbedder(gateway, ctx.repo)

    saved = embedder.embed_pending(ctx.rows)
    assert saved == 2
    assert ctx.repo.count() == 2
    # One batched gateway call carrying both news texts.
    assert len(gateway.calls) == 1
    assert gateway.calls[0] == ["Headline acc-0 summary", "Headline acc-1 summary"]


def test_embed_pending_skips_already_embedded(ctx: SimpleNamespace) -> None:
    # Pre-embed the first row.
    ctx.repo.save_if_new(news_id=ctx.rows[0].id, model=DEFAULT_EMBED_MODEL, vector=[9.0])

    gateway = _FakeEmbeddingGateway([[0.0, 1.0]])
    saved = NewsEmbedder(gateway, ctx.repo).embed_pending(ctx.rows)

    assert saved == 1
    # Only the un-embedded row's text reached the gateway.
    assert gateway.calls == [["Headline acc-1 summary"]]
    assert ctx.repo.count() == 2


def test_embed_pending_no_pending_does_not_call_gateway(ctx: SimpleNamespace) -> None:
    for row in ctx.rows:
        ctx.repo.save_if_new(news_id=row.id, model=DEFAULT_EMBED_MODEL, vector=[1.0])

    gateway = _FakeEmbeddingGateway([])
    saved = NewsEmbedder(gateway, ctx.repo).embed_pending(ctx.rows)

    assert saved == 0
    assert gateway.calls == []  # gateway never invoked → no billing


def test_embed_pending_count_mismatch_raises(ctx: SimpleNamespace) -> None:
    # Gateway returns fewer vectors than texts → fail loud, persist nothing.
    gateway = _FakeEmbeddingGateway([[1.0, 0.0]])
    embedder = NewsEmbedder(gateway, ctx.repo)
    with pytest.raises(ValueError, match="embedding count mismatch"):
        embedder.embed_pending(ctx.rows)


def test_default_model_is_bge_m3_and_routes_there() -> None:
    """Permanent boundary (l): the embedder's default model name matches
    the routing table's ``embedding`` task → bge-m3."""

    assert DEFAULT_EMBED_MODEL == "bge-m3"
    assert route_task("embedding") == "bge-m3"


def test_bge_m3_dim_is_locked() -> None:
    """Lock the live-validated bge-m3 dimension (=1024). The fixture
    vectors and their declared ``dim`` must match, so a future fixture
    regeneration or model swap that changes the dimension fails here."""

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["model"] == "bge-m3"
    assert fixture["dim"] == BGE_M3_DIM
    all_vectors = list(fixture["news"].values()) + list(
        fixture["sleeve_queries"].values()
    )
    assert all_vectors, "fixture must carry at least one vector"
    for vec in all_vectors:
        assert len(vec) == BGE_M3_DIM


def test_embed_pending_dim_matches_fixture_vectors(ctx: SimpleNamespace) -> None:
    """End-to-end: embedding a news with a 1024-dim vector stores
    ``dim == 1024`` — the embedder derives dim from the vector length, so
    the stored shape always agrees with the live model's output."""

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    sample_vec = next(iter(fixture["news"].values()))
    gateway = _FakeEmbeddingGateway([sample_vec])
    NewsEmbedder(gateway, ctx.repo).embed_pending([ctx.rows[0]])
    stored = ctx.repo.get_by_news_and_model(ctx.rows[0].id, DEFAULT_EMBED_MODEL)
    assert stored is not None
    assert stored.dim == BGE_M3_DIM
