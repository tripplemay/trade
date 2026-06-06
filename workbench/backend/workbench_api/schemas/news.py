"""B038 F001 — schemas for ``GET /api/news/latest``.

The Home "Today's market news" feed (personas §2 mockup). Purely
structured metadata + deterministic topic tags — **no AI-generated
text** (B034 non-generative boundary §3: no ``summary`` / ``advice`` /
``rationale`` free-form field). Unlike B034's ``SleeveNewsItem`` this is
a global, sleeve-less feed, so the ``matched_tickers`` / ``score``
relevance fields are dropped. ``tests/safety/test_b034_no_generative_ai.py``
pins this exact field set so a future free-text field can't slip in.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LatestNewsItem(BaseModel):
    """One global-feed news headline (metadata-only)."""

    news_id: str = Field(description="News row UUID (string form).")
    title: str
    source: str = Field(description="'sec_edgar' / 'yahoo_rss'.")
    url: str = Field(description="Source URL (rendered as an external link).")
    published_at: str = Field(description="ISO-8601 publish timestamp.")
    topics: list[str] = Field(
        default_factory=list,
        description="Deterministic topic tags (财报 / 重大事件 / …); never LLM-generated.",
    )


class LatestNewsResponse(BaseModel):
    """GET /api/news/latest payload — newest-first global market news."""

    items: list[LatestNewsItem] = Field(default_factory=list)
