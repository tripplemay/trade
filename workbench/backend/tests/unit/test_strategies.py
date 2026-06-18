"""B022 F007 — strategies registry endpoint coverage.

Pins the three contracts the frontend depends on:

1. Auth gate (anon → 401) — the registry is unauthenticated nowhere.
2. List shape — at least the 4 sleeves the spec calls out.
3. Detail-or-404 — known id 200, unknown id 404. Both round-trip the
   field set the StrategyDetail schema declares so the
   /api/strategies/{id} responder cannot silently drop a field.
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
        {"email": ALLOWED_EMAIL, "sub": "strategies-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_strategies_list_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/strategies").status_code == 401


def test_strategies_list_reflects_master_sleeves(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies")
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert isinstance(payload["strategies"], list)
    ids = [entry["id"] for entry in payload["strategies"]]
    # B046 F002 reconcile: the registry now mirrors the Master's real
    # composition (trade/portfolio/master.py). The four active sleeves
    # (momentum / risk_parity / satellite_us_quality / satellite_hk_china)
    # lead, then the regime overlay entries (research-state, weight 0.0).
    assert ids == [
        # B050 F001: Master Portfolio flagship leads (explicit backtestable entry).
        "master_portfolio",
        "B006-global-etf-momentum",
        "B016-risk-parity-hrp",
        "B025-us-quality-momentum",
        "B011-satellite-hk-china",
        "B013-regime-quarterly",
        "B014-regime-stress",
        "B015-regime-active",
        # B057 F002: the Regime-Adaptive strategy as a first-class backtestable
        # mode (distinct from the B013/B014/B015 overlays), research-state.
        "regime_adaptive",
        # B066 F003: A-share attack momentum+quality — a STANDALONE research
        # strategy (not a Master sleeve; excluded from sleeve_strategies), listed
        # last so the backtest page can select + run it.
        "cn_attack_momentum_quality",
    ]


def test_strategies_list_covers_master_four_active_sleeves(
    initialised_db: str,
) -> None:
    """The four sleeves the Master allocates to are all surfaced, and the
    regime entries are research-state (not active)."""

    client = _authed_client()
    payload = client.get("/api/strategies").json()
    by_id = {e["id"]: e for e in payload["strategies"]}

    # Master's four default sleeves (master.default_master_portfolio_parameters).
    active_sleeves = {
        by_id["B006-global-etf-momentum"]["sleeve"],
        by_id["B016-risk-parity-hrp"]["sleeve"],
        by_id["B025-us-quality-momentum"]["sleeve"],
        by_id["B011-satellite-hk-china"]["sleeve"],
    }
    assert active_sleeves == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }

    # The momentum core was missing pre-B046; now active.
    assert by_id["B006-global-etf-momentum"]["status"] == "active"
    # BL-B011-S2: HK-China is now an implemented strategy (Master 4/4 real),
    # no longer the reserved stub.
    assert by_id["B011-satellite-hk-china"]["status"] == "active"
    # Regime overlay ships at weight 0.0 → research-state, not active.
    for rid in ("B013-regime-quarterly", "B014-regime-stress", "B015-regime-active"):
        assert by_id[rid]["sleeve"] == "regime"
        assert by_id[rid]["status"] == "research"


def test_strategy_detail_momentum_exposes_master_strategy_id(
    initialised_db: str,
) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/B006-global-etf-momentum")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sleeve"] == "momentum"
    assert payload["config"]["master_strategy_id"] == "global_etf_momentum"
    assert payload["provenance"]["code_path"].endswith("global_etf_momentum.py")


def test_strategy_detail_hk_china_is_implemented(initialised_db: str) -> None:
    """BL-B011-S2: the HK-China satellite is an implemented strategy now
    (Master 4/4 real) — the registry mirrors master.py's sleeve_type flip."""

    client = _authed_client()
    payload = client.get("/api/strategies/B011-satellite-hk-china").json()
    assert payload["sleeve"] == "satellite_hk_china"
    assert payload["status"] == "active"
    assert payload["config"]["sleeve_type"] == "implemented"
    assert payload["config"]["master_strategy_id"] == "hk_china_momentum"
    assert payload["config"]["planning_weight"] == 0.10


