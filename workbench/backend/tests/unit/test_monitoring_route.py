"""B080 F001 — /api/monitoring/trials route + worker auto-registration.

Drives the read-only trial-registry API through the real FastAPI TestClient
(auth-gated, DSR counts) and pins the backtest worker's auto-log of a completed
run as a ``verdict=NA`` trial carrying the surfaced parameter_hash + realized
window.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.backtests.worker import _register_trial
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.settings import Settings, get_settings

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
        {"email": ALLOWED_EMAIL, "sub": "b080-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_trials_route_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    resp = TestClient(app).get("/api/monitoring/trials")
    assert resp.status_code == 401


def test_trials_route_returns_registry_and_dsr_counts(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = TrialRegistryRepository(session)
        repo.register(
            id="t1", batch="B066", strategy_id="cn_attack_pure_momentum", verdict="INCONCLUSIVE"
        )
        repo.register(id="t2", batch="B070", strategy_id="cn_attack_pure_momentum", verdict="GO")
        repo.register(id="t3", batch="B063", strategy_id="hk_china_real", verdict="NO_GO")
        session.commit()

    resp = _authed_client().get("/api/monitoring/trials")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["counts_by_strategy"]["cn_attack_pure_momentum"] == 2  # the DSR N
    assert body["counts_by_strategy"]["hk_china_real"] == 1
    assert {t["id"] for t in body["trials"]} == {"t1", "t2", "t3"}
    verdicts = {t["id"]: t["verdict"] for t in body["trials"]}
    assert verdicts["t2"] == "GO"


def test_worker_registers_completed_run_as_trial(initialised_db: str) -> None:
    run = SimpleNamespace(
        run_id="run-xyz",
        strategy_id="master_portfolio",
        params={"start_date": "2020-01-01"},
    )
    mapped = {
        "metrics": {"cagr": 0.11, "sharpe": 0.9},
        "equity": [{"date": "2020-01-02", "nav": 1.0}, {"date": "2026-03-31", "nav": 2.1}],
        "parameter_hash": "abc123",
    }
    with Session(get_engine()) as session:
        _register_trial(session, run, mapped)
        session.commit()
        repo = TrialRegistryRepository(session)
        rows = repo.list_by_strategy("master_portfolio")
        assert len(rows) == 1
        row = rows[0]
        assert row.id == "run-run-xyz"
        assert row.verdict == "NA"
        assert row.parameter_hash == "abc123"
        assert row.metrics == {"cagr": 0.11, "sharpe": 0.9}
        assert row.window_start is not None and row.window_start.isoformat() == "2020-01-02"
        assert row.window_end is not None and row.window_end.isoformat() == "2026-03-31"
