"""B038 F001 — global "latest news" read service.

Assembles the ``GET /api/news/latest`` payload from
``NewsRepository.list_latest_global`` + the deterministic
:func:`workbench_api.news.topics.tag_topics` tagger. Pure read over the
``news`` table; **no repo-root file reads** on the request path
(v0.9.32 §12.10) and **no generative call on the request path** — this
service only *reads* metadata columns + the pre-computed ``title_zh``
(B054 F-news: the Simplified-Chinese headline is translated off the
request path by the ``news_translation`` batch and cached on the row, so
the read path stays non-generative, exactly like the cached embeddings).
The deterministic topic tag and all other fields are metadata. Only the
metadata columns are surfaced; the snapshot body (boundary (p)) is never
read here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.topics import tag_topics
from workbench_api.schemas.news import LatestNewsItem, LatestNewsResponse

DEFAULT_LIMIT = 20


def build_latest_news(
    session: Session,
    *,
    limit: int = DEFAULT_LIMIT,
    since: datetime | None = None,
    source: str | None = None,
    form_type: str | None = None,
) -> LatestNewsResponse:
    """Return the newest-first global news feed as metadata-only items.

    An empty ``news`` table surfaces as ``items=[]`` (the Home news
    section renders an empty state). Topics are tagged deterministically
    from the form type + title/summary keyword rules — never an LLM call."""

    repo = NewsRepository(session)
    rows = repo.list_latest_global(
        limit=limit, since=since, source=source, form_type=form_type
    )
    items = [
        LatestNewsItem(
            news_id=str(row.id),
            # B054 F-news — prefer the pre-computed Simplified-Chinese
            # headline; fall back to the English source title when the
            # translation batch has not run for this row yet.
            title=row.title_zh or row.title,
            source=row.source,
            url=row.url,
            published_at=row.published_at.isoformat(),
            topics=tag_topics(row),
        )
        for row in rows
    ]
    return LatestNewsResponse(items=items)