def test_strategy_detail_risk_parity_records_master_id(initialised_db: str) -> None:
    client = _authed_client()
    payload = client.get("/api/strategies/B016-risk-parity-hrp").json()
    # B046 F002: the B016 HRP entry traces to the Master's
    # risk_parity_vol_target sleeve id.
    assert payload["config"]["master_strategy_id"] == "risk_parity_vol_target"


def test_strategy_detail_us_quality_momentum_exposes_b025_config(
    initialised_db: str,
) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/B025-us-quality-momentum")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "B025-us-quality-momentum"
    assert payload["sleeve"] == "satellite_us_quality"
    config = payload["config"]
    assert config["top_n"] == 15
    assert config["max_position_weight"] == 0.07
    assert config["max_sector_weight"] == 0.30
    assert "0.35" in config["factor_weights"]
    assert payload["provenance"]["spec_path"].endswith(
        "B025-us-quality-momentum-satellite-spec.md"
    )


def test_strategy_detail_known_id_returns_provenance(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/B013-regime-quarterly")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "B013-regime-quarterly"
    assert payload["sleeve"] == "regime"
    # Schema fields present (no silent drops).
    assert "config" in payload
    assert "provenance" in payload
    assert payload["provenance"]["spec_path"].endswith(".md")
    assert payload["provenance"]["last_sweep_path"] is not None
    # B019 retune sets activation_threshold=0.11; pinned so a future
    # config edit that drops the field surfaces here.
    assert payload["config"]["activation_threshold"] == 0.11


_STALE_SYNTHETIC_PHRASES = (
    "Synthetic fixture only",
    "not live market data",
    "not actual filings",
)


def test_no_strategy_note_carries_stale_synthetic_copy(initialised_db: str) -> None:
    """B049 F002 guard: after B045 connected real data, no user-visible strategy
    note may still claim synthetic/non-live data. Regression for the stale notes
    on global_etf_momentum / us_quality / hk_china."""

    client = _authed_client()
    ids = [entry["id"] for entry in client.get("/api/strategies").json()["strategies"]]
    for strategy_id in ids:
        config = client.get(f"/api/strategies/{strategy_id}").json()["config"]
        note = str(config.get("note", ""))
        for phrase in _STALE_SYNTHETIC_PHRASES:
            assert phrase not in note, (
                f"{strategy_id} note still carries stale synthetic copy "
                f"{phrase!r}: {note!r}"
            )


def test_honest_research_disclosures_are_preserved(initialised_db: str) -> None:
    """B049 F002 §1.2: the guard must not scrub the honest research-state
    disclosure on the regime overlay (weight 0.0, inactive) — that is a true
    statement, not stale synthetic copy."""

    client = _authed_client()
    note = client.get("/api/strategies/B013-regime-quarterly").json()["config"]["note"]
    assert "Research-state" in note
    assert "weight 0.0" in note.lower() or "weight=0.0" in note.lower()


def test_strategy_detail_master_portfolio_is_backtestable(initialised_db: str) -> None:
    """B050 F001: the Master Portfolio flagship is an explicit registry entry so
    the backtest selector can run the full combined portfolio."""

    client = _authed_client()
    response = client.get("/api/strategies/master_portfolio")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "master_portfolio"
    assert payload["sleeve"] == "master"
    assert payload["status"] == "active"
    assert payload["provenance"]["code_path"].endswith("master_portfolio.py")


def test_sleeve_strategies_excludes_master_flagship(initialised_db: str) -> None:
    """B050 F001: sleeve-derivation (home / advisor / risk panel / news) must not
    treat the portfolio-level master as a constituent sleeve."""

    from workbench_api.services.strategies import list_strategies, sleeve_strategies

    all_ids = {s.id for s in list_strategies().strategies}
    sleeve_ids = {s.id for s in sleeve_strategies()}
    assert "master_portfolio" in all_ids
    assert "master_portfolio" not in sleeve_ids
    assert "master" not in {s.sleeve for s in sleeve_strategies()}


def test_strategy_detail_unknown_id_returns_404(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/strategies/does-not-exist")
    assert response.status_code == 404
    assert "Unknown strategy id" in response.json()["detail"]
