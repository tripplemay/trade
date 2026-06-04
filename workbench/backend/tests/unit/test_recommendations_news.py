"""B034 F003 — GET /api/recommendations/news endpoint.

Pins the auth gate, the required ``sleeve`` query param, the filter
contract, and the **exact structured field set** (no AI-generated text
— B034 non-generative boundary §3).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"

EXPECTED_ITEM_FIELDS = {
    "news_id",
    "title",
    "source",
    "url",
    "published_at",
    "content_sha256",
    "topics",
    "matched_tickers",
    "score",
}


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


def _seed_news(
    *,
    ticker: str,
    title: str,
    form_type: str | None = None,
    source: str = "sec_edgar",
) -> None:
    with Session(get_engine()) as session:
        session.add(
            News(
                id=uuid4(),
                source=source,
                source_id=str(uuid4()),
                url=f"https://www.sec.gov/{ticker}",
                title=title,
                summary=None,
                ticker=ticker,
                form_type=form_type,
                published_at=datetime(2026, 5, 1, tzinfo=UTC),
                fetched_at=datetime(2026, 5, 1, tzinfo=UTC),
                snapshot_path=f"sec_edgar/2026-05-01/{ticker}.htm",
                content_sha256="aa" * 32,
                ticker_mentions=None,
            )
        )
        session.commit()


def test_news_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    resp = client.get("/api/recommendations/news?sleeve=satellite_us_quality")
    assert resp.status_code == 401


def test_news_requires_sleeve_param(initialised_db: str) -> None:
    client = _authed_client()
    assert client.get("/api/recommendations/news").status_code == 422


def test_news_returns_relevant_items(initialised_db: str) -> None:
    _seed_news(ticker="AAPL", title="Apple 10-K", form_type="10-K")
    _seed_news(ticker="TSLA", title="Tesla news")  # not in universe
    client = _authed_client()
    payload = client.get(
        "/api/recommendations/news?sleeve=satellite_us_quality"
    ).json()
    assert [item["title"] for item in payload["items"]] == ["Apple 10-K"]
    item = payload["items"][0]
    assert item["matched_tickers"] == ["AAPL"]
    assert "财报" in item["topics"]
    assert item["score"] == pytest.approx(1.0)


def test_news_item_field_set_is_exactly_structured(initialised_db: str) -> None:
    """The response item carries exactly the structured fields — no
    free-form AI text field (B034 boundary)."""

    _seed_news(ticker="AAPL", title="Apple 10-K", form_type="10-K")
    client = _authed_client()
    payload = client.get(
        "/api/recommendations/news?sleeve=satellite_us_quality"
    ).json()
    assert set(payload.keys()) == {"items"}
    assert set(payload["items"][0].keys()) == EXPECTED_ITEM_FIELDS


def test_news_empty_for_unknown_sleeve(initialised_db: str) -> None:
    _seed_news(ticker="AAPL", title="Apple 10-K")
    client = _authed_client()
    payload = client.get("/api/recommendations/news?sleeve=no_such").json()
    assert payload == {"items": []}


def test_news_topic_filter(initialised_db: str) -> None:
    _seed_news(ticker="AAPL", title="annual", form_type="10-K")  # 财报
    _seed_news(ticker="AAPL", title="event", form_type="8-K")  # 重大事件
    client = _authed_client()
    payload = client.get(
        "/api/recommendations/news?sleeve=satellite_us_quality&topic=财报"
    ).json()
    assert [item["title"] for item in payload["items"]] == ["annual"]


def test_news_route_works_without_universe_fixture_file(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the F004 L2 production 500 (2026-06-04): the route
    must return 200 even when the repo-root universe fixture CSV is absent
    (it is not in the deploy artifact). Before the fix this raised
    FileNotFoundError → 500 — the exact production failure."""

    from pathlib import Path

    from workbench_api.news import ticker_match

    monkeypatch.setattr(
        ticker_match, "UNIVERSE_CSV", Path("/nonexistent/universe.csv")
    )
    ticker_match.build_ticker_dictionary.cache_clear()

    _seed_news(ticker="AAPL", title="Apple 10-K", form_type="10-K")
    client = _authed_client()
    resp = client.get("/api/recommendations/news?sleeve=satellite_us_quality")
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Apple 10-K"]

    ticker_match.build_ticker_dictionary.cache_clear()


def test_news_source_and_limit(initialised_db: str) -> None:
    _seed_news(ticker="AAPL", title="edgar", source="sec_edgar")
    _seed_news(ticker="AAPL", title="yahoo", source="yahoo_rss")
    client = _authed_client()
    by_source = client.get(
        "/api/recommendations/news?sleeve=satellite_us_quality&source=yahoo_rss"
    ).json()
    assert [item["title"] for item in by_source["items"]] == ["yahoo"]
    limited = client.get(
        "/api/recommendations/news?sleeve=satellite_us_quality&limit=1"
    ).json()
    assert len(limited["items"]) == 1
