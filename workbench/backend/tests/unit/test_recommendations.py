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
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.observability.active_users import active_users
from workbench_api.services.prices_provider import PriceMark
from workbench_api.services.recommendations import (
    DISCLAIMER_LITERAL,
    DISCLAIMER_LITERAL_ZH,
    _build_target_positions,
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


class _FakeProvider:
    """PriceProvider returning fixed marks (B046 F001 — inject known closes)."""

    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = marks

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {s.upper(): self._marks[s.upper()] for s in symbols if s.upper() in self._marks}


def _seed_account_snapshot(positions: list[dict[str, object]], cash: float) -> None:
    from decimal import Decimal

    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id="rec-snap-1",
                snapshot_at=date(2026, 6, 5),
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions,
                source="bootstrap",
                created_at=date(2026, 6, 5),
            )
        )
        session.commit()


def test_target_positions_current_weight_is_mark_to_market(
    initialised_db: str, tmp_path: Path
) -> None:
    """B046 F001 — current_weight is the account's mark-to-market weight (held
    shares × latest close / market-value NAV), not the old hardcoded 0.0."""

    _seed_snapshot()  # targets EEM/SPY/SGOV (target_weight 0.2/0.2/0.6)
    # Hold 100 SGOV; cash 0; SGOV marks at $100 → NAV = 100×100 = 10000, SGOV = 1.0.
    _seed_account_snapshot([{"symbol": "SGOV", "shares": 100, "avg_cost": 90.0}], cash=0.0)
    provider = _FakeProvider({"SGOV": PriceMark(latest_close=100.0, prior_close=99.0)})

    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        positions = _build_target_positions(session, provider=provider)

    by_symbol = {p.symbol: p for p in positions}
    assert by_symbol["SGOV"].current_weight == pytest.approx(1.0)
    # diff = target - current = 0.6 - 1.0 = -0.4 (already over-weight → sell).
    assert by_symbol["SGOV"].diff == pytest.approx(0.6 - 1.0)
    # Targets not held have current_weight 0.0 → diff == target.
    assert by_symbol["EEM"].current_weight == 0.0
    assert by_symbol["EEM"].diff == pytest.approx(0.2)


def test_target_positions_current_weight_degrades_when_unmarked(
    initialised_db: str, tmp_path: Path
) -> None:
    """A held symbol with no price mark degrades to current_weight 0.0 (not a
    crash) — same trust-nothing posture as the execution diff."""

    _seed_snapshot()
    _seed_account_snapshot([{"symbol": "SGOV", "shares": 100, "avg_cost": 90.0}], cash=0.0)
    provider = _FakeProvider({})  # no marks at all

    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        positions = _build_target_positions(session, provider=provider)

    by_symbol = {p.symbol: p for p in positions}
    assert by_symbol["SGOV"].current_weight == 0.0


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


# --- B048 F003: kill_switch gate reads the real master drawdown -----------


def _seed_two_snapshots(*, peak_cash: float, latest_cash: float) -> None:
    """Two account snapshots so nav_history has a peak + latest. With no
    price_history present, valuation degrades to cost basis (= cash here)."""

    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id="ks-peak", snapshot_at=datetime(2026, 5, 1, 10, 0, 0),
                cash=Decimal(str(peak_cash)), base_currency="USD",
                positions=[], source="bootstrap",
                created_at=datetime(2026, 5, 1, 10, 0, 0),
            )
        )
        session.add(
            AccountSnapshot(
                id="ks-now", snapshot_at=datetime(2026, 5, 2, 10, 0, 0),
                cash=Decimal(str(latest_cash)), base_currency="USD",
                positions=[], source="bootstrap",
                created_at=datetime(2026, 5, 2, 10, 0, 0),
            )
        )
        session.commit()


def test_kill_switch_gate_fails_on_real_drawdown(
    initialised_db: str, tmp_path: Path
) -> None:
    """100k → 80k = 20% master drawdown ≥ 0.15 → kill_switch gate FAILS
    (B048 F003: real DD, not a hard-coded pass), at the unified 0.15."""

    _seed_two_snapshots(peak_cash=100_000.0, latest_cash=80_000.0)
    client = _authed_client(tmp_path)
    payload = client.get("/api/recommendations/current").json()
    gates = {g["name"]: g for g in payload["gate_checks"]}
    assert gates["kill_switch"]["status"] == "fail"
    assert "0.15" in gates["kill_switch"]["detail"]


def test_kill_switch_gate_passes_without_drawdown(
    initialised_db: str, tmp_path: Path
) -> None:
    """Flat equity → 0% drawdown → kill_switch gate passes."""

    _seed_two_snapshots(peak_cash=100_000.0, latest_cash=100_000.0)
    client = _authed_client(tmp_path)
    payload = client.get("/api/recommendations/current").json()
    gates = {g["name"]: g for g in payload["gate_checks"]}
    assert gates["kill_switch"]["status"] == "pass"
