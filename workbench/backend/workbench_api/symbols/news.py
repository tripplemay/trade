"""B059 F004 / B064 F002 — symbol news service (reuses the B034/B035 news feed).

Returns recent news for an arbitrary ticker by reusing the existing
``NewsRepository.list_by_ticker`` (exact-match on the indexed ``ticker``
column), the Simplified-Chinese ``title_zh`` (falls back to the source title),
and the deterministic ``tag_topics`` tagger (never LLM-generated).

**B064**: for A-share (.SH/.SZ) + Hong Kong (.HK) tickers the read is preceded
by an **on-demand cache-first** akshare ingest (``cn_hk_news.ingest_symbol_news``)
— the lookup is any-ticker so CN/HK news cannot be batch-ingested ahead of time.
The ingest is best-effort: any failure (akshare unreachable / rate-limited)
degrades to the honest empty / previously-cached state, never a 500. US tickers
keep the pure batch-fed read path unchanged.

Request-path safe (§12.10.2): no ``trade`` import (akshare is lazy-imported
inside ``cn_hk_news``)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.topics import tag_topics
from workbench_api.schemas.news import LatestNewsItem
from workbench_api.schemas.symbols import SymbolNewsResponse
from workbench_api.symbols.cn_hk_news import ingest_symbol_news
from workbench_api.symbols.service import normalize_symbol
from workbench_api.symbols.symbol_ref import SymbolRef

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
    ref = SymbolRef.parse(symbol)
    if ref.market in ("CN", "HK"):
        try:
            ingest_symbol_news(session, ref)
        except Exception:
            # Honest degrade: discard any partial/failed write so the read can
            # still serve previously-cached rows (or the empty state).
            session.rollback()
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
