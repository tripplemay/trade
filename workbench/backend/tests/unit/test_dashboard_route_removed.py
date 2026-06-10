"""B049 F003 regression — the dead /api/dashboard route is gone, NAV preserved.

The dashboard route had zero frontend runtime consumers (only OpenAPI-generated
types). B049 F003 removed the route + service + filesystem scanner and relocated
the one genuinely-shared helper (`_aggregate_nav` → `services.nav.aggregate_nav`,
reused by Home). This pins both halves so a future re-add or a botched relocation
is caught:

1. ``GET /api/dashboard`` is no longer registered (404, not 200/401).
2. ``services.nav.aggregate_nav`` still aggregates NAV (Home's NAV source) —
   since B051 from the latest ``account_snapshot`` (cash + mark-to-market),
   no longer ``account.cash + equity_value``.
3. The removed modules stay removed.
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Iterable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.observability.active_users import active_users
from workbench_api.services.nav import aggregate_nav
from workbench_api.services.prices_provider import PriceMark
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


class _FakeProvider:
    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = marks

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {s.upper(): self._marks[s.upper()] for s in symbols if s.upper() in self._marks}


def test_nav_helper_aggregates_snapshot_mark_to_market(initialised_db: str) -> None:
    """B051: NAV = latest account_snapshot cash + Σ shares × latest close."""

    engine = get_engine()
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        at = datetime(2026, 5, 17, 12, 0, 0)
        session.add(
            AccountSnapshot(
                id="dash-snap",
                snapshot_at=at,
                cash=10_000.0,
                base_currency="USD",
                positions=[{"symbol": "AAPL", "shares": 100, "avg_cost": 150.0}],
                source="ui_edit",
                created_at=at,
            )
        )
        session.commit()
        provider = _FakeProvider({"AAPL": PriceMark(latest_close=425.005, prior_close=420.0)})
        # 10000 + 100 × 425.005 = 52500.50
        assert aggregate_nav(session, provider) == 52_500.50


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
