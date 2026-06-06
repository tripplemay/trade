"""B038 F001 — global latest-news feed: repo + service + route.

Covers ``NewsRepository.list_latest_global`` (newest-first, cross-ticker,
optional source / form_type / since filters), ``build_latest_news``
(recency order, deterministic topic tags, metadata-only items), and
``GET /api/news/latest`` (auth gate, structured payload, exact field set,
v0.9.32 §12.10 request-path self-containment).
"""

from __future__ import annotations

import ast
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.services.news import build_latest_news
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_ITEM_FIELDS = {"news_id", "title", "source", "url", "published_at", "topics"}

_BASE = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _seed_news(
    *,
    source_id: str,
    source: str = "yahoo_rss",
    title: str = "Market headline",
    ticker: str | None = None,
    form_type: str | None = None,
    summary: str | None = None,
    published_at: datetime,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            News(
                id=uuid4(),
                source=source,
                source_id=source_id,
                url=f"https://example.com/{source_id}",
                title=title,
                summary=summary,
                ticker=ticker,
                form_type=form_type,
                published_at=published_at,
                fetched_at=datetime(2026, 6, 4, tzinfo=UTC),
                snapshot_path=f"{source}/{source_id}",
                content_sha256="a" * 64,
                ticker_mentions=None,
            )
        )
        session.commit()


@pytest.fixture
def repo(initialised_db: str) -> Iterator[NewsRepository]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    yield NewsRepository(session)
    session.close()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "news-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


# --- Repository.list_latest_global ----------------------------------------


def test_list_latest_global_newest_first_cross_ticker(repo: NewsRepository) -> None:
    _seed_news(source_id="A", ticker="AAPL", published_at=_BASE, title="oldest")
    _seed_news(
        source_id="B", ticker="NVDA", published_at=_BASE + timedelta(days=2), title="newest"
    )
    _seed_news(
        source_id="C", ticker="SPY", published_at=_BASE + timedelta(days=1), title="middle"
    )
    rows = repo.list_latest_global()
    assert [r.title for r in rows] == ["newest", "middle", "oldest"]


def test_list_latest_global_applies_limit(repo: NewsRepository) -> None:
    for offset in range(5):
        _seed_news(source_id=f"n{offset}", published_at=_BASE + timedelta(days=offset))
    rows = repo.list_latest_global(limit=2)
    assert len(rows) == 2
    assert rows[0].source_id == "n4"
    assert rows[1].source_id == "n3"


def test_list_latest_global_source_filter(repo: NewsRepository) -> None:
    _seed_news(source_id="e1", source="sec_edgar", published_at=_BASE)
    _seed_news(source_id="y1", source="yahoo_rss", published_at=_BASE + timedelta(days=1))
    rows = repo.list_latest_global(source="sec_edgar")
    assert [r.source_id for r in rows] == ["e1"]


def test_list_latest_global_form_type_filter(repo: NewsRepository) -> None:
    _seed_news(source_id="k", source="sec_edgar", form_type="10-K", published_at=_BASE)
    _seed_news(
        source_id="q",
        source="sec_edgar",
        form_type="10-Q",
        published_at=_BASE + timedelta(days=1),
    )
    rows = repo.list_latest_global(form_type="10-Q")
    assert [r.source_id for r in rows] == ["q"]


def test_list_latest_global_since_filter(repo: NewsRepository) -> None:
    for offset in range(4):
        _seed_news(source_id=f"s{offset}", published_at=_BASE + timedelta(days=offset))
    rows = repo.list_latest_global(since=_BASE + timedelta(days=2))
    assert [r.source_id for r in rows] == ["s3", "s2"]


def test_list_latest_global_empty(repo: NewsRepository) -> None:
    assert repo.list_latest_global() == []


# --- services.build_latest_news -------------------------------------------


def test_build_latest_news_recency_order(initialised_db: str) -> None:  # noqa: ARG001
    _seed_news(source_id="old", published_at=_BASE, title="old")
    _seed_news(source_id="new", published_at=_BASE + timedelta(days=1), title="new")
    with Session(get_engine()) as session:
        resp = build_latest_news(session)
    assert [i.title for i in resp.items] == ["new", "old"]


