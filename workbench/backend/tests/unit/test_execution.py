"""B023 F002 — ``/api/execution/*`` contract tests.

Covers the three F002 endpoints (position-diff / account/latest /
account PUT) plus the validation surface on the PUT body. The diff
math is exercised end-to-end via a seeded snapshot + the existing
recommendations service so the sign-correctness invariant
(``delta_shares > 0 when target > current``) is tested through real
data, not mocks.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_active_users() -> None:
    active_users.clear()


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )


def _authed_client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "execution-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_account(cash: float = 100_000.0) -> None:
    """Ensure the recommendations service sees account_present=True."""

    with Session(get_engine()) as session:
        session.add(
            Account(
                account_id="research-mvp",
                name="Research MVP",
                base_currency="USD",
                cash=Decimal(str(cash)),
                equity_value=Decimal("0"),
                as_of_date=date(2026, 5, 18),
            )
        )
        session.commit()


def _seed_snapshot(
    *,
    snap_id: str = "snap-test-1",
    cash: float = 50_000.0,
    positions: list[dict[str, Any]] | None = None,
    snapshot_at: datetime | None = None,
    source: str = "bootstrap",
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=snap_id,
                snapshot_at=snapshot_at or datetime(2026, 5, 18, 10, 0, 0),
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions or [],
                source=source,
                created_at=snapshot_at or datetime(2026, 5, 18, 10, 0, 0),
            )
        )
        session.commit()


def _seed_price_snapshot(symbol: str, latest_close: float, prior_close: float) -> None:
    """Two closes so DbPriceProvider yields a mark. B046 F001 — the position diff
    is mark-to-market, so a symbol needs a price_snapshot mark to be priced
    (else it degrades to unmatched / reference_price None)."""

    with Session(get_engine()) as session:
        for obs_date, close in [
            (date(2026, 5, 16), prior_close),
            (date(2026, 5, 17), latest_close),
        ]:
            session.add(
                PriceSnapshot(
                    id=uuid4(),
                    symbol=symbol.upper(),
                    obs_date=obs_date,
                    close=close,
                    source="tiingo",
                    fetched_at=datetime(2026, 5, 18, tzinfo=UTC),
                )
            )
        session.commit()


def test_position_diff_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/position-diff")
    assert response.status_code == 401, response.text


def test_account_latest_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/account/latest")
    assert response.status_code == 401, response.text


def test_put_account_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.put(
        "/api/execution/account",
        json={"cash": 1, "base_currency": "USD", "positions": []},
    )
    assert response.status_code == 401, response.text


def test_account_latest_empty_state(initialised_db: str, tmp_path: Path) -> None:
    """No snapshot rows → null response (frontend renders empty state)."""

    client = _authed_client(_settings(tmp_path))
    response = client.get("/api/execution/account/latest")
    assert response.status_code == 200, response.text
    assert response.json() is None


def test_position_diff_empty_state(initialised_db: str, tmp_path: Path) -> None:
    """No account + no snapshot → schema-complete payload with empty
    diff/target lists (frontend keys never see undefined)."""

    client = _authed_client(_settings(tmp_path))
    response = client.get("/api/execution/position-diff")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current"] is None
    assert payload["target"] == []
    assert payload["diff"] == []
    assert payload["unmatched"] == []
    assert payload["total_equity"] == 0.0
    assert isinstance(payload["as_of_date"], str)


def test_put_account_inserts_snapshot(initialised_db: str, tmp_path: Path) -> None:
    """PUT body persists a new snapshot row with source=ui_edit."""

    client = _authed_client(_settings(tmp_path))
    body = {
        "cash": 75_000.0,
        "base_currency": "USD",
        "positions": [
            {"symbol": "SPY", "shares": 100, "avg_cost": 500.0},
            {"symbol": "IEF", "shares": 50, "avg_cost": 94.0},
        ],
    }
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "ui_edit"
    assert payload["cash"] == 75_000.0
    assert payload["base_currency"] == "USD"
    assert len(payload["positions"]) == 2
    assert payload["id"] is not None
    assert payload["snapshot_at"] is not None

    # And GET /account/latest immediately reflects it.
    latest = client.get("/api/execution/account/latest").json()
    assert latest["id"] == payload["id"]
    assert latest["cash"] == 75_000.0
    symbols = {p["symbol"] for p in latest["positions"]}
    assert symbols == {"SPY", "IEF"}


def test_put_account_round_trips_sleeve_tag(initialised_db: str, tmp_path: Path) -> None:
    """B048 F002: the ui_edit write path persists the optional sleeve tag,
    and a tagless position reads back as None (schema-tolerant)."""

    client = _authed_client(_settings(tmp_path))
    body = {
        "cash": 50_000.0,
        "base_currency": "USD",
        "positions": [
            {"symbol": "SPY", "shares": 100, "avg_cost": 500.0, "sleeve": "momentum"},
            {"symbol": "GLD", "shares": 10, "avg_cost": 180.0, "sleeve": "risk_parity"},
            {"symbol": "IEF", "shares": 50, "avg_cost": 94.0},  # no tag
        ],
    }
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 200, response.text

    latest = client.get("/api/execution/account/latest").json()
    by_symbol = {p["symbol"]: p for p in latest["positions"]}
    assert by_symbol["SPY"]["sleeve"] == "momentum"
    assert by_symbol["GLD"]["sleeve"] == "risk_parity"
    # Tagless holding round-trips as null, not a fabricated tag.
    assert by_symbol["IEF"]["sleeve"] is None


def test_put_account_rejects_duplicate_symbols(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    body = {
        "cash": 10.0,
        "base_currency": "USD",
        "positions": [
            {"symbol": "SPY", "shares": 1, "avg_cost": 500.0},
            {"symbol": "spy", "shares": 1, "avg_cost": 500.0},  # case-insensitive dup
        ],
    }
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 422, response.text


def test_put_account_rejects_negative_cash(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    body = {"cash": -1, "base_currency": "USD", "positions": []}
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 422, response.text


def test_put_account_rejects_negative_shares(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    body = {
        "cash": 10.0,
        "base_currency": "USD",
        "positions": [{"symbol": "SPY", "shares": -1, "avg_cost": 500.0}],
    }
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 422, response.text


def _seed_recommendation_target(symbols: tuple[str, ...]) -> None:
    """B044: the recommendations target now comes from the precomputed
    recommendation_snapshot (not equal-weight). Seed an equal-weight target
    over ``symbols`` so the position-diff has target rows to compare against."""
    from datetime import date

    from workbench_api.db.repositories.recommendation_snapshot import (
        RecommendationSnapshotRepository,
    )

    weight = round(1.0 / len(symbols), 4)
    with Session(get_engine()) as session:
        RecommendationSnapshotRepository(session).save_batch(
            as_of_date=date(2024, 12, 31),
            rows=[
                {"symbol": s, "sleeve": "momentum", "target_weight": weight, "rationale": "t"}
                for s in symbols
            ],
            master_meta={"data_source": "fixture", "planning_weights": {}},
        )
        session.commit()


def test_position_diff_sign_correctness(initialised_db: str, tmp_path: Path) -> None:
    """delta_shares is positive when target_weight > current_weight.

    B044: the recommendations service reads the recommendation_snapshot; we
    seed a 4-symbol equal-weight target (B013/B014/B015/B016) + a tiny B013
    position so the diff row has a price reference and a positive delta.
    """

    _seed_account(cash=100_000.0)
    _seed_recommendation_target(("B013", "B014", "B015", "B016"))
    _seed_snapshot(
        cash=50_000.0,
        positions=[
            # 10 shares cost $500 but now mark at $600 (appreciated). B046 F001
            # prices the diff at market ($600), not cost — so total_equity is the
            # market-value NAV (50k + 10×600 = 56k) and reference_price is 600.
            {"symbol": "B013", "shares": 10, "avg_cost": 500.0},
        ],
    )
    _seed_price_snapshot("B013", latest_close=600.0, prior_close=580.0)
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/position-diff").json()
    assert payload["current"] is not None
    # Market-value NAV: cash 50k + 10 shares × $600 mark = 56k (NOT cost-basis).
    assert payload["total_equity"] == pytest.approx(50_000.0 + 10 * 600.0)

    matching = [r for r in payload["diff"] if r["symbol"] == "B013"]
    assert len(matching) == 1
    row = matching[0]
    assert row["current_shares"] == 10
    assert row["delta_shares"] > 0
    assert row["delta_weight"] > 0
    # Mark-to-market reference price is the latest close, not the $500 avg_cost.
    assert row["reference_price"] == 600.0

    # Every diff row must carry the canonical key set the frontend
    # destructures.
    required_keys = {
        "symbol",
        "current_shares",
        "target_shares",
        "delta_shares",
        "current_weight",
        "target_weight",
        "delta_weight",
        "delta_dollar",
        "reference_price",
        "reason",
    }
    for row in payload["diff"]:
        assert required_keys.issubset(row.keys()), row


def test_position_diff_flags_target_only_symbols_as_unmatched(
    initialised_db: str, tmp_path: Path
) -> None:
    """A target row whose symbol has no current position (no avg_cost
    reference) lands in ``unmatched`` so the UI can warn about the
    placeholder share calculation."""

    _seed_account(cash=100_000.0)
    _seed_recommendation_target(("B013", "B014", "B015", "B016"))
    _seed_snapshot(cash=100_000.0, positions=[])
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/position-diff").json()
    # All targets are unmatched in this scenario (no current positions).
    assert len(payload["unmatched"]) > 0
    for row in payload["unmatched"]:
        assert row["reference_price"] is None


def test_position_diff_flags_held_but_not_targeted_as_sell_to_zero(
    initialised_db: str, tmp_path: Path
) -> None:
    """A symbol present in the snapshot but absent from target_positions
    appears in the diff with negative delta_shares."""

    _seed_account(cash=100_000.0)
    _seed_snapshot(
        cash=100_000.0,
        positions=[
            {"symbol": "ZZZNOTGT", "shares": 25, "avg_cost": 50.0},
        ],
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/position-diff").json()
    zzz_rows = [r for r in payload["diff"] if r["symbol"] == "ZZZNOTGT"]
    assert len(zzz_rows) == 1
    assert zzz_rows[0]["delta_shares"] == -25
    assert zzz_rows[0]["target_shares"] == 0
    assert zzz_rows[0]["reason"]
    assert "sell" in zzz_rows[0]["reason"].lower()


def test_put_account_then_position_diff_reflects_new_state(
    initialised_db: str, tmp_path: Path
) -> None:
    """Acceptance #3: 'on submit ... Recommendations/Position-diff pages
    immediately reflect the new state.' We verify the position-diff
    response sees the new snapshot the moment the PUT commits."""

    _seed_account(cash=100_000.0)
    client = _authed_client(_settings(tmp_path))

    # Before PUT: position-diff has no current snapshot.
    pre = client.get("/api/execution/position-diff").json()
    assert pre["current"] is None

    # PUT new account state.
    body = {
        "cash": 60_000.0,
        "base_currency": "USD",
        "positions": [{"symbol": "SPY", "shares": 20, "avg_cost": 500.0}],
    }
    response = client.put("/api/execution/account", json=body)
    assert response.status_code == 200, response.text

    # B046 F001 — diff is mark-to-market; seed SPY's mark so total_equity is the
    # market-value NAV (cash + shares × latest close), not the cost-basis sum.
    _seed_price_snapshot("SPY", latest_close=550.0, prior_close=540.0)

    # After PUT: position-diff sees the new state on the very next call.
    post = client.get("/api/execution/position-diff").json()
    assert post["current"] is not None
    assert post["current"]["cash"] == 60_000.0
    assert post["total_equity"] == pytest.approx(60_000.0 + 20 * 550.0)
