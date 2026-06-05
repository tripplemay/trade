"""B037 F001 — GET /api/home endpoint.

Pins the auth gate, the structured payload shape (nav / day_pnl /
sleeves), and the v0.9.32 §12.10 request-path self-containment (the Home
request path reads the DB only — no repo-root fixture / file reads).
"""

from __future__ import annotations

import ast
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "home-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_marked_holding(session: Session) -> None:
    session.add(
        Account(
            account_id="research", name="Research", base_currency="USD",
            cash=1000.0, equity_value=5000.0, as_of_date=date(2026, 6, 5),
        )
    )
    session.add(
        AccountSnapshot(
            id="snap-1", snapshot_at=datetime(2026, 6, 5, tzinfo=None),
            cash=1000.0, base_currency="USD",
            positions=[{"symbol": "AAPL", "shares": 10, "avg_cost": 150, "sleeve": "regime"}],
            source="bootstrap", created_at=datetime(2026, 6, 5, tzinfo=None),
        )
    )
    for d, c in [(date(2026, 6, 3), 192.0), (date(2026, 6, 4), 195.0)]:
        session.add(
            PriceSnapshot(
                id=uuid4(), symbol="AAPL", obs_date=d, close=c,
                source="tiingo", fetched_at=datetime(2026, 6, 5, tzinfo=UTC),
            )
        )
    session.commit()


def test_home_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/home").status_code == 401


def test_home_payload_shape_and_values(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_marked_holding(session)
    payload = _authed_client().get("/api/home").json()
    assert set(payload.keys()) == {"nav", "day_pnl", "sleeves"}
    assert payload["nav"] == 6000.0
    assert payload["day_pnl"]["value"] == 30.0  # 10 * (195 - 192)
    sleeve_keys = {k for s in payload["sleeves"] for k in s}
    assert sleeve_keys == {"sleeve", "nav_share", "day_pnl", "positions_summary"}
    regime = next(s for s in payload["sleeves"] if s["sleeve"] == "regime")
    assert regime["day_pnl"]["value"] == 30.0


def test_home_empty_state(initialised_db: str) -> None:
    payload = _authed_client().get("/api/home").json()
    assert payload["nav"] == 0.0
    assert payload["day_pnl"] is None


def test_home_request_self_contained() -> None:
    """v0.9.32 §12.10 — the /home request-path modules must not read
    repo-root fixtures or import pandas / the scripts package. Data comes
    from the DB only (price_snapshot + account snapshot)."""

    request_path = [
        BACKEND_ROOT / "workbench_api" / "schemas" / "home.py",
        BACKEND_ROOT / "workbench_api" / "services" / "home.py",
        BACKEND_ROOT / "workbench_api" / "services" / "prices_provider.py",
        BACKEND_ROOT / "workbench_api" / "routes" / "home.py",
        BACKEND_ROOT / "workbench_api" / "db" / "repositories" / "price_snapshot.py",
        BACKEND_ROOT / "workbench_api" / "db" / "models" / "price_snapshot.py",
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
