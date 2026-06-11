"""B054 F-news — news headline → Simplified-Chinese translation.

Covers the generative translation service (prompt shape + no-AI clean/guard),
the batch CLI (idempotent, only NULL ``title_zh`` rows, None-output skip), and
the serving-path fallback (``title_zh or title``) on both user-facing news
surfaces — the Home global feed and the Recommendations sleeve-news panel.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.llm.cost_guard import BudgetExceeded
from workbench_api.llm.gateway import ChatRequest, ChatResult
from workbench_api.news.association import NewsAssociationService
from workbench_api.news_translation.cli import run_translation
from workbench_api.news_translation.service import (
    NEWS_TRANSLATE_TASK,
    NewsTranslationService,
    build_default_translator,
)
from workbench_api.services.news import build_latest_news

_BASE = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _chat_result(content: str) -> ChatResult:
    return ChatResult(
        content=content,
        model_used="claude-haiku-4.5",
        input_tokens=10,
        output_tokens=5,
        cost_usd_est=0.0,
        aigc_log_id="log-1",
    )


class _StubGateway:
    """Returns a fixed translation; records each request for assertions."""

    def __init__(self, content: str = "某中文标题") -> None:
        self._content = content
        self.requests: list[ChatRequest] = []

    def advise(self, request: ChatRequest) -> ChatResult:
        self.requests.append(request)
        return _chat_result(self._content)


class _MapGateway:
    """Translate by source-title lookup (unknown → empty string)."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping
        self.calls = 0

    def advise(self, request: ChatRequest) -> ChatResult:
        self.calls += 1
        source = request.messages[-1]["content"]
        return _chat_result(self._mapping.get(source, ""))


class _FlakyGateway:
    """Raises a transient HTTP error for titles in ``fail_on``; else maps."""

    def __init__(self, mapping: dict[str, str], *, fail_on: set[str]) -> None:
        self._mapping = mapping
        self._fail_on = fail_on
        self.calls = 0

    def advise(self, request: ChatRequest) -> ChatResult:
        self.calls += 1
        source = request.messages[-1]["content"]
        if source in self._fail_on:
            raise httpx.ConnectError("simulated gateway 429 / network blip")
        return _chat_result(self._mapping.get(source, ""))


class _BudgetTrippedGateway:
    """Always trips the monthly cost cap (must abort the batch)."""

    def advise(self, request: ChatRequest) -> ChatResult:  # noqa: ARG002
        raise BudgetExceeded("Monthly LLM budget cap reached")


# --- service: prompt shape + guard ----------------------------------------


def test_translate_title_returns_chinese() -> None:
    gw = _StubGateway("苹果公司发布季度财报")
    svc = NewsTranslationService(gw)
    assert svc.translate_title("Apple reports quarterly earnings") == "苹果公司发布季度财报"


def test_prompt_routes_to_news_translate_task_with_zh_instruction() -> None:
    gw = _StubGateway()
    NewsTranslationService(gw).translate_title("Fed holds rates")
    assert len(gw.requests) == 1
    req = gw.requests[0]
    assert req.task == NEWS_TRANSLATE_TASK
    system = req.messages[0]
    user = req.messages[-1]
    assert system["role"] == "system"
    assert "Simplified Chinese" in system["content"]
    assert "zh-CN" in system["content"]
    # The user message is just the source headline (no leakage / preamble).
    assert user["content"] == "Fed holds rates"
    # Deterministic translation — temperature pinned to 0.
    assert req.temperature == 0.0


def test_strips_wrapping_quotes() -> None:
    gw = _StubGateway('"美联储维持利率不变"')
    assert NewsTranslationService(gw).translate_title("Fed holds rates") == "美联储维持利率不变"


def test_empty_output_returns_none() -> None:
    gw = _StubGateway("   ")
    assert NewsTranslationService(gw).translate_title("Fed holds rates") is None


