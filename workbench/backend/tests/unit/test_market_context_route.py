"""B035 F003 — GET /api/market-context endpoint.

Pins the auth gate, the catalog-ordered 6-series payload (empty + seeded),
the exact structured field set, catalog↔loader-series parity, and the
v0.9.32 §12.10 request-path self-containment (no repo-root file reads).
"""

from __future__ import annotations

import ast
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.data.alpha_vantage_loader import ALPHA_VANTAGE_SERIES
from workbench_api.data.fred_loader import FRED_SERIES
from workbench_api.db.engine import get_engine
from workbench_api.db.models.market_context import MarketContextObservation
from workbench_api.market.catalog import SERIES_CATALOG
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SERIES_FIELDS = {
    "series_id",
    "source",
    "label",
    "latest_value",
    "latest_date",
}


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "mc-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed(series_id: str, source: str, obs_date: date, value: float) -> None:
    with Session(get_engine()) as session:
        session.add(
            MarketContextObservation(
                id=uuid4(),
                series_id=series_id,
                source=source,
                obs_date=obs_date,
                value=value,
                snapshot_path=f"{source}/{obs_date.isoformat()}/{series_id}.json",
                fetched_at=datetime(2026, 6, 4, tzinfo=UTC),
            )
        )
        session.commit()


def test_market_context_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/market-context").status_code == 401


def test_returns_all_catalog_series_empty_state(initialised_db: str) -> None:
    client = _authed_client()
    payload = client.get("/api/market-context").json()
    series = payload["series"]
    assert [s["series_id"] for s in series] == [e.series_id for e in SERIES_CATALOG]
    # No data ingested → all latest values null (empty state).
    assert all(s["latest_value"] is None and s["latest_date"] is None for s in series)


def test_returns_latest_values_when_seeded(initialised_db: str) -> None:
    _seed("DGS10", "fred", date(2026, 6, 2), 4.25)
    _seed("DGS10", "fred", date(2026, 6, 3), 4.28)  # newer → wins
    _seed("SPY", "alpha_vantage", date(2026, 6, 3), 580.5)
    client = _authed_client()
    by_id = {s["series_id"]: s for s in client.get("/api/market-context").json()["series"]}
    assert by_id["DGS10"]["latest_value"] == pytest.approx(4.28)
    assert by_id["DGS10"]["latest_date"] == "2026-06-03"
    assert by_id["DGS10"]["label"] == "10-Year Treasury Yield (%)"
    assert by_id["SPY"]["latest_value"] == pytest.approx(580.5)
    # A series with no data still appears, with nulls.
    assert by_id["VIXCLS"]["latest_value"] is None


def test_series_field_set_is_exactly_structured(initialised_db: str) -> None:
    client = _authed_client()
    payload = client.get("/api/market-context").json()
    assert set(payload.keys()) == {"series"}
    assert set(payload["series"][0].keys()) == EXPECTED_SERIES_FIELDS


def test_catalog_matches_loader_series() -> None:
    """The display catalog must cover exactly the loaders' series — drift
    guard so a new loader series can't silently miss the Home card."""

    catalog_ids = {e.series_id for e in SERIES_CATALOG}
    assert catalog_ids == set(FRED_SERIES) | set(ALPHA_VANTAGE_SERIES)


def test_request_path_is_self_contained() -> None:
    """v0.9.32 §12.10 — the /market-context request-path modules must not
    read repo-root fixtures or import pandas / the scripts package (the
    B034 production-500 failure class). Data comes from the DB + the
    in-package catalog only."""

    request_path = [
        BACKEND_ROOT / "workbench_api" / "market" / "catalog.py",
        BACKEND_ROOT / "workbench_api" / "schemas" / "market_context.py",
        BACKEND_ROOT / "workbench_api" / "services" / "market_context.py",
        BACKEND_ROOT / "workbench_api" / "routes" / "market_context.py",
        BACKEND_ROOT / "workbench_api" / "db" / "repositories" / "market_context.py",
    ]
    forbidden_substrings = ("data/fixtures", ".csv", "open(")
    for path in request_path:
        src = path.read_text(encoding="utf-8")
        for frag in forbidden_substrings:
            assert frag not in src, f"{path.name} reads a file ({frag!r}) on the request path"
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".", 1)[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert "pandas" not in imported, f"{path.name} imports pandas on the request path"
        assert "scripts" not in imported, f"{path.name} imports scripts on the request path"
