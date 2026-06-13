"""B059 F004 — symbol news service (reuses the B034/B035 news feed).

Returns recent news for an arbitrary ticker by reusing the existing
``NewsRepository.list_by_ticker`` (exact-match on the indexed ``ticker``
column), the B054 Simplified-Chinese ``title_zh`` (falls back to the source
title), and the deterministic ``tag_topics`` tagger (never LLM-generated). A
symbol the ingest doesn't cover simply returns an empty list — the honest
"no recent news" empty state, not an error. Request-path safe: no ``trade``
import (mirrors the existing ``services/news`` read path).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.topics import tag_topics
from workbench_api.schemas.news import LatestNewsItem
from workbench_api.schemas.symbols import SymbolNewsResponse
from workbench_api.symbols.service import normalize_symbol

_DEFAULT_LIMIT = 20


def get_symbol_news(
    session: Session,
    raw_symbol: str,
    *,
    limit: int = _DEFAULT_LIMIT,
) -> SymbolNewsResponse:
    """Return newest-first news for ``raw_symbol`` (empty list = honest empty
    state). A malformed ticker raises :class:`InvalidSymbolError` (→ 400)."""

    symbol = normalize_symbol(raw_symbol)
    repo = NewsRepository(session)
    rows = repo.list_by_ticker(symbol, limit=limit)
    items = [
        LatestNewsItem(
            news_id=str(row.id),
            # B054 — prefer the Simplified-Chinese headline; fall back to source title.
            title=row.title_zh or row.title,
            source=row.source,
            url=row.url,
            published_at=row.published_at.isoformat(),
            topics=tag_topics(row),
        )
        for row in rows
    ]
    return SymbolNewsResponse(symbol=symbol, items=items)
