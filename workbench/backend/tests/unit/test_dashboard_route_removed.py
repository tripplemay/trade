"""B049 F003 regression — the dead /api/dashboard route is gone, NAV preserved.

The dashboard route had zero frontend runtime consumers (only OpenAPI-generated
types). B049 F003 removed the route + service + filesystem scanner and relocated
the one genuinely-shared helper (`_aggregate_nav` → `services.nav.aggregate_nav`,
reused by Home). This pins both halves so a future re-add or a botched relocation
is caught:

1. ``GET /api/dashboard`` is no longer registered (404, not 200/401).
2. ``services.nav.aggregate_nav`` still sums cash + equity (Home's NAV source).
3. The removed modules stay removed.
"""

from __future__ import annotations

import importlib
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.observability.active_users import active_users
from workbench_api.services.nav import aggregate_nav
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
        {"email": ALLOWED_EMAIL, "sub": "dash-removed-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_dashboard_route_is_removed(initialised_db: str) -> None:
    """A removed route returns 404 even for an authenticated user (a still-wired
    auth-gated route would 401 anon / 200 authed — neither must happen)."""

    client = _authed_client()
    assert client.get("/api/dashboard").status_code == 404


def test_nav_helper_still_aggregates_cash_plus_equity(initialised_db: str) -> None:
    engine = get_engine()
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(
            Account(
                account_id="acct-1",
                name="Test",
                base_currency="USD",
                cash=10_000.0,
                equity_value=42_500.50,
                as_of_date=date(2026, 5, 17),
            )
        )
        session.commit()
        assert aggregate_nav(session) == 52_500.50


@pytest.mark.parametrize(
    "module",
    [
        "workbench_api.routes.dashboard",
        "workbench_api.services.dashboard",
        "workbench_api.schemas.dashboard",
        "workbench_api.services.reports_scanner",
    ],
)
def test_dead_dashboard_modules_are_removed(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
