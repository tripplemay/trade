"""B022 F008 — backtest runner + result cache endpoint coverage.

The runner is synthetic (F008 ships placeholder math until B023 wires
real ``trade.master.run_backtest``), but the contract this test pins
is stable:

* Auth gate — anon must 401.
* run-then-fetch round trip — POST returns a run_id; GET by that id
  returns the same payload (deterministic via the seed helper).
* Unknown strategy_id → 404 (sanitises bad input before the synthetic
  math runs).
* Unknown run_id → 404 (cache misses don't 500).
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
from workbench_api.services.backtests import reset_cache
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()
    reset_cache()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "backtests-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


SAMPLE_REQUEST: dict[str, Any] = {
    "strategy_id": "B013-regime-quarterly",
    "snapshot_id": "snap-fixture",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "parameters": {},
}


def test_backtest_run_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.post("/api/backtests/run", json=SAMPLE_REQUEST).status_code == 401


def test_backtest_run_then_fetch_round_trip(initialised_db: str) -> None:
    client = _authed_client()
    response = client.post("/api/backtests/run", json=SAMPLE_REQUEST)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    run_id = payload["run_id"]
    assert isinstance(run_id, str) and run_id
    # Headline schema fields present + non-empty.
    assert payload["metrics"]["cagr"] != 0 or payload["metrics"]["sharpe"] != 0
    assert len(payload["equity"]) > 0
    assert payload["equity"][0]["nav"] > 0
    assert len(payload["trades"]) > 0

    fetched = client.get(f"/api/backtests/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json() == payload


def test_backtest_run_unknown_strategy_returns_404(initialised_db: str) -> None:
    client = _authed_client()
    response = client.post(
        "/api/backtests/run",
        json={**SAMPLE_REQUEST, "strategy_id": "does-not-exist"},
    )
    assert response.status_code == 404
    assert "Unknown strategy id" in response.json()["detail"]


def test_backtest_get_unknown_run_id_returns_404(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/backtests/no-such-run")
    assert response.status_code == 404


def test_backtest_finishes_under_five_seconds(initialised_db: str) -> None:
    """F008 acceptance target: synchronous run < 5s on a canned snapshot.

    The synthetic engine runs in < 100ms on commodity hardware; this
    test guards against a future regression that swaps in a slower
    implementation without updating the page UX.
    """

    client = _authed_client()
    start = time.perf_counter()
    response = client.post("/api/backtests/run", json=SAMPLE_REQUEST)
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 5.0, f"backtest took {elapsed:.2f}s (>=5s)"
