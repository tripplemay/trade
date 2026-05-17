"""B022 F002 — schema registration + auth gate for the 7 stub routes.

Three things are asserted per route:

1. Anonymous access (no session cookie) gets ``401`` — the auth dependency
   is wired before the 501 raise, so the gate cannot accidentally regress
   into an auth-open state when F006-F012 fill in the bodies.
2. Authenticated access gets ``501`` with the "B022-F00x" marker — proves
   F002 only registers the surface and signals which feature finishes it.
3. The OpenAPI document carries the response schemas — proves the
   ``response_model=`` argument actually registered the Pydantic models so
   the ``openapi-typescript`` pipeline emits them into ``api.ts``.
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
        {"email": ALLOWED_EMAIL, "sub": "user-1", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


# (method, path, body, expected feature marker, expected success status_code)
STUB_ROUTES: list[tuple[str, str, dict[str, Any] | None, str, int]] = [
    ("get", "/api/dashboard", None, "F006", 501),
    ("get", "/api/strategies", None, "F007", 501),
    ("get", "/api/strategies/B013-quarterly", None, "F007", 501),
    (
        "post",
        "/api/backtests/run",
        {
            "strategy_id": "B013-quarterly",
            "snapshot_id": "snap-1",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
            "parameters": {},
        },
        "F008",
        501,
    ),
    ("get", "/api/backtests/run-1", None, "F008", 501),
    ("get", "/api/reports", None, "F009", 501),
    ("get", "/api/reports/B019-retune", None, "F009", 501),
    ("get", "/api/docs/docs/specs/B019.md", None, "F009", 501),
    ("get", "/api/recommendations/current", None, "F010", 501),
    (
        "post",
        "/api/recommendations/export-ticket",
        {"as_of_date": "2026-05-17"},
        "F010",
        501,
    ),
    ("get", "/api/snapshots", None, "F011", 501),
    ("post", "/api/snapshots/refresh", None, "F011", 501),
    ("get", "/api/backlog", None, "F012", 501),
    ("post", "/api/backlog", {"title": "X"}, "F012", 501),
    ("patch", "/api/backlog/BL-1", {"title": "Y"}, "F012", 501),
    ("delete", "/api/backlog/BL-1", None, "F012", 501),
]


@pytest.mark.parametrize("method, path, body, marker, _ok_status", STUB_ROUTES)
def test_stub_route_rejects_anonymous(
    initialised_db: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    marker: str,
    _ok_status: int,
) -> None:
    """No session cookie → 401, never the underlying 501 marker.

    Without this test a maintainer could accidentally drop the auth
    dependency while filling in the F006-F012 bodies and the route would
    silently start serving anonymous traffic.
    """

    del marker, _ok_status
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    response = client.request(method, path, json=body)
    assert response.status_code == 401, (path, response.text)


@pytest.mark.parametrize("method, path, body, marker, ok_status", STUB_ROUTES)
def test_stub_route_returns_501_with_marker(
    initialised_db: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    marker: str,
    ok_status: int,
) -> None:
    """Authenticated request → canonical 501 string naming the F006-F012
    feature that fills in the body. F006-F012 acceptance includes flipping
    this test to assert the real response shape.
    """

    del ok_status
    client = _authed_client()
    response = client.request(method, path, json=body)
    assert response.status_code == 501, (path, response.text)
    detail = response.json()["detail"]
    assert marker in detail, (path, detail)


def test_openapi_registers_all_b022_schemas(initialised_db: str) -> None:
    """The schemas live under ``components.schemas`` of the OpenAPI doc;
    ``openapi-typescript`` reads them from there.
    """

    client = TestClient(create_app())
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    expected = {
        "DashboardResponse",
        "LastRebalance",
        "RecentReport",
        "ActionItem",
        "StrategyListResponse",
        "StrategyDetail",
        "StrategySummary",
        "StrategyProvenance",
        "BacktestRunRequest",
        "BacktestRunResponse",
        "BacktestMetrics",
        "EquitySample",
        "AllocationBar",
        "BacktestTrade",
        "ReportListResponse",
        "ReportSummary",
        "ReportDetail",
        "ReportTable",
        "DocsResponse",
        "RecommendationsResponse",
        "TargetPosition",
        "GateCheck",
        "WashSaleFlag",
        "ExportTicketRequest",
        "ExportTicketResponse",
        "SnapshotListResponse",
        "SnapshotSummary",
        "SnapshotRefreshResponse",
        "BacklogListResponse",
        "BacklogEntry",
        "BacklogCreateRequest",
        "BacklogUpdateRequest",
        "BacklogDeleteResponse",
    }
    missing = expected - schemas.keys()
    assert missing == set(), f"Missing schemas: {sorted(missing)}"
