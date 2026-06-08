"""B047 F004 — /api/reports surfaces DB-backed INVESTMENT reports.

Replaces the B022 F009 filesystem-scan coverage. The user Reports page now
lists canonical Master/sleeve backtest reports (``kind='investment'``) written
by the canonical job — the development sign-offs under ``docs/test-reports/``
are filtered OUT of the user list (still reachable via /api/docs deep links).

Pinned: auth gate; list shows only investment reports; empty → empty list;
detail returns the stored markdown + extracts tables + maps the stored metrics;
unknown slug → 404.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.investment_report import InvestmentReportRepository
from workbench_api.observability.active_users import active_users
from workbench_api.services.reports import _extract_tables
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
        {"email": ALLOWED_EMAIL, "sub": "reports-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


SAMPLE_MD = """# Master Portfolio Report

## Summary
- CAGR: 0.12

| metric | value |
|---|---:|
| CAGR | 0.12 |
| Sharpe | 1.30 |
"""


def _seed_report(
    *, strategy_id: str = "master_portfolio", as_of: date = date(2026, 3, 31)
) -> str:
    with Session(get_engine()) as session:
        row = InvestmentReportRepository(session).upsert_report(
            strategy_id=strategy_id,
            as_of_date=as_of,
            title="Master Portfolio — Quarterly Backtest",
            markdown=SAMPLE_MD,
            metrics={"cagr": 0.12, "sharpe": 1.3, "sortino": None,
                     "max_drawdown": -0.2, "turnover": 3.0, "win_rate": None},
            computed_at=datetime(2026, 6, 8, tzinfo=UTC),
        )
        session.commit()
        return row.slug


def test_reports_list_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    assert TestClient(app).get("/api/reports").status_code == 401


def test_reports_list_shows_investment_reports(initialised_db: str) -> None:
    _seed_report()
    client = _authed_client()
    payload = client.get("/api/reports").json()
    assert len(payload["reports"]) == 1
    row = payload["reports"][0]
    assert row["kind"] == "investment"
    assert row["slug"] == "master_portfolio-2026-03-31"
    assert row["date"] == "2026-03-31"
    assert "Master Portfolio" in row["title"]


def test_reports_list_empty_returns_empty_list(initialised_db: str) -> None:
    # No canonical reports + the dev sign-offs are NOT surfaced here.
    assert _authed_client().get("/api/reports").json()["reports"] == []


def test_reports_detail_returns_markdown_tables_and_metrics(initialised_db: str) -> None:
    slug = _seed_report()
    payload = _authed_client().get(f"/api/reports/{slug}").json()
    assert payload["kind"] == "investment"
    assert payload["body_markdown"].startswith("# Master Portfolio Report")
    assert len(payload["tables"]) >= 1
    # Metrics mapped from the stored metrics_json (+ derived calmar).
    assert payload["metrics"]["cagr"] == 0.12
    assert payload["metrics"]["sharpe"] == 1.3
    assert payload["metrics"]["calmar"] == pytest.approx(0.12 / 0.2)


def test_reports_detail_404_for_unknown_slug(initialised_db: str) -> None:
    assert _authed_client().get("/api/reports/nope-2026-01-01").status_code == 404


def test_extract_tables_unit_handles_no_tables() -> None:
    assert _extract_tables("# Heading\n\nNo tables here.") == []