def test_build_latest_news_tags_topics_deterministically(
    initialised_db: str,  # noqa: ARG001
) -> None:
    _seed_news(
        source_id="k",
        source="sec_edgar",
        form_type="10-K",
        title="Apple Q1 earnings beat",
        published_at=_BASE,
    )
    with Session(get_engine()) as session:
        resp = build_latest_news(session)
    # form-type 10-K → 财报; the keyword rule "earnings" also maps to 财报 (deduped).
    assert resp.items[0].topics == ["财报"]


def test_build_latest_news_items_are_metadata_only(initialised_db: str) -> None:  # noqa: ARG001
    _seed_news(source_id="m", title="Headline", summary="some body", published_at=_BASE)
    with Session(get_engine()) as session:
        resp = build_latest_news(session)
    item = resp.items[0]
    # No sleeve-relevance / free-form-text fields on the global feed item.
    assert set(item.model_dump().keys()) == EXPECTED_ITEM_FIELDS


def test_build_latest_news_source_filter(initialised_db: str) -> None:  # noqa: ARG001
    _seed_news(source_id="e", source="sec_edgar", published_at=_BASE)
    _seed_news(source_id="y", source="yahoo_rss", published_at=_BASE + timedelta(days=1))
    with Session(get_engine()) as session:
        resp = build_latest_news(session, source="yahoo_rss")
    assert [i.source for i in resp.items] == ["yahoo_rss"]


def test_build_latest_news_empty_table(initialised_db: str) -> None:  # noqa: ARG001
    with Session(get_engine()) as session:
        resp = build_latest_news(session)
    assert resp.items == []


# --- GET /api/news/latest -------------------------------------------------


def test_news_latest_requires_auth(initialised_db: str) -> None:  # noqa: ARG001
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/news/latest").status_code == 401


def test_news_latest_authed_returns_structured_payload(
    initialised_db: str,  # noqa: ARG001
) -> None:
    _seed_news(
        source_id="r1",
        source="sec_edgar",
        form_type="8-K",
        title="Fed minutes released",
        published_at=_BASE,
    )
    client = _authed_client()
    resp = client.get("/api/news/latest")
    assert resp.status_code == 200
    payload = resp.json()
    assert set(payload.keys()) == {"items"}
    item = payload["items"][0]
    assert set(item.keys()) == EXPECTED_ITEM_FIELDS
    assert item["title"] == "Fed minutes released"
    assert item["source"] == "sec_edgar"
    assert item["topics"] == ["重大事件"]
    assert item["url"].startswith("https://")


def test_news_latest_empty_state_is_empty_items(initialised_db: str) -> None:  # noqa: ARG001
    client = _authed_client()
    payload = client.get("/api/news/latest").json()
    assert payload == {"items": []}


# --- v0.9.32 §12.10 request-path self-containment -------------------------


def test_request_path_is_self_contained() -> None:
    """The /news/latest request-path modules must not read repo-root fixtures
    or import pandas / the scripts package (the B034 production-500 class).
    Data comes from the DB + the in-package deterministic topic tagger only."""

    request_path = [
        BACKEND_ROOT / "workbench_api" / "schemas" / "news.py",
        BACKEND_ROOT / "workbench_api" / "services" / "news.py",
        BACKEND_ROOT / "workbench_api" / "routes" / "news.py",
        BACKEND_ROOT / "workbench_api" / "db" / "repositories" / "news.py",
        BACKEND_ROOT / "workbench_api" / "news" / "topics.py",
    ]
    forbidden_substrings = ("data/fixtures", ".csv", "open(")
    for path in request_path:
        src = path.read_text(encoding="utf-8")
        for frag in forbidden_substrings:
            assert frag not in src, f"{path.name} reads a file ({frag!r}) on the request path"
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".", 1)[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert "pandas" not in imported, f"{path.name} imports pandas on the request path"
        assert "scripts" not in imported, f"{path.name} imports scripts on the request path"
