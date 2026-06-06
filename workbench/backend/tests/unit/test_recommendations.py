"""B022 F010 — recommendations endpoint coverage + disclaimer pin.

Three contracts pinned, plus the **safety-bedrock** disclaimer assertion:

1. Auth gate (anon → 401) on both routes.
2. GET shape — account_present=False with empty target_positions when
   no Account row exists; account_present=True with N positions when
   the registry has sleeves and an Account row is present.
3. POST export-ticket — writes a markdown file under
   ``<WORKBENCH_RUNS_DIR>/<date>/order-ticket-<date>.md``; the file
   body MUST contain the literal F010 disclaimer string so the user's
   downstream review checklist can never be mistaken for a trading
   instruction. This is a hard contract; any future edit that drops
   the literal trips this test.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.observability.active_users import active_users
from workbench_api.services.recommendations import (
    DISCLAIMER_LITERAL,
    DISCLAIMER_LITERAL_ZH,
)
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()


def _authed_client(runs_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_RUNS_DIR=str(runs_dir),
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "recs-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_account() -> None:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            Account(
                account_id="acct-1",
                name="Research",
                base_currency="USD",
                cash=10_000.0,
                equity_value=40_000.0,
                as_of_date=date(2026, 5, 17),
            )
        )
        session.commit()


def test_recommendations_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_RUNS_DIR=str(tmp_path),
    )
    client = TestClient(app)
    assert client.get("/api/recommendations/current").status_code == 401
    assert (
        client.post(
            "/api/recommendations/export-ticket", json={"as_of_date": "2026-05-17"}
        ).status_code
        == 401
    )


def _seed_snapshot() -> None:
    """B044: seed a precomputed Master Portfolio target (the precompute timer
    writes this; the read path maps it to TargetPosition)."""
    from sqlalchemy.orm import Session

    from workbench_api.db.repositories.recommendation_snapshot import (
        RecommendationSnapshotRepository,
    )

    with Session(get_engine()) as session:
        RecommendationSnapshotRepository(session).save_batch(
            as_of_date=date(2024, 12, 31),
            rows=[
                {"symbol": "EEM", "sleeve": "momentum", "target_weight": 0.2, "rationale": "m"},
                {"symbol": "SPY", "sleeve": "momentum", "target_weight": 0.2, "rationale": "m"},
                {"symbol": "SGOV", "sleeve": "risk_parity", "target_weight": 0.6, "rationale": "d"},
            ],
            master_meta={"data_source": "fixture", "planning_weights": {}},
        )
        session.commit()


def test_current_graceful_empty_when_no_snapshot(
    initialised_db: str, tmp_path: Path
) -> None:
    # B044: target positions come from the recommendation_snapshot; with no
    # precompute run yet the read path is graceful (empty), never an error.
    client = _authed_client(tmp_path)
    payload = client.get("/api/recommendations/current").json()
    assert payload["account_present"] is False
    assert payload["target_positions"] == []
    # Gate panel still ships so the UI has something to render.
    assert len(payload["gate_checks"]) >= 1
    assert payload["wash_sale_flags"] == []


def test_current_returns_target_positions_from_snapshot(
    initialised_db: str, tmp_path: Path
) -> None:
    # B044: real (fixture-data) Master composition from the snapshot, NOT the
    # old equal-weight placeholder; independent of account presence.
    _seed_snapshot()
    client = _authed_client(tmp_path)
    payload = client.get("/api/recommendations/current").json()
    positions = payload["target_positions"]
    assert {p["symbol"] for p in positions} == {"EEM", "SPY", "SGOV"}
    by_symbol = {p["symbol"]: p for p in positions}
    assert by_symbol["SGOV"]["target_weight"] == pytest.approx(0.6)
    assert by_symbol["EEM"]["target_weight"] == pytest.approx(0.2)
    # current_weight 0.0 this batch (B045 wires the account) → diff == target.
    assert by_symbol["SGOV"]["current_weight"] == 0.0
    assert by_symbol["SGOV"]["diff"] == pytest.approx(0.6)
    # Not equal-weight (the whole point of B044).
    weights = [p["target_weight"] for p in positions]
    assert len(set(weights)) > 1


def test_export_ticket_writes_markdown_with_disclaimer_literal(
    initialised_db: str, tmp_path: Path
) -> None:
    """F010 safety bedrock — the exported checklist MUST carry the literal
    research-only disclaimer; removing it lets the user accidentally
    treat the export as a trading instruction. This assertion exists
    to make that mistake impossible to merge.
    """

    _seed_account()
    client = _authed_client(tmp_path)
    response = client.post(
        "/api/recommendations/export-ticket",
        json={"as_of_date": "2026-05-17"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert DISCLAIMER_LITERAL in payload["disclaimer"]
    # Path is repo-relative when the runs_dir sits under the repo; tests
    # use a tmp_path outside it so we get an absolute path back. Either
    # way the file exists and its body carries the literal.
    written = Path(payload["path"])
    assert written.is_file(), f"export-ticket path missing: {written}"
    assert DISCLAIMER_LITERAL in written.read_text(encoding="utf-8")


def test_export_ticket_markdown_is_bilingual(
    initialised_db: str, tmp_path: Path
) -> None:
    """B024 F005 — exported recommendation Markdown carries both
    disclaimers and bilingual section titles. The English literal stays
    immutable (see ``test_export_ticket_writes_markdown_with_disclaimer_literal``);
    this spec layers the Chinese contract on top.
    """

    _seed_account()
    _seed_snapshot()  # B044: the target-positions table now comes from the snapshot
    client = _authed_client(tmp_path)
    payload = client.post(
        "/api/recommendations/export-ticket",
        json={"as_of_date": "2026-05-17"},
    ).json()
    body = Path(payload["path"]).read_text(encoding="utf-8")

    assert DISCLAIMER_LITERAL in body
    assert DISCLAIMER_LITERAL_ZH in body

    # ≥3 bilingual section titles.
    assert "Order ticket — 2026-05-17 / 订单清单 — 2026-05-17" in body
    assert "## Target positions / 目标持仓" in body
    assert "## Gate checks / 门控检查" in body
    assert "## Wash-sale flags / 洗售标记" in body

    # Table headers carry both languages too.
    assert "Symbol / 标的" in body
    assert "Rationale / 说明" in body


def test_export_ticket_path_includes_as_of_date(
    initialised_db: str, tmp_path: Path
) -> None:
    """Exported file lives under ``<runs>/<date>/order-ticket-<date>.md``."""

    _seed_account()
    client = _authed_client(tmp_path)
    payload = client.post(
        "/api/recommendations/export-ticket",
        json={"as_of_date": "2026-05-17"},
    ).json()
    assert "2026-05-17" in payload["path"]
    assert payload["path"].endswith("order-ticket-2026-05-17.md")
