"""B022 F007 — strategies registry endpoint coverage.

Pins the three contracts the frontend depends on:

1. Auth gate (anon → 401) — the registry is unauthenticated nowhere.
2. List shape — at least the 4 sleeves the spec calls out.
3. Detail-or-404 — known id 200, unknown id 404. Both round-trip the
   field set the StrategyDetail schema declares so the
   /api/strategies/{id} responder cannot silently drop a field.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_active_users() -> None:
    active_users.clear()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "strategies-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_strategies_list_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/strategies").status_code == 401


def test_strategies_list_returns_four_sleeves(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies")
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert isinstance(payload["strategies"], list)
    ids = [entry["id"] for entry in payload["strategies"]]
    # F007 acceptance — exactly the 4 sleeves spec calls out (B019 default).
    assert ids == [
        "B013-regime-quarterly",
        "B014-regime-stress",
        "B015-regime-active",
        "B016-risk-parity-hrp",
    ]


def test_strategy_detail_known_id_returns_provenance(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/B013-regime-quarterly")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "B013-regime-quarterly"
    assert payload["sleeve"] == "regime"
    # Schema fields present (no silent drops).
    assert "config" in payload
    assert "provenance" in payload
    assert payload["provenance"]["spec_path"].endswith(".md")
    assert payload["provenance"]["last_sweep_path"] is not None
    # B019 retune sets activation_threshold=0.11; pinned so a future
    # config edit that drops the field surfaces here.
    assert payload["config"]["activation_threshold"] == 0.11


def test_strategy_detail_unknown_id_returns_404(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/does-not-exist")
    assert response.status_code == 404
    assert "Unknown strategy id" in response.json()["detail"]
