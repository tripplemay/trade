"""B059 F001 — GET /api/symbols/{symbol}/price end-to-end.

Drives the route through the FastAPI TestClient with an auth override and a
monkeypatched provider / guard so no network is touched. Pins: 200 happy path
(normalised symbol + honest EOD labelling), 400 invalid ticker, 404 unknown
ticker (actionable copy), 429 rate-limited, and auth-gating.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

import workbench_api.symbols.fundamentals as fundamentals_module
import workbench_api.symbols.service as service_module
from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.models.news import News
from workbench_api.settings import Settings, get_settings
from workbench_api.symbols.provider import (
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
    SymbolRateLimitedError,
)

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "sym-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _recent_series(n: int = 60) -> list[PriceBar]:
    end = datetime.now(UTC).date()
    bars: list[PriceBar] = []
    for i in range(n):
        d = end - timedelta(days=(n - 1 - i))
        close = 100.0 + i
        bars.append(
            PriceBar(
                ticker="X",
                bar_date=d,
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                adj_close=close,
                volume=1_000,
            )
        )
    return bars


class _FakeProvider(SymbolDataProvider):
    name = "fake"

    def __init__(self, *, raise_not_found: bool = False) -> None:
        self._raise_not_found = raise_not_found
        self._bars = _recent_series()

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        if self._raise_not_found:
            raise SymbolNotFoundError(symbol)
        return list(self._bars)

    def get_quote(self, symbol: str) -> ProviderQuote:  # pragma: no cover
        raise NotImplementedError

    def get_stats(self, symbol: str) -> ProviderStats:  # pragma: no cover
        raise NotImplementedError


class _RaisingGuard:
    def check_and_increment(self) -> None:
        raise SymbolRateLimitedError("slow down")


def test_price_route_happy_path(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "_default_provider", lambda: _FakeProvider())
    client = _authed_client()
    resp = client.get("/api/symbols/aapl/price")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "AAPL"  # normalised
    assert body["is_eod"] is True
    # B061 F002 — source is honestly provider-derived now; fake provider = "fake".
    assert body["source"] == "fake"
    assert body["currency"] == "USD"  # US default (bare ticker)
    assert body["close"] == 159.0  # last bar: 100 + 59
    assert len(body["bars"]) == 60
    assert "returns" in body
    # No execution surface leaked into the price payload.
    assert "ticket" not in body
    assert "order" not in body


def test_price_route_invalid_symbol_returns_400(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "_default_provider", lambda: _FakeProvider())
    client = _authed_client()
    resp = client.get(f"/api/symbols/{'A' * 40}/price")
    assert resp.status_code == 400, resp.text
    assert "Invalid ticker" in resp.json()["detail"]


def test_price_route_unknown_symbol_returns_404(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service_module, "_default_provider", lambda: _FakeProvider(raise_not_found=True)
    )
    client = _authed_client()
    resp = client.get("/api/symbols/ZZZZ/price")
    assert resp.status_code == 404, resp.text
    detail = resp.json()["detail"]
    assert "ZZZZ" in detail
    assert "No price data" in detail  # actionable copy, default test locale = en


def test_price_route_rate_limited_returns_429(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "_default_provider", lambda: _FakeProvider())
    monkeypatch.setattr(service_module, "_default_guard", lambda: _RaisingGuard())
    client = _authed_client()
    resp = client.get("/api/symbols/AAPL/price")
    assert resp.status_code == 429, resp.text


def test_price_route_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    resp = client.get("/api/symbols/AAPL/price")
    assert resp.status_code in (401, 403)


class _StatsProvider(SymbolDataProvider):
    name = "fake"

    def __init__(self, stats: ProviderStats) -> None:
        self._stats = stats

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:  # pragma: no cover
        raise NotImplementedError

    def get_quote(self, symbol: str) -> ProviderQuote:  # pragma: no cover
        raise NotImplementedError

    def get_stats(self, symbol: str) -> ProviderStats:
        return self._stats


def test_fundamentals_route_us_equity_available(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    stats = ProviderStats(
        symbol="AAPL",
        source="yfinance",
        quote_type="EQUITY",
        country="United States",
        market_cap=3.0e12,
        trailing_pe=30.5,
    )
    monkeypatch.setattr(fundamentals_module, "_default_provider", lambda: _StatsProvider(stats))
    client = _authed_client()
    resp = client.get("/api/symbols/aapl/fundamentals")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["available"] is True
    assert body["reason"] is None
    assert body["market_cap"] == 3.0e12


def test_fundamentals_route_hk_available(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # B064 — HK (.HK) now surfaces akshare HKFRS fundamentals (available), no
    # longer the B059 'non_us' degradation. Routing goes through
    # _resolve_provider, so that's the monkeypatch seam (not _default_provider).
    stats = ProviderStats(
        symbol="0700.HK",
        source="akshare",
        currency="HKD",
        quote_type="EQUITY",
        country="Hong Kong",
        long_name="腾讯控股",
        accounting_standard="HKFRS",
        market_cap=4.06e12,
        trailing_pe=15.23,
    )
    monkeypatch.setattr(
        fundamentals_module, "_resolve_provider", lambda _s: _StatsProvider(stats)
    )
    client = _authed_client()
    resp = client.get("/api/symbols/0700.HK/fundamentals")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True
    assert body["reason"] is None
    assert body["accounting_standard"] == "HKFRS"
    assert body["currency"] == "HKD"
    assert body["market_cap"] == 4.06e12


def test_fundamentals_route_cn_source_unavailable_degrades(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # akshare unreachable → minimal identity, honest source_unavailable (200).
    stats = ProviderStats(
        symbol="600519.SH",
        source="akshare",
        currency="CNY",
        quote_type="EQUITY",
        country="China",
        accounting_standard="CAS",
    )
    monkeypatch.setattr(
        fundamentals_module, "_resolve_provider", lambda _s: _StatsProvider(stats)
    )
    client = _authed_client()
    resp = client.get("/api/symbols/600519.SH/fundamentals")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is False
    assert body["reason"] == "source_unavailable"
    assert body["market_cap"] is None
    assert body["currency"] == "CNY"


def test_fundamentals_route_invalid_symbol_returns_400(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    stats = ProviderStats(symbol="X", source="yfinance")
    monkeypatch.setattr(fundamentals_module, "_default_provider", lambda: _StatsProvider(stats))
    client = _authed_client()
    resp = client.get(f"/api/symbols/{'A' * 40}/fundamentals")
    assert resp.status_code == 400, resp.text


def _seed_news(ticker: str, title: str) -> None:
    with Session(get_engine()) as session:
        session.add(
            News(
                id=uuid4(),
                source="yahoo_rss",
                source_id=f"{ticker}-{title}",
                url="https://example.com/n",
                title=title,
                title_zh=None,
                summary=None,
                ticker=ticker,
                form_type=None,
                published_at=datetime(2026, 6, 12, tzinfo=UTC),
                fetched_at=datetime(2026, 6, 12, tzinfo=UTC),
                snapshot_path="snap/x.htm",
                content_sha256="sha256:abc",
                ticker_mentions=None,
            )
        )
        session.commit()


def test_news_route_returns_items(initialised_db: str) -> None:
    _seed_news("AAPL", "Apple headline")
    client = _authed_client()
    resp = client.get("/api/symbols/aapl/news")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Apple headline"


def test_news_route_empty_state(initialised_db: str) -> None:
    client = _authed_client()
    resp = client.get("/api/symbols/ZZZZ/news")
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


def test_news_route_invalid_symbol_returns_400(initialised_db: str) -> None:
    client = _authed_client()
    resp = client.get(f"/api/symbols/{'A' * 40}/news")
    assert resp.status_code == 400, resp.text
