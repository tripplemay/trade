"""B022 F006 vertical slice — ``/api/dashboard`` handler + service tests.

The route is auth-gated, reads SQLite via the AccountRepository session,
and surfaces recent reports off the filesystem (``WORKBENCH_REPORTS_DIR``).
This file pins the three contracts a future regression could break:

1. Auth boundary — anonymous traffic must 401, never leak a payload.
2. Schema fidelity — every DashboardResponse field is present and typed.
3. Empty-state behaviour — missing accounts → nav=0.0; missing reports
   dir → recent_reports=[]; action_items always []. The Dashboard page
   relies on these being lists, not nulls.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_active_users() -> None:
    active_users.clear()


def _authed_client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "dashboard-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _insert_account(account_id: str, cash: float, equity: float) -> None:
    """Persist a row through the ORM so the dashboard service can read it
    via the same engine the FastAPI dependency yields."""

    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            Account(
                account_id=account_id,
                name="Test",
                base_currency="USD",
                cash=cash,
                equity_value=equity,
                as_of_date=date(2026, 5, 17),
            )
        )
        session.commit()


def test_dashboard_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    """No session cookie → 401, never the dashboard payload."""

    settings = Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    response = client.get("/api/dashboard")
    assert response.status_code == 401, response.text


def test_dashboard_returns_schema_with_zero_state(
    initialised_db: str, tmp_path: Path
) -> None:
    """No accounts + empty reports dir → all empty-state defaults.

    The response shape must still be complete (every field present)
    because the frontend uses keyed access and Pydantic would 500 if a
    required field were missing.
    """

    settings = Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    client = _authed_client(settings)
    response = client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert payload["nav"] == 0.0
    assert payload["master_drawdown"] == 0.0
    assert payload["kill_switch_threshold"] == 0.2
    assert payload["days_to_next_rebalance"] == 0
    assert payload["last_rebalance"] is None
    assert payload["recent_reports"] == []
    assert payload["action_items"] == []


def test_dashboard_nav_aggregates_cash_plus_equity(
    initialised_db: str, tmp_path: Path
) -> None:
    """NAV must equal cash + equity across all accounts (single row in MVP)."""

    _insert_account("acct-1", cash=10_000.0, equity=42_500.50)
    settings = Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    client = _authed_client(settings)
    payload = client.get("/api/dashboard").json()
    assert payload["nav"] == 52500.50


def test_dashboard_surfaces_recent_reports_from_disk(
    initialised_db: str, tmp_path: Path
) -> None:
    """Markdown files in WORKBENCH_REPORTS_DIR materialise as RecentReport rows.

    Date in filename anchors sort order; only top-N (default 10) ship.
    """

    (tmp_path / "B019-retune-signoff-2026-05-15.md").write_text("body", encoding="utf-8")
    (tmp_path / "B018-something-review-2026-05-01.md").write_text("body", encoding="utf-8")

    settings = Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    client = _authed_client(settings)
    payload = client.get("/api/dashboard").json()
    reports = payload["recent_reports"]
    assert len(reports) >= 2
    # Most recent date first.
    assert reports[0]["date"] == "2026-05-15"
    assert "B019" in reports[0]["id"]
    assert reports[0]["status"] == "signoff"
    assert reports[1]["date"] == "2026-05-01"
    assert reports[1]["status"] == "review"


def test_dashboard_handles_missing_reports_dir(
    initialised_db: str, tmp_path: Path
) -> None:
    """A non-existent reports directory degrades to [] rather than 500."""

    missing = tmp_path / "does-not-exist"
    settings = Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(missing),
    )
    client = _authed_client(settings)
    payload = client.get("/api/dashboard").json()
    assert payload["recent_reports"] == []
