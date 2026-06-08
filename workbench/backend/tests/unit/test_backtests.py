"""B047 F003 — async backtest request path (enqueue + poll).

Replaces the B022 F008 synchronous synthetic coverage. The request path now:

* Auth gate — anon → 401.
* POST /run → 202 + {run_id, status: 'queued'} (no result yet; no trade import).
* GET /{run_id} reflects DB state — queued (no result), then done (result) /
  error after the worker writes it.
* Unknown strategy_id → 404; unknown run_id → 404.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.backtest_run import BacktestRunRepository
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()


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


def test_backtest_run_enqueues_and_returns_202_queued(initialised_db: str) -> None:
    client = _authed_client()
    response = client.post("/api/backtests/run", json=SAMPLE_REQUEST)
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "queued"
    assert isinstance(payload["run_id"], str) and payload["run_id"]
    # No result while queued — the worker fills it in.
    assert payload["metrics"] is None
    assert payload["equity"] == []

    # GET reflects the queued state (worker hasn't run in the test).
    fetched = client.get(f"/api/backtests/{payload['run_id']}").json()
    assert fetched["status"] == "queued"
    assert fetched["metrics"] is None


def test_backtest_get_reflects_done_result(initialised_db: str) -> None:
    """Once the worker writes a result, GET surfaces the mapped done payload."""

    client = _authed_client()
    run_id = client.post("/api/backtests/run", json=SAMPLE_REQUEST).json()["run_id"]

    # Simulate the worker: claim + save a result.
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        repo.claim_next_queued()
        repo.save_result(
            run_id,
            metrics={"cagr": 0.12, "sharpe": 1.3, "sortino": None,
                     "max_drawdown": -0.15, "turnover": 3.0, "win_rate": None},
            equity=[{"date": "2024-03-31", "nav": 10500.0}],
            allocations=[{"date": "2024-03-31", "weights": {"SPY": 1.0}}],
            trades=[{"date": "2024-04-01", "symbol": "SPY", "side": "buy",
                     "quantity": 1.0, "price": 100.0, "notional": 100.0}],
            report_markdown="# Master Portfolio Report",
        )
        session.commit()

    fetched = client.get(f"/api/backtests/{run_id}").json()
    assert fetched["status"] == "done"
    assert fetched["metrics"]["cagr"] == 0.12
    assert fetched["equity"][0]["nav"] == 10500.0
    assert fetched["trades"][0]["symbol"] == "SPY"
    assert fetched["report_markdown"].startswith("# Master Portfolio Report")


def test_backtest_get_reflects_error(initialised_db: str) -> None:
    client = _authed_client()
    run_id = client.post("/api/backtests/run", json=SAMPLE_REQUEST).json()["run_id"]
    with Session(get_engine()) as session:
        repo = BacktestRunRepository(session)
        repo.claim_next_queued()
        repo.save_error(run_id, "no real price data available")
        session.commit()
    fetched = client.get(f"/api/backtests/{run_id}").json()
    assert fetched["status"] == "error"
    assert "no real price data" in fetched["error"]


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
    assert client.get("/api/backtests/no-such-run").status_code == 404
