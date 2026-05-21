"""B023 F003 — ``/api/execution/tickets/*`` contract tests.

Covers the four ticket endpoints (POST / list / detail / void), the
Markdown disclaimer literal pin, the historical-ticket listing
contract (≥ 3 seeded rows), and the void state-machine guard
(voided ticket cannot be re-voided nor reconciled later — the latter
half lives in F005 once reconcile lands).
"""

from __future__ import annotations

import time
from datetime import date, datetime
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
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.observability.active_users import active_users
from workbench_api.services.tickets import DISCLAIMER_LITERAL, DISCLAIMER_LITERAL_ZH
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
        {"email": ALLOWED_EMAIL, "sub": "tickets-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_account(cash: float = 100_000.0) -> None:
    with Session(get_engine()) as session:
        session.add(
            Account(
                account_id="research-mvp",
                name="Research MVP",
                base_currency="USD",
                cash=Decimal(str(cash)),
                equity_value=Decimal("0"),
                as_of_date=date(2026, 5, 19),
            )
        )
        session.commit()


def _seed_snapshot(
    *,
    snap_id: str = "snap-test-1",
    cash: float = 50_000.0,
    positions: list[dict[str, Any]] | None = None,
    snapshot_at: datetime | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=snap_id,
                snapshot_at=snapshot_at or datetime(2026, 5, 19, 10, 0, 0),
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions or [{"symbol": "B013", "shares": 10, "avg_cost": 500.0}],
                source="bootstrap",
                created_at=snapshot_at or datetime(2026, 5, 19, 10, 0, 0),
            )
        )
        session.commit()


def _seed_ticket(
    *,
    ticket_id: str,
    status: str = "generated",
    ticket_date: date | None = None,
    markdown_path: str = "docs/runs/2026-05-19/order-ticket-seed.md",
    created_at: datetime | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            OrderTicket(
                id=ticket_id,
                ticket_date=ticket_date or date(2026, 5, 19),
                snapshot_id="snap-seed",
                target_positions_id="tp-seed",
                markdown_path=markdown_path,
                status=status,
                created_at=created_at or datetime(2026, 5, 19, 9, 0, 0),
            )
        )
        session.commit()


def test_post_ticket_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.post("/api/execution/tickets", json={})
    assert response.status_code == 401


def test_list_tickets_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/tickets")
    assert response.status_code == 401


def test_detail_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/tickets/anything")
    assert response.status_code == 401


def test_void_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.post("/api/execution/tickets/anything/void")
    assert response.status_code == 401


def test_generate_ticket_requires_snapshot(initialised_db: str, tmp_path: Path) -> None:
    """No snapshot on file → 409 with a hint pointing to /execution/account."""

    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets", json={})
    assert response.status_code == 409, response.text
    assert "snapshot" in response.json()["detail"].lower()


def test_generate_ticket_writes_markdown_with_disclaimer(
    initialised_db: str, tmp_path: Path
) -> None:
    """Acceptance #1: POST writes both DB row + Markdown file; Markdown
    body carries the literal disclaimer, the "Trades to place" heading,
    and the "After execution checklist" section."""

    _seed_account()
    _seed_snapshot()
    settings = _settings(tmp_path)
    client = _authed_client(settings)

    response = client.post("/api/execution/tickets", json={})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "generated"
    assert payload["disclaimer"] == DISCLAIMER_LITERAL
    assert DISCLAIMER_LITERAL in payload["markdown_body"]
    assert "## Trades to place" in payload["markdown_body"]
    assert "## After execution checklist" in payload["markdown_body"]
    # The wash-sale flag section is present even when no flags fire.
    assert "## Tax / wash-sale flags" in payload["markdown_body"]
    # The disclaimer block also calls out manual execution.
    assert "Manual review checklist" in payload["markdown_body"]

    # Markdown file actually exists on disk under runs_dir.
    runs_dir = tmp_path / "runs"
    ticket_files = list(runs_dir.rglob("order-ticket-*.md"))
    assert len(ticket_files) == 1
    on_disk = ticket_files[0].read_text(encoding="utf-8")
    assert DISCLAIMER_LITERAL in on_disk