def test_overlong_output_rejected() -> None:
    # A model that ignored "output only the translation" and appended a
    # paragraph of commentary must be rejected (leaves title_zh NULL).
    gw = _StubGateway("利率" * 400)
    assert NewsTranslationService(gw).translate_title("Fed holds rates") is None


def test_empty_title_skips_gateway_call() -> None:
    gw = _StubGateway()
    assert NewsTranslationService(gw).translate_title("   ") is None
    assert gw.requests == []  # no spend on an empty headline


def test_build_default_translator_none_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIGC_GATEWAY_API_KEY", raising=False)
    assert build_default_translator() is None


# --- batch CLI: idempotent, NULL-only, None-output skip -------------------


def _seed(
    session: Session,
    *,
    source_id: str,
    title: str,
    title_zh: str | None = None,
    ticker: str | None = None,
    published_at: datetime | None = None,
) -> News:
    row = News(
        id=uuid4(),
        source="yahoo_rss",
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        title=title,
        title_zh=title_zh,
        summary=None,
        ticker=ticker,
        form_type=None,
        published_at=published_at or _BASE,
        fetched_at=_BASE,
        snapshot_path=f"yahoo_rss/{source_id}",
        content_sha256="a" * 64,
        ticker_mentions=None,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def test_run_translation_only_untranslated_rows(session: Session) -> None:
    _seed(session, source_id="done", title="Already done", title_zh="已翻译")
    _seed(session, source_id="todo", title="Translate me")
    session.commit()

    gw = _MapGateway({"Translate me": "翻译我"})
    summary = run_translation(
        session, NewsTranslationService(gw), limit=50, sleep_seconds=0
    )

    assert summary.translated == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert gw.calls == 1  # the already-translated row is never re-sent
    repo = NewsRepository(session)
    rows = {r.source_id: r.title_zh for r in repo.list_all_rows()}
    assert rows == {"done": "已翻译", "todo": "翻译我"}


def test_run_translation_skips_on_none_output(session: Session) -> None:
    _seed(session, source_id="bad", title="Untranslatable")
    session.commit()

    gw = _MapGateway({})  # returns "" → None → skip
    summary = run_translation(
        session, NewsTranslationService(gw), limit=50, sleep_seconds=0
    )

    assert summary.translated == 0
    assert summary.skipped == 1
    assert summary.failed == 0
    row = NewsRepository(session).get_by_source_and_source_id("yahoo_rss", "bad")
    assert row is not None
    assert row.title_zh is None  # left NULL to retry next run


def test_run_translation_is_idempotent(session: Session) -> None:
    _seed(session, source_id="x", title="Hello world")
    session.commit()
    gw = _MapGateway({"Hello world": "你好世界"})
    svc = NewsTranslationService(gw)

    first = run_translation(session, svc, limit=50, sleep_seconds=0)
    second = run_translation(session, svc, limit=50, sleep_seconds=0)

    assert first.translated == 1
    assert second.translated == 0  # nothing left untranslated
    assert gw.calls == 1


def test_run_translation_survives_transient_gateway_error(session: Session) -> None:
    # One row's gateway call fails transiently (429 / network); the batch must
    # not abort — the other rows still translate, the failed row stays NULL.
    _seed(session, source_id="ok1", title="First headline", published_at=_BASE)
    _seed(
        session,
        source_id="boom",
        title="Boom headline",
        published_at=_BASE + timedelta(days=1),
    )
    _seed(
        session,
        source_id="ok2",
        title="Third headline",
        published_at=_BASE + timedelta(days=2),
    )
    session.commit()

    gw = _FlakyGateway(
        {"First headline": "第一条", "Third headline": "第三条"},
        fail_on={"Boom headline"},
    )
    summary = run_translation(
        session, NewsTranslationService(gw), limit=50, sleep_seconds=0
    )

    assert summary.translated == 2
    assert summary.failed == 1
    repo = NewsRepository(session)
    rows = {r.source_id: r.title_zh for r in repo.list_all_rows()}
    assert rows == {"ok1": "第一条", "boom": None, "ok2": "第三条"}


def test_run_translation_commits_progress_before_failure(session: Session) -> None:
    # Even if a later row raises a non-HTTP error and the batch unwinds, the
    # rows committed by an earlier incremental flush survive the rollback.
    # list_untranslated is newest-first, so "first" (later published_at) is
    # processed before "second".
    _seed(
        session, source_id="first", title="A", published_at=_BASE + timedelta(days=1)
    )
    _seed(session, source_id="second", title="B", published_at=_BASE)
    session.commit()

    class _OneThenBudget:
        def __init__(self) -> None:
            self.calls = 0

        def advise(self, request: ChatRequest) -> ChatResult:  # noqa: ARG002
            self.calls += 1
            if self.calls == 1:
                return _chat_result("甲")
            raise BudgetExceeded("cap")

    with pytest.raises(BudgetExceeded):
        run_translation(
            session,
            NewsTranslationService(_OneThenBudget()),
            limit=50,
            sleep_seconds=0,
            commit_every=1,  # flush after the first successful row
        )
    session.rollback()
    repo = NewsRepository(session)
    first = repo.get_by_source_and_source_id("yahoo_rss", "first")
    second = repo.get_by_source_and_source_id("yahoo_rss", "second")
    assert first is not None and first.title_zh == "甲"  # early commit persisted
    assert second is not None and second.title_zh is None  # tripped before write


def test_run_translation_budget_cap_propagates(session: Session) -> None:
    _seed(session, source_id="x", title="Anything", published_at=_BASE)
    session.commit()
    with pytest.raises(BudgetExceeded):
        run_translation(
            session,
            NewsTranslationService(_BudgetTrippedGateway()),
            limit=50,
            sleep_seconds=0,
        )


def test_run_translation_throttles_between_rows(session: Session) -> None:
    _seed(session, source_id="a", title="A", published_at=_BASE)
    _seed(session, source_id="b", title="B", published_at=_BASE + timedelta(days=1))
    _seed(session, source_id="c", title="C", published_at=_BASE + timedelta(days=2))
    session.commit()

    delays: list[float] = []
    gw = _MapGateway({"A": "甲", "B": "乙", "C": "丙"})
    run_translation(
        session,
        NewsTranslationService(gw),
        limit=50,
        sleep_seconds=0.6,
        sleep=delays.append,
    )
    # One pause between each adjacent pair, never after the last row.
    assert delays == [0.6, 0.6]


# --- serving fallback: title_zh or title ----------------------------------


def test_latest_feed_prefers_title_zh(session: Session) -> None:
    _seed(session, source_id="z", title="English headline", title_zh="中文标题")
    session.commit()
    resp = build_latest_news(session)
    assert resp.items[0].title == "中文标题"


def test_latest_feed_falls_back_to_english(session: Session) -> None:
    _seed(session, source_id="e", title="English headline")  # title_zh NULL
    session.commit()
    resp = build_latest_news(session)
    assert resp.items[0].title == "English headline"


def test_sleeve_news_prefers_title_zh(session: Session) -> None:
    # AAPL is a satellite_us_quality constituent (see test_news_association).
    _seed(
        session,
        source_id="aapl-zh",
        title="Apple files 10-Q",
        title_zh="苹果提交 10-Q 季报",
        ticker="AAPL",
        published_at=_BASE + timedelta(days=1),
    )
    session.commit()
    svc = NewsAssociationService(session)
    results = svc.news_for_sleeve("satellite_us_quality")
    assert results
    assert results[0].title == "苹果提交 10-Q 季报"


def test_sleeve_news_falls_back_to_english(session: Session) -> None:
    _seed(
        session,
        source_id="aapl-en",
        title="Apple files 10-Q",  # title_zh NULL
        ticker="AAPL",
    )
    session.commit()
    svc = NewsAssociationService(session)
    results = svc.news_for_sleeve("satellite_us_quality")
    assert results
    assert results[0].title == "Apple files 10-Q"
