"""B023 F006 — ``/api/execution/risk-panel`` 3-state coverage + defensive
ticket mode honoring.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.price_history import PriceHistoryRepository
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
        WORKBENCH_REPORTS_DIR=str(tmp_path / "reports"),
        WORKBENCH_RUNS_DIR=str(tmp_path / "runs"),
    )


def _authed_client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "risk-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_snapshot(
    *,
    snap_id: str,
    cash: float,
    positions: list[dict[str, Any]],
    snapshot_at: datetime,
    source: str = "bootstrap",
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=snap_id,
                snapshot_at=snapshot_at,
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions,
                source=source,
                created_at=snapshot_at,
            )
        )
        session.commit()


def _seed_account() -> None:
    """Mirror the recommendations service's account_present prerequisite."""

    from datetime import date as _date

    with Session(get_engine()) as session:
        session.add(
            Account(
                account_id="research-mvp",
                name="Research MVP",
                base_currency="USD",
                cash=Decimal("100000"),
                equity_value=Decimal("0"),
                as_of_date=_date(2026, 5, 19),
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# Auth + empty state
# ---------------------------------------------------------------------------


def test_risk_panel_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    assert client.get("/api/execution/risk-panel").status_code == 401


def test_risk_panel_no_snapshots_is_green(initialised_db: str, tmp_path: Path) -> None:
    """No snapshot history → master_dd=0 → green banner; the response
    shape must still be complete so the frontend can render without
    null-guards on the optional fields."""

    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    assert payload["state"] == "green"
    assert payload["master_dd"] == 0.0
    assert payload["kill_switch_triggered"] is False
    assert payload["alternative_defensive_ticket"] is None
    assert payload["kill_switch_threshold"] == 0.15
    assert payload["per_sleeve_threshold"] == 0.08


# ---------------------------------------------------------------------------
# 3-state coverage (acceptance #1)
# ---------------------------------------------------------------------------


def test_risk_panel_green_state(initialised_db: str, tmp_path: Path) -> None:
    """Two snapshots with 1% drawdown → state stays green (< 8% per-sleeve)."""

    _seed_snapshot(
        snap_id="snap-peak",
        cash=100_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 17, 10, 0, 0),
    )
    _seed_snapshot(
        snap_id="snap-now",
        cash=99_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 18, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    # peak equity = 150_000; latest = 149_000; dd = 1000/150000 ≈ 0.00667
    assert payload["master_dd"] == pytest.approx(0.00667, rel=1e-2)
    assert payload["state"] == "green"
    assert payload["alternative_defensive_ticket"] is None


def test_risk_panel_yellow_state(initialised_db: str, tmp_path: Path) -> None:
    """Per-sleeve DD ≥ 8% but < 15% kill-switch → yellow."""

    _seed_snapshot(
        snap_id="snap-peak",
        cash=100_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 17, 10, 0, 0),
    )
    # 12% drawdown ≥ 8% per-sleeve threshold but < 15% kill switch.
    _seed_snapshot(
        snap_id="snap-now",
        cash=132_000,
        positions=[],
        snapshot_at=datetime(2026, 5, 18, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    assert payload["master_dd"] == pytest.approx(0.12, rel=1e-2)
    assert payload["state"] == "yellow"
    assert payload["kill_switch_triggered"] is False
    assert payload["alternative_defensive_ticket"] is None


def test_risk_panel_red_state_includes_defensive_ticket(
    initialised_db: str, tmp_path: Path
) -> None:
    """master_dd ≥ 15% → red; alternative_defensive_ticket populated."""

    _seed_snapshot(
        snap_id="snap-peak",
        cash=100_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 17, 10, 0, 0),
    )
    # 20% drawdown ≥ 15% kill switch.
    _seed_snapshot(
        snap_id="snap-now",
        cash=120_000,
        positions=[],
        snapshot_at=datetime(2026, 5, 18, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    assert payload["master_dd"] == pytest.approx(0.20, rel=1e-2)
    assert payload["state"] == "red"
    assert payload["kill_switch_triggered"] is True
    assert payload["alternative_defensive_ticket"] is not None
    targets = payload["alternative_defensive_ticket"]["target_positions"]
    assert len(targets) == 1
    assert targets[0]["target_weight"] == 1.0
    # The single defensive symbol must be the workbench's B011 proxy.
    assert targets[0]["symbol"] == "SGOV"
    assert "kill-switch" in payload["alternative_defensive_ticket"]["rationale"].lower()


# ---------------------------------------------------------------------------
# B048 F003 — mark-to-market drawdown (master + per-sleeve, over time)
# ---------------------------------------------------------------------------


def _seed_prices(rows: list[tuple[str, date, float]]) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        for symbol, obs_date, close in rows:
            repo.save_if_new(
                symbol=symbol, obs_date=obs_date, close=close,
                source="b045_unified_csv", fetched_at=datetime(2026, 6, 7, tzinfo=UTC),
            )
        session.commit()


def test_risk_panel_master_dd_is_mark_to_market(initialised_db: str, tmp_path: Path) -> None:
    """With price_history present, master DD reflects the market price drop
    (not the flat cost basis), and valuation_basis is mark_to_market."""

    # Flat shares + flat cash; only the market price falls 12%.
    pos = [{"symbol": "SPY", "shares": 100, "avg_cost": 500, "sleeve": "momentum"}]
    _seed_snapshot(
        snap_id="s1", cash=0.0, positions=pos, snapshot_at=datetime(2026, 5, 1, 10, 0, 0)
    )
    _seed_snapshot(
        snap_id="s2", cash=0.0, positions=pos, snapshot_at=datetime(2026, 5, 2, 10, 0, 0)
    )
    _seed_prices([("SPY", date(2026, 5, 1), 500.0), ("SPY", date(2026, 5, 2), 440.0)])

    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    # 500 → 440 = 12% drawdown, mark-to-market (cost basis would show 0%).
    assert payload["master_dd"] == pytest.approx(0.12, rel=1e-3)
    assert payload["valuation_basis"] == "mark_to_market"
    assert payload["degraded_symbols"] == []
    # The momentum sleeve carries the same real drawdown (per-sleeve, not mirrored).
    by_sleeve = {s["sleeve"]: s["drawdown"] for s in payload["per_sleeve_dd"]}
    assert by_sleeve["momentum"] == pytest.approx(0.12, rel=1e-3)


def test_risk_panel_degrades_to_cost_without_price_history(
    initialised_db: str, tmp_path: Path
) -> None:
    """No price_history → valuation degrades to cost basis and the symbol is
    flagged (annotate, don't fabricate)."""

    _seed_snapshot(
        snap_id="s1", cash=100_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 1, 10, 0, 0),
    )
    _seed_snapshot(
        snap_id="s2", cash=80_000,
        positions=[{"symbol": "SPY", "shares": 100, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 2, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/risk-panel").json()
    assert payload["valuation_basis"] == "cost_degraded"
    assert "SPY" in payload["degraded_symbols"]


# ---------------------------------------------------------------------------
# Defensive ticket flag (acceptance #2)
# ---------------------------------------------------------------------------


def test_generate_ticket_defensive_flag_swaps_diff(
    initialised_db: str, tmp_path: Path
) -> None:
    """POST /tickets with defensive=true rolls the diff into a 100%
    defensive rotation. The resulting Markdown body must mention SGOV
    and the defensive rotation rationale."""

    _seed_account()
    _seed_snapshot(
        snap_id="snap-current",
        cash=10_000,
        positions=[
            {"symbol": "SPY", "shares": 50, "avg_cost": 500},
            {"symbol": "IEF", "shares": 30, "avg_cost": 95},
        ],
        snapshot_at=datetime(2026, 5, 19, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets", json={"defensive": True})
    assert response.status_code == 200, response.text
    payload = response.json()
    body = payload["markdown_body"]
    assert "SGOV" in body
    assert "Defensive rotation" in body
    # Each current holding should appear as a sell-to-zero line.
    assert "SPY" in body
    assert "IEF" in body


def test_generate_ticket_default_mode_unchanged(
    initialised_db: str, tmp_path: Path
) -> None:
    """Without the defensive flag, the normal diff drives the Markdown
    body — F003's existing path keeps its old behaviour."""

    _seed_account()
    _seed_snapshot(
        snap_id="snap-current",
        cash=10_000,
        positions=[{"symbol": "B013", "shares": 10, "avg_cost": 500}],
        snapshot_at=datetime(2026, 5, 19, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets", json={})
    assert response.status_code == 200, response.text
    body = response.json()["markdown_body"]
    # Normal path does not insert the defensive proxy.
    assert "SGOV" not in body
    assert "Defensive rotation" not in body