def test_list_tickets_pagination_with_three_seeded(initialised_db: str, tmp_path: Path) -> None:
    """Acceptance #2: list works for ≥ 3 historical tickets."""

    _seed_ticket(
        ticket_id="tkt-001",
        created_at=datetime(2026, 5, 17, 10, 0, 0),
    )
    _seed_ticket(
        ticket_id="tkt-002",
        status="voided",
        created_at=datetime(2026, 5, 18, 10, 0, 0),
    )
    _seed_ticket(
        ticket_id="tkt-003",
        created_at=datetime(2026, 5, 19, 10, 0, 0),
    )

    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/tickets").json()
    assert payload["total"] == 3
    assert payload["limit"] == 20
    assert payload["offset"] == 0
    ids = [item["id"] for item in payload["items"]]
    # Newest-first ordering.
    assert ids == ["tkt-003", "tkt-002", "tkt-001"]

    # offset+limit pagination round-trips.
    page2 = client.get("/api/execution/tickets?limit=2&offset=2").json()
    assert page2["total"] == 3
    assert [item["id"] for item in page2["items"]] == ["tkt-001"]


def test_get_ticket_detail_returns_markdown_body(initialised_db: str, tmp_path: Path) -> None:
    """Detail route reads the on-disk file and returns the rendered Markdown."""

    _seed_account()
    _seed_snapshot()
    client = _authed_client(_settings(tmp_path))
    generated = client.post("/api/execution/tickets", json={}).json()
    ticket_id = generated["id"]

    detail = client.get(f"/api/execution/tickets/{ticket_id}").json()
    assert detail["id"] == ticket_id
    assert detail["status"] == "generated"
    assert DISCLAIMER_LITERAL in detail["markdown_body"]


def test_get_ticket_unknown_id_returns_404(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    response = client.get("/api/execution/tickets/does-not-exist")
    assert response.status_code == 404


def test_void_ticket_flips_status(initialised_db: str, tmp_path: Path) -> None:
    _seed_ticket(ticket_id="tkt-void-1")
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets/tkt-void-1/void")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "voided"

    # Detail reflects new status.
    detail = client.get("/api/execution/tickets/tkt-void-1").json()
    assert detail["status"] == "voided"


def test_void_ticket_already_executed_returns_409(initialised_db: str, tmp_path: Path) -> None:
    """Acceptance #3: voided/executed tickets cannot be voided again."""

    _seed_ticket(ticket_id="tkt-exec", status="executed")
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets/tkt-exec/void")
    assert response.status_code == 409, response.text


def test_void_ticket_unknown_id_returns_409(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/tickets/does-not-exist/void")
    assert response.status_code == 409


def test_disclaimer_literal_is_pinned() -> None:
    """The Markdown renderer must continue to spell the disclaimer
    exactly as the export-ticket service does — any future drift breaks
    the F010 acceptance pin in test_recommendations.py too."""

    assert DISCLAIMER_LITERAL == (
        "research-only; this is a manual review checklist, not a trading instruction"
    )


def test_disclaimer_zh_literal_is_pinned() -> None:
    """B024 F005 — Chinese translation of the immutable disclaimer.

    Renders alongside (never instead of) the English literal. Keeping
    both pinned lets the bilingual contract drift only via an explicit
    spec change to both literals at once.
    """

    assert DISCLAIMER_LITERAL_ZH == (
        "仅供研究使用;这是一份人工核对清单,不构成交易指令"
    )


def test_markdown_carries_bilingual_disclaimer_and_sections(
    initialised_db: str, tmp_path: Path
) -> None:
    """B024 F005 — every generated ticket Markdown must carry both
    disclaimers + bilingual section titles + bilingual checklist items.

    The English literals stay pinned by `test_generate_ticket_*` above;
    this spec adds the Chinese counterparts so future refactors can't
    silently drop the bilingual contract.
    """

    _seed_account()
    _seed_snapshot()
    settings = _settings(tmp_path)
    client = _authed_client(settings)
    response = client.post("/api/execution/tickets", json={})
    assert response.status_code == 200, response.text
    body = response.json()["markdown_body"]

    # English literal (existing contract — duplicated here so a
    # regression flags both halves at once).
    assert DISCLAIMER_LITERAL in body
    # Chinese disclaimer renders on the line right below the English one.
    assert DISCLAIMER_LITERAL_ZH in body
    assert f"_Disclaimer: {DISCLAIMER_LITERAL}._" in body
    assert f"_免责声明:{DISCLAIMER_LITERAL_ZH}。_" in body

    # Bilingual section titles (≥3 distinct sections).
    assert "## Account snapshot / 账户快照" in body
    assert "## Trades to place / 待下达交易" in body
    assert "## After execution checklist / 执行后核对清单" in body
    assert "## Tax / wash-sale flags / 税务 / 洗售标记" in body

    # Bilingual checklist items.
    assert "Record actual fills in workbench's Fill Journal" in body
    assert "在工作台的 Fill Journal 中录入实际成交" in body
    assert "Or upload CSV from broker" in body
    assert "或上传券商导出的 CSV" in body

    # The manual-review warning also renders both languages.
    assert "Manual review checklist" in body
    assert "人工核对清单" in body
