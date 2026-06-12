"""B056 F003 — /api/paper/* routes (auth, strategies, activate, view).

End-to-end through the real ``DbPriceProvider``: seed recommendation targets +
price snapshots, POST activate, then GET the 6-section view and assert it is
active with a summary, positions, and drift. Also covers the auth gate, the
inactive view, the unknown-strategy 400, and the double-activate 409.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
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
        {"email": ALLOWED_EMAIL, "sub": "paper-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_prices(symbol: str, closes: list[tuple[date, float]]) -> None:
    with Session(get_engine()) as session:
        for obs_date, close in closes:
            session.add(
                PriceSnapshot(
                    id=uuid4(),
                    symbol=symbol,
                    obs_date=obs_date,
                    close=close,
                    source="test",
                    fetched_at=datetime(2026, 6, 12, tzinfo=UTC),
                )
            )
        session.commit()


def _seed_targets() -> None:
    with Session(get_engine()) as session:
        RecommendationSnapshotRepository(session).save_batch(
            as_of_date=date(2026, 3, 31),
            rows=[
                {"symbol": "AAA", "sleeve": "m", "target_weight": 0.6},
                {"symbol": "BBB", "sleeve": "m", "target_weight": 0.4},
            ],
            master_meta={"data_source": "real"},
        )
        session.commit()


def _seed_world() -> None:
    _seed_targets()
    d1, d2 = date(2026, 6, 11), date(2026, 6, 12)
    _seed_prices("AAA", [(d1, 99.0), (d2, 100.0)])
    _seed_prices("BBB", [(d1, 49.0), (d2, 50.0)])
    _seed_prices("SPY", [(d1, 398.0), (d2, 400.0)])


def test_paper_requires_auth(initialised_db: str) -> None:  # noqa: ARG001
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/paper/strategies").status_code == 401


def test_strategies_lists_master(initialised_db: str) -> None:  # noqa: ARG001
    payload = _authed_client().get("/api/paper/strategies").json()
    ids = {s["strategy_id"]: s for s in payload["strategies"]}
    assert "master_portfolio" in ids
    assert ids["master_portfolio"]["name"] == "旗舰组合"
    assert ids["master_portfolio"]["has_account"] is False


def test_view_inactive_when_no_account(initialised_db: str) -> None:  # noqa: ARG001
    payload = _authed_client().get("/api/paper/master_portfolio").json()
    assert payload["active"] is False
    assert payload["summary"] is None


def test_activate_unknown_strategy_400(initialised_db: str) -> None:  # noqa: ARG001
    resp = _authed_client().post(
        "/api/paper/activate", json={"strategy_id": "nope"}
    )
    assert resp.status_code == 400


def test_activate_then_view_is_active(initialised_db: str) -> None:  # noqa: ARG001
    _seed_world()
    client = _authed_client()

    activate = client.post(
        "/api/paper/activate",
        json={"strategy_id": "master_portfolio", "initial_capital": 100_000.0},
    )
    assert activate.status_code == 200
    body = activate.json()
    assert body["activated"] is True and body["positions"] == 2

    view = client.get("/api/paper/master_portfolio").json()
    assert view["active"] is True
    assert view["strategy_name"] == "旗舰组合"
    assert view["summary"]["initial_capital"] == pytest.approx(100_000.0)
    symbols = {p["symbol"] for p in view["positions"]}
    assert symbols == {"AAA", "BBB"}
    # Drift entries exist for the target symbols.
    assert {d["symbol"] for d in view["drift"]} == {"AAA", "BBB"}

    # Activating again conflicts.
    again = client.post(
        "/api/paper/activate", json={"strategy_id": "master_portfolio"}
    )
    assert again.status_code == 409
