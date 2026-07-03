"""B079 F002/F003 — route-level acceptance: enriched API responses carry names.

验收即代码 (generator §31): sinks the F004 name-display check into permanent CI
regression. Drives ``GET /api/execution/account/latest`` through the real FastAPI
TestClient (auth override, in-memory DB) and asserts each held position surfaces
its display name — the US ticker via the curated static seed, an A-share ticker
via the live-captured Chinese name (overriding the English fallback), and a
synthetic symbol via the graceful ``null`` fallback (缺失纯 code). This is the
closest automated proxy to F004's manual L2 check; Codex still owns the
independent real-machine judgment + screenshots.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import (
    DEFAULT_STRATEGY_ID,
    AccountSnapshot,
)
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.symbol_name import SymbolNameRepository
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
        {"email": ALLOWED_EMAIL, "sub": "b079-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed(session: Session) -> None:
    at = datetime(2026, 7, 3, 12, 0, tzinfo=UTC).replace(tzinfo=None)
    AccountSnapshotRepository(session).upsert(
        AccountSnapshot(
            id="snap-b079-route",
            snapshot_at=at,
            strategy_id=DEFAULT_STRATEGY_ID,
            cash=Decimal("1000"),
            base_currency="USD",
            positions=[
                {"symbol": "AAPL", "shares": 10.0, "avg_cost": 150.0},
                {"symbol": "600519.SH", "shares": 5.0, "avg_cost": 1600.0},
                {"symbol": "ZQFAKE", "shares": 1.0, "avg_cost": 1.0},
            ],
            source="ui_edit",
            created_at=at,
        )
    )
    # A live-captured A-share Chinese name overrides the curated English fallback.
    SymbolNameRepository(session).upsert_names(
        {"600519.SH": "贵州茅台"}, source="akshare_spot"
    )
    session.commit()


def test_account_latest_response_carries_display_names(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(session)

    resp = _authed_client().get("/api/execution/account/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    names = {p["symbol"]: p.get("name") for p in body["positions"]}
    assert names["AAPL"] == "Apple Inc."  # curated static seed (US equity)
    assert names["600519.SH"] == "贵州茅台"  # live A-share Chinese wins over English
    assert names["ZQFAKE"] is None  # no name anywhere → null (raw-code fallback)
