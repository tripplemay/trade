"""B034 F002 — deterministic news topic taxonomy.

Tags a news item with one or more Chinese topic labels using **only**
deterministic rules (no LLM — B034 AI boundary §3): the SEC form type
plus a keyword rule table over ``title + summary``. A news item can
carry multiple topics (a ``8-K`` whose title mentions a dividend is
both ``重大事件`` and ``股息``); when nothing matches it falls back to
``其他``.

Keeping this rule-based (vs. an LLM classifier) is a deliberate B034
boundary decision — generative tagging is B036 scope. The rule table is
inlined and easy to extend; each rule is ``(topic, keywords)`` where a
case-insensitive whole-word match of any keyword in the text assigns
the topic.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workbench_api.db.models.news import News

OTHER_TOPIC = "其他"

# SEC form type → topic. Form types arrive normalised (e.g. "10-K").
FORM_TYPE_TOPICS: dict[str, str] = {
    "10-K": "财报",
    "10-Q": "财报",
    "8-K": "重大事件",
    "4": "内部人交易",
}

# Keyword rules over title + summary. ``(topic, (keywords...))`` —
# whole-word, case-insensitive. Ordered so the resulting topic list is
# deterministic. Keywords are English (Yahoo RSS / SEC headlines are
# English); the topic labels are the product's Chinese taxonomy.
KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("股息", ("dividend", "dividends", "distribution")),
    ("业绩指引", ("guidance", "outlook", "forecast")),
    ("评级变动", ("upgrade", "upgrades", "downgrade", "downgrades", "rating")),
    ("并购", ("merger", "acquisition", "acquire", "acquires", "takeover")),
    ("财报", ("earnings", "results", "revenue", "quarterly report")),
)


def _matches_keyword(haystack: str, keyword: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def tag_topics(news: News) -> list[str]:
    """Return the ordered, de-duplicated topic list for ``news``.

    Order: the form-type topic first (if any), then keyword-rule topics
    in table order. Falls back to ``["其他"]`` when nothing matches."""

    topics: list[str] = []

    form_topic = FORM_TYPE_TOPICS.get((news.form_type or "").strip())
    if form_topic is not None:
        topics.append(form_topic)

    haystack = f"{news.title or ''} {news.summary or ''}".lower()
    for topic, keywords in KEYWORD_RULES:
        if topic in topics:
            continue
        if any(_matches_keyword(haystack, kw) for kw in keywords):
            topics.append(topic)

    return topics or [OTHER_TOPIC]
