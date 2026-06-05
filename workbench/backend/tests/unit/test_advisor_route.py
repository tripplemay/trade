"""B036 F003 — GET /api/advisor endpoint + §12.10 self-containment."""

from __future__ import annotations

import ast
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.advisor_recommendation import (
    STATUS_INSUFFICIENT_GROUNDING,
    STATUS_OK,
    AdvisorRecommendation,
)
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_ITEM_FIELDS = {
    "sleeve",
    "advice",
    "rationale",
    "references",
    "status",
    "generated_at",
}


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "adv-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed(
    sleeve: str,
    *,
    status: str,
    advice: str = "Stay diversified.",
    refs: list[dict[str, object]] | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AdvisorRecommendation(
                id=uuid4(),
                sleeve=sleeve,
                advice_json={"advice": advice, "rationale": "r"}
                if status == STATUS_OK
                else {"status": STATUS_INSUFFICIENT_GROUNDING},
                quant_signal_sha="sha256:abc",
                references_json=refs if refs is not None else [],
                model="claude-haiku-4.5",
                status=status,
                generated_at=datetime(2026, 6, 5, 1, 0, tzinfo=UTC),
            )
        )
        session.commit()


def test_advisor_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/advisor").status_code == 401


def test_advisor_empty_when_no_recommendations(initialised_db: str) -> None:
    payload = _authed_client().get("/api/advisor").json()
    assert payload == {"sleeves": []}


def test_advisor_returns_ok_and_insufficient_states(initialised_db: str) -> None:
    _seed(
        "satellite_us_quality",
        status=STATUS_OK,
        refs=[{"quant_signal_sha": "sha256:abc", "news_urls": ["https://a.example/1"]}],
    )
    _seed("regime", status=STATUS_INSUFFICIENT_GROUNDING)
    by_sleeve = {
        s["sleeve"]: s for s in _authed_client().get("/api/advisor").json()["sleeves"]
    }
    ok = by_sleeve["satellite_us_quality"]
    assert ok["status"] == STATUS_OK
    assert ok["advice"] == "Stay diversified."
    assert ok["references"][0]["quant_signal_sha"] == "sha256:abc"
    assert ok["references"][0]["news_urls"] == ["https://a.example/1"]
    assert by_sleeve["regime"]["status"] == STATUS_INSUFFICIENT_GROUNDING
    assert by_sleeve["regime"]["references"] == []


def test_advisor_item_field_set(initialised_db: str) -> None:
    _seed("satellite_us_quality", status=STATUS_OK)
    payload = _authed_client().get("/api/advisor").json()
    assert set(payload.keys()) == {"sleeves"}
    assert set(payload["sleeves"][0].keys()) == EXPECTED_ITEM_FIELDS


def test_advisor_request_self_contained() -> None:
    """§12.10 — the /advisor request path must not read repo-root fixtures
    or import pandas / scripts (the B034 production-500 failure class)."""

    request_path = [
        BACKEND_ROOT / "workbench_api" / "schemas" / "advisor.py",
        BACKEND_ROOT / "workbench_api" / "services" / "advisor.py",
        BACKEND_ROOT / "workbench_api" / "routes" / "advisor.py",
    ]
    for path in request_path:
        src = path.read_text(encoding="utf-8")
        for frag in ("data/fixtures", ".csv", "open("):
            assert frag not in src, f"{path.name} reads a file ({frag!r}) on the request path"
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".", 1)[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert "pandas" not in imported
        assert "scripts" not in imported
