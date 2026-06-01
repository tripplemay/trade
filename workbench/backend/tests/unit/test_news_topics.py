"""B034 F002 — deterministic topic taxonomy (no LLM).

Pins the form-type mapping, keyword rules, multi-topic behaviour, and
the ``其他`` fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime

from workbench_api.db.models.news import News
from workbench_api.news.topics import OTHER_TOPIC, tag_topics


def _news(
    *,
    title: str = "Headline",
    summary: str | None = None,
    form_type: str | None = None,
) -> News:
    return News(
        title=title,
        summary=summary,
        form_type=form_type,
        source="sec_edgar",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
    )


def test_form_type_mappings() -> None:
    assert tag_topics(_news(form_type="10-K")) == ["财报"]
    assert tag_topics(_news(form_type="10-Q")) == ["财报"]
    assert tag_topics(_news(form_type="8-K")) == ["重大事件"]
    assert tag_topics(_news(form_type="4")) == ["内部人交易"]


def test_keyword_rules() -> None:
    assert "股息" in tag_topics(_news(title="Board declares dividend"))
    assert "业绩指引" in tag_topics(_news(title="Company raises guidance"))
    assert "评级变动" in tag_topics(_news(title="Analyst upgrade to buy"))
    assert "并购" in tag_topics(_news(summary="announced a merger"))


def test_keyword_is_whole_word() -> None:
    # "guidances" is not the whole word "guidance" → no 业绩指引 from it.
    assert tag_topics(_news(title="random guidances-like text")) == [OTHER_TOPIC]


def test_multiple_topics_form_type_first() -> None:
    topics = tag_topics(_news(title="8-K: special dividend approved", form_type="8-K"))
    assert topics[0] == "重大事件"  # form-type topic leads
    assert "股息" in topics


def test_other_fallback_when_no_rule_matches() -> None:
    assert tag_topics(_news(title="Quiet day", summary="nothing notable")) == [OTHER_TOPIC]


def test_topics_are_deduped() -> None:
    # form_type 10-K → 财报, and "earnings" keyword also → 财报; only once.
    topics = tag_topics(_news(title="Q4 earnings beat", form_type="10-K"))
    assert topics.count("财报") == 1
