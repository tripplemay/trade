"""B023 F004 — ``/api/execution/fills`` contract + 3 fixture CSV adapters.

Acceptance pins:
- POST /fills accepts both multipart CSV and JSON (Schwab / IBKR /
  generic adapters each parse with ≤ 5 LOC of glue per broker).
- 400 with row-level ``{row, error}`` details when a row fails
  validation.
- Unmatched fills flag a user prompt (``allow_unmatched=true``) rather
  than silently rejecting.
- Manual entry validates positive shares + valid date.
"""

from __future__ import annotations

import io
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.observability.active_users import active_users
from workbench_api.services.fills import parse_csv
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
        {"email": ALLOWED_EMAIL, "sub": "fills-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_ticket(
    ticket_id: str = "tkt-test-1", status: str = "generated"
) -> None:
    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        session.add(
            OrderTicket(
                id=ticket_id,
                ticket_date=date(2026, 5, 19),
                snapshot_id="snap-test",
                target_positions_id="tp-2026-05-19",
                markdown_path="docs/runs/2026-05-19/order-ticket-tkt-test-1.md",
                status=status,
                created_at=datetime(2026, 5, 19, 10, 0, 0),
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# CSV adapters (parse_csv is the pure parser; submit_csv adds persistence)
# ---------------------------------------------------------------------------

GENERIC_CSV = (
    "order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at\n"
    "1,SPY,buy,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42\n"
    "2,IEF,sell,45,94.18,0.50,0.10,USD,2026-05-30T13:32:15\n"
)
SCHWAB_CSV = (
    '#,Symbol,Action,Quantity,Price,Commission,"Fees & Taxes",Date\n'
    "1,SPY,Bought,72,501.85,0.00,0.00,2026-05-30T13:31:42\n"
    "2,IEF,Sold,45,94.18,0.50,0.10,2026-05-30T13:32:15\n"
)
IBKR_CSV = (
    "OrderID,Symbol,Buy/Sell,Quantity,TradePrice,IBCommission,Taxes,CurrencyPrimary,DateTime\n"
    "1,SPY,BUY,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42\n"
    "2,IEF,SELL,45,94.18,0.50,0.10,USD,2026-05-30T13:32:15\n"
)


@pytest.mark.parametrize(
    "csv_body,label",
    [
        (GENERIC_CSV, "generic"),
        (SCHWAB_CSV, "schwab"),
        (IBKR_CSV, "ibkr"),
    ],
)
def test_parse_csv_handles_each_broker_format(csv_body: str, label: str) -> None:
    rows, errors = parse_csv(csv_body)
    assert errors == [], f"adapter {label}: {errors}"
    assert len(rows) == 2
    assert rows[0].symbol == "SPY"
    assert rows[0].side == "buy"
    assert rows[0].shares == 72
    assert rows[0].fill_price == pytest.approx(501.85)
    assert rows[1].side == "sell"


def test_parse_csv_unknown_format_returns_400_like_error(initialised_db: str) -> None:
    """An off-format CSV (no recognised columns) raises before parsing."""

    from fastapi import HTTPException

    bad = "foo,bar,baz\n1,2,3\n"
    with pytest.raises(HTTPException) as excinfo:
        parse_csv(bad)
    assert excinfo.value.status_code == 400


def test_parse_csv_emits_row_level_validation_errors() -> None:
    """One bad row → one entry in errors, the rest in rows."""

    csv_body = (
        "order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at\n"
        "1,SPY,buy,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42\n"
        "2,IEF,sell,-1,94.18,0.50,0.10,USD,2026-05-30T13:32:15\n"
    )
    rows, errors = parse_csv(csv_body)
    assert len(rows) == 1
    assert len(errors) == 1
    assert errors[0].row == 1  # 0-indexed in input
    assert "shares" in errors[0].error.lower()
    assert errors[0].source_row is not None


# ---------------------------------------------------------------------------
# Route-level auth + happy/unhappy paths
# ---------------------------------------------------------------------------


def test_fills_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/fills?ticket_id=anything")
    assert response.status_code == 401


def test_post_fills_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.post("/api/execution/fills", json={"ticket_id": "x", "fills": []})
    assert response.status_code == 401


def test_post_fills_json_path_inserts_matched(initialised_db: str, tmp_path: Path) -> None:
    _seed_ticket()
    client = _authed_client(_settings(tmp_path))
    body: dict[str, Any] = {
        "ticket_id": "tkt-test-1",
        "fills": [
            {
                "order_seq": 1,
                "symbol": "SPY",
                "side": "buy",
                "shares": 72,
                "fill_price": 501.85,
                "currency": "USD",
                "filled_at": "2026-05-30T13:31:42",
            },
        ],
    }
    response = client.post("/api/execution/fills", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket_id"] == "tkt-test-1"
    assert len(payload["inserted"]) == 1
    assert payload["inserted"][0]["matched"] is True
    assert payload["inserted"][0]["source"] == "manual_entry"

    listed = client.get("/api/execution/fills?ticket_id=tkt-test-1").json()
    assert len(listed["items"]) == 1


def test_post_fills_unmatched_requires_explicit_flag(
    initialised_db: str, tmp_path: Path
) -> None:
    """Unmatched fills (order_seq=null) get a 400 with row-level details
    until the user confirms with allow_unmatched=true."""

    _seed_ticket()
    client = _authed_client(_settings(tmp_path))
    body: dict[str, Any] = {
        "ticket_id": "tkt-test-1",
        "fills": [
            {
                "symbol": "QQQ",
                "side": "buy",
                "shares": 10,
                "fill_price": 450.0,
                "currency": "USD",
                "filled_at": "2026-05-30T13:31:42",
            },
        ],
    }
    response = client.post("/api/execution/fills", json=body)
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "errors" in detail
    assert detail["errors"][0]["row"] == 0
    assert "allow_unmatched" in detail["errors"][0]["error"]

    # Re-submit with allow_unmatched → accepted; matched=False.
    body["allow_unmatched"] = True
    response = client.post("/api/execution/fills", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["unmatched_count"] == 1
    assert payload["accepted_under_allow_unmatched"] is True
    assert payload["inserted"][0]["matched"] is False


def test_post_fills_csv_upload_via_multipart(initialised_db: str, tmp_path: Path) -> None:
    _seed_ticket()
    client = _authed_client(_settings(tmp_path))
    response = client.post(
        "/api/execution/fills/csv",
        data={"ticket_id": "tkt-test-1", "allow_unmatched": "false"},
        files={"csv_file": ("fills.csv", io.BytesIO(GENERIC_CSV.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["inserted"]) == 2
    assert {r["symbol"] for r in payload["inserted"]} == {"SPY", "IEF"}
    assert payload["inserted"][0]["source"] == "csv_upload"


def test_post_fills_csv_invalid_row_returns_row_level_400(
    initialised_db: str, tmp_path: Path
) -> None:
    _seed_ticket()
    client = _authed_client(_settings(tmp_path))
    bad_csv = (
        "order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at\n"
        "1,SPY,buy,72,501.85,0.00,0.00,USD,not-a-date\n"
    )
    response = client.post(
        "/api/execution/fills/csv",
        data={"ticket_id": "tkt-test-1"},
        files={"csv_file": ("fills.csv", io.BytesIO(bad_csv.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["errors"][0]["row"] == 0
    assert "filled_at" in detail["errors"][0]["error"].lower()


def test_post_fills_unknown_ticket_returns_404(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    response = client.post(
        "/api/execution/fills",
        json={
            "ticket_id": "tkt-missing",
            "fills": [
                {
                    "order_seq": 1,
                    "symbol": "SPY",
                    "side": "buy",
                    "shares": 72,
                    "fill_price": 501.85,
                    "currency": "USD",
                    "filled_at": "2026-05-30T13:31:42",
                },
            ],
        },
    )
    assert response.status_code == 404


def test_post_fills_voided_ticket_rejected(initialised_db: str, tmp_path: Path) -> None:
    _seed_ticket(status="voided")
    client = _authed_client(_settings(tmp_path))
    response = client.post(
        "/api/execution/fills",
        json={
            "ticket_id": "tkt-test-1",
            "fills": [
                {
                    "order_seq": 1,
                    "symbol": "SPY",
                    "side": "buy",
                    "shares": 72,
                    "fill_price": 501.85,
                    "currency": "USD",
                    "filled_at": "2026-05-30T13:31:42",
                },
            ],
        },
    )
    assert response.status_code == 409
