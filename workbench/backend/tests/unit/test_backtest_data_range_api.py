"""B047-OPS2 F001 — GET /api/backtests/data-range (request-path, read-only).

The endpoint exposes the real data-coverage window so the frontend picks a valid
default range and clamps the picker. It reads the ``backtest_data_window``
singleton ONLY (no ``trade`` import, §12.10.2) and returns all-``null`` when no
data-refresh has run yet (empty state).
"""

from __future__ import annotations

import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.backtest_data_window import (
    BacktestDataWindowRepository,
)
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
        {"email": ALLOWED_EMAIL, "sub": "range-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_data_range_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/backtests/data-range").status_code == 401


def test_data_range_empty_returns_nulls(initialised_db: str) -> None:
    """No data-refresh yet → all-null (frontend shows the empty state)."""

    client = _authed_client()
    response = client.get("/api/backtests/data-range")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "data_start": None,
        "data_end": None,
        "min_usable_start": None,
    }


def test_data_range_returns_window(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        BacktestDataWindowRepository(session).upsert_window(
            data_start=date(2021, 6, 1),
            data_end=date(2026, 6, 8),
            first_usable_signal_date=date(2022, 4, 2),
        )
        session.commit()

    client = _authed_client()
    payload = client.get("/api/backtests/data-range").json()
    assert payload["data_start"] == "2021-06-01"
    assert payload["data_end"] == "2026-06-08"
    # min_usable_start is the lookback-safe floor (the frontend clamps to it).
    assert payload["min_usable_start"] == "2022-04-02"


def test_data_range_not_shadowed_by_run_id_route(initialised_db: str) -> None:
    """The literal /data-range path must resolve to the window endpoint, not be
    swallowed by GET /{run_id} (which would 404 the unknown 'data-range' id)."""

    client = _authed_client()
    assert client.get("/api/backtests/data-range").status_code == 200
