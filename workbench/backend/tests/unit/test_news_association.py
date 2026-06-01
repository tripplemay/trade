"""B034 F002 — NewsAssociationService hard match + cosine soft-rank.

Uses the offline embedding fixture so cosine ordering is reproducible.
Seeds ``news`` + ``news_embedding`` rows directly (one shared session,
closed before teardown so the SQLite file is never locked).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.db.repositories.news_embedding import NewsEmbeddingRepository
from workbench_api.news.association import (
    NewsAssociationService,
    cosine_similarity,
)

FIXTURE = json.loads(
    (
        Path(__file__).resolve().parents[4]
        / "data"
        / "fixtures"
        / "news"
        / "embeddings-bge-m3-sample.json"
    ).read_text(encoding="utf-8")
)
# Fixture news ids → the ticker each row represents (see generator).
AAPL_VEC = FIXTURE["news"]["0000320193-26-000001"]
MSFT_VEC = FIXTURE["news"]["0000789019-26-000045"]
NVDA_VEC = FIXTURE["news"]["0001045810-26-000012"]
TECH_QUERY = FIXTURE["sleeve_queries"]["us_quality_tech"]


def _tech_query_provider(sleeve: str) -> list[float] | None:
    return TECH_QUERY if sleeve == "satellite_us_quality" else None


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    emb_repo = NewsEmbeddingRepository(session)

    def add_news(
        *,
        ticker: str | None,
        title: str = "Headline",
        summary: str | None = None,
        form_type: str | None = None,
        source: str = "sec_edgar",
        published_at: datetime | None = None,
        ticker_mentions: list[str] | None = None,
        vector: list[float] | None = None,
    ) -> News:
        row = News(
            id=uuid4(),
            source=source,
            source_id=str(uuid4()),
            url="https://www.sec.gov/x",
            title=title,
            summary=summary,
            ticker=ticker,
            form_type=form_type,
            published_at=published_at or datetime(2026, 5, 1, tzinfo=UTC),
            fetched_at=datetime(2026, 5, 1, tzinfo=UTC),
            snapshot_path="sec_edgar/2026-05-01/x",
            content_sha256="aa" * 32,
            ticker_mentions=ticker_mentions,
        )
        session.add(row)
        session.flush()
        if vector is not None:
            emb_repo.save_if_new(news_id=row.id, model="bge-m3", vector=vector)
        return row

    session_ns = SimpleNamespace(session=session, add_news=add_news, factory=factory)
    yield session_ns
    session.close()


def _svc(ctx: SimpleNamespace) -> NewsAssociationService:
    return NewsAssociationService(
        ctx.session, sleeve_query_provider=_tech_query_provider
    )


# --- cosine_similarity unit ----------------------------------------------


def test_cosine_identical_orthogonal_and_degenerate() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0  # length mismatch


# --- hard match -----------------------------------------------------------


def test_empty_for_unknown_sleeve(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="AAPL")
    assert _svc(ctx).news_for_sleeve("no_such_sleeve") == []


def test_hard_match_only_intersecting_tickers(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="AAPL", title="Apple news")
    ctx.add_news(ticker="TSLA", title="Tesla news")  # not in universe
    out = _svc(ctx).news_for_sleeve("satellite_us_quality")
    assert [r.title for r in out] == ["Apple news"]
    assert out[0].matched_tickers == ["AAPL"]


def test_hard_match_via_ticker_mentions(ctx: SimpleNamespace) -> None:
    """A news with no primary ticker but a recorded mention still matches."""

    ctx.add_news(ticker=None, ticker_mentions=["AAPL"], title="Mentions Apple")
    out = _svc(ctx).news_for_sleeve("satellite_us_quality")
    assert [r.title for r in out] == ["Mentions Apple"]
    assert out[0].matched_tickers == ["AAPL"]


def test_master_sleeve_matches_etfs(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="SPY", title="SPY flows")
    ctx.add_news(ticker="AAPL", title="Apple news")
    out = NewsAssociationService(ctx.session).news_for_sleeve("master")
    assert [r.title for r in out] == ["SPY flows"]


# --- cosine soft-rank -----------------------------------------------------


def test_cosine_orders_within_match_tier(ctx: SimpleNamespace) -> None:
    """All three equities hard-match the tech sleeve (1 ticker each), so
    cosine against the sleeve query orders them: AAPL > NVDA > MSFT."""

    ctx.add_news(ticker="AAPL", title="AAPL", vector=AAPL_VEC)
    ctx.add_news(ticker="MSFT", title="MSFT", vector=MSFT_VEC)
    ctx.add_news(ticker="NVDA", title="NVDA", vector=NVDA_VEC)
    out = _svc(ctx).news_for_sleeve("satellite_us_quality")
    assert [r.title for r in out] == ["AAPL", "NVDA", "MSFT"]
    assert out[0].score > out[1].score > out[2].score


def test_match_count_dominates_cosine(ctx: SimpleNamespace) -> None:
    """A news mentioning two sleeve tickers (score≈2) outranks a single-
    ticker news even with a high cosine (score≈1.94)."""

    ctx.add_news(ticker="AAPL", title="single high cosine", vector=AAPL_VEC)
    ctx.add_news(ticker="MSFT", ticker_mentions=["AAPL"], title="two tickers")
    out = _svc(ctx).news_for_sleeve("satellite_us_quality")
    assert out[0].title == "two tickers"
    assert out[0].score >= 2.0
    assert out[1].title == "single high cosine"


def test_missing_embedding_scores_match_count_only(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="AAPL", title="no vector")
    out = _svc(ctx).news_for_sleeve("satellite_us_quality")
    assert out[0].score == 1.0  # 1 matched ticker + 0 cosine


# --- filters --------------------------------------------------------------


def test_topic_filter(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="AAPL", title="annual", form_type="10-K")  # 财报
    ctx.add_news(ticker="AAPL", title="event", form_type="8-K")  # 重大事件
    out = _svc(ctx).news_for_sleeve("satellite_us_quality", topic="财报")
    assert [r.title for r in out] == ["annual"]


def test_source_and_form_type_filters(ctx: SimpleNamespace) -> None:
    ctx.add_news(ticker="AAPL", title="edgar", source="sec_edgar", form_type="10-K")
    ctx.add_news(ticker="AAPL", title="yahoo", source="yahoo_rss", form_type=None)
    svc = _svc(ctx)
    by_source = svc.news_for_sleeve("satellite_us_quality", source="yahoo_rss")
    assert [r.title for r in by_source] == ["yahoo"]
    by_form = svc.news_for_sleeve("satellite_us_quality", form_type="10-K")
    assert [r.title for r in by_form] == ["edgar"]


def test_since_filter_and_limit(ctx: SimpleNamespace) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for offset in range(4):
        ctx.add_news(
            ticker="AAPL",
            title=f"item {offset}",
            published_at=base + timedelta(days=offset),
        )
    svc = _svc(ctx)
    recent = svc.news_for_sleeve(
        "satellite_us_quality", since=base + timedelta(days=2)
    )
    assert {r.title for r in recent} == {"item 2", "item 3"}
    limited = svc.news_for_sleeve("satellite_us_quality", limit=1)
    assert len(limited) == 1
