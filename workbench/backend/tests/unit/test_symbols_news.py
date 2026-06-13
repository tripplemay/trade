"""B059 F004 — get_symbol_news: per-symbol feed, title_zh, honest empty state.

Seeds News rows in the fixture DB and exercises the reuse of
NewsRepository.list_by_ticker + title_zh fallback + topic tagging.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.symbols.news import get_symbol_news
from workbench_api.symbols.provider import InvalidSymbolError


def _seed(
    session: Session,
    *,
    ticker: str,
    title: str,
    published_at: datetime,
    title_zh: str | None = None,
    source: str = "yahoo_rss",
    form_type: str | None = None,
) -> None:
    session.add(
        News(
            id=uuid4(),
            source=source,
            source_id=f"{ticker}-{title}",
            url="https://example.com/n",
            title=title,
            title_zh=title_zh,
            summary=None,
            ticker=ticker,
            form_type=form_type,
            published_at=published_at,
            fetched_at=published_at,
            snapshot_path="snap/x.htm",
            content_sha256="sha256:deadbeef",
            ticker_mentions=None,
        )
    )


def test_symbol_news_returns_items_newest_first_with_title_zh(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(
            session,
            ticker="AAPL",
            title="Apple older headline",
            published_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
        )
        _seed(
            session,
            ticker="AAPL",
            title="Apple newer headline",
            title_zh="苹果最新头条",
            published_at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
            form_type="10-K",
        )
        session.commit()

        result = get_symbol_news(session, "aapl")  # lower-case → normalised
        assert result.symbol == "AAPL"
        assert len(result.items) == 2
        # Newest first; Chinese title preferred when present.
        assert result.items[0].title == "苹果最新头条"
        assert result.items[1].title == "Apple older headline"
        # Deterministic topic tags are attached (10-K → 财报).
        assert isinstance(result.items[0].topics, list)
        assert "财报" in result.items[0].topics


def test_symbol_news_empty_state(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        result = get_symbol_news(session, "ZZZZ")
        assert result.symbol == "ZZZZ"
        assert result.items == []


def test_symbol_news_does_not_leak_other_tickers(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(
            session,
            ticker="MSFT",
            title="Microsoft headline",
            published_at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        )
        session.commit()
        result = get_symbol_news(session, "AAPL")
        assert result.items == []


def test_symbol_news_invalid_symbol_raises(initialised_db: str) -> None:
    with Session(get_engine()) as session, pytest.raises(InvalidSymbolError):
        get_symbol_news(session, "A" * 40)
