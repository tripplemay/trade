"""B051 F001 — account state unified onto ``account_snapshot``.

Production bug (user-reported 2026-06-10): the UI Account form saved
(``PUT /api/execution/account`` → ``account_snapshot`` row) but
``GET /api/recommendations/current`` still claimed no account was
configured, and Home NAV stayed 0.0 (B046 soft-watch S1 — same root
cause). ``nav.aggregate_nav`` + ``recommendations._aggregate_account_state``
read the vestigial ``account`` table, which only the ``accounts/me.json``
bootstrap ever fills — empty in production, so the UI-saved snapshot was
invisible to both surfaces.

Pins, per the F001 acceptance:

(a) snapshot WITH positions → ``account_present=True``, nav = cash +
    mark-to-market positions;
(b) pure-cash snapshot, zero positions (new-user path) → ``True``,
    nav = cash;
(c) no snapshot → ``(False, 0.0)`` graceful;
(d) the recommendations ``min_equity`` gate reads the snapshot equity;
(★) route-level user-flow regression: PUT account → recommendations
    recognise it + Home NAV is real — with the ``account`` table EMPTY;
(¬) the inverse pin: a row in the vestigial ``account`` table alone is
    no longer recognised (proves the source actually moved).
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account import Account
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.services.nav import (
    aggregate_account_state,
    aggregate_nav,
    snapshot_positions_and_cash,
)
from workbench_api.services.prices_provider import PriceMark
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


class _FakeProvider:
    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = {k.upper(): v for k, v in marks.items()}

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        return {
            s.upper(): self._marks[s.upper()]
            for s in symbols
            if s.upper() in self._marks
        }


def _seed_snapshot(
    session: Session,
    *,
    cash: float,
    positions: list[dict[str, object]],
    source: str = "ui_edit",
) -> None:
    at = datetime(2026, 6, 9, 12, 0, 0)
    session.add(
        AccountSnapshot(
            id="b051-snap",
            snapshot_at=at,
            cash=cash,
            base_currency="USD",
            positions=positions,
            source=source,
            created_at=at,
        )
    )
    session.commit()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "b051-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


# --- (a) snapshot with positions → mark-to-market NAV ----------------------


def test_snapshot_with_positions_is_present_and_marked_to_market(
    initialised_db: str,
) -> None:
    with Session(get_engine()) as session:
        _seed_snapshot(
            session,
            cash=5_000.0,
            positions=[{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}],
        )
        provider = _FakeProvider({"AAPL": PriceMark(latest_close=195.0, prior_close=192.0)})
        present, nav = aggregate_account_state(session, provider)
        assert present is True
        # 5000 cash + 10 × 195 market = 6950 (NOT 10 × 150 cost).
        assert nav == pytest.approx(6_950.0)
        assert aggregate_nav(session, provider) == pytest.approx(6_950.0)


def test_unmarked_position_contributes_nothing_to_nav(initialised_db: str) -> None:
    """No price mark → the position is skipped, NAV degrades to cash
    (mark_to_market contract; never a crash, never cost-basis)."""

    with Session(get_engine()) as session:
        _seed_snapshot(
            session,
            cash=1_000.0,
            positions=[{"symbol": "ZZZZ", "shares": 5, "avg_cost": 10.0}],
        )
        present, nav = aggregate_account_state(session, _FakeProvider({}))
        assert present is True
        assert nav == pytest.approx(1_000.0)


# --- (b) pure-cash snapshot — the new-user path -----------------------------


def test_pure_cash_snapshot_zero_positions_counts_as_present(
    initialised_db: str,
) -> None:
    """A brand-new user saves the Account form with just a cash balance:
    zero positions must still flip account_present and value NAV at cash."""

    with Session(get_engine()) as session:
        _seed_snapshot(session, cash=50_000.0, positions=[])
        present, nav = aggregate_account_state(session, _FakeProvider({}))
        assert present is True
        assert nav == pytest.approx(50_000.0)


# --- (c) no snapshot → graceful absent --------------------------------------


def test_no_snapshot_is_absent_and_zero(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        assert aggregate_account_state(session, _FakeProvider({})) == (False, 0.0)
        assert aggregate_nav(session, _FakeProvider({})) == 0.0


# --- (¬) the vestigial account table is no longer consulted -----------------


def test_vestigial_account_row_alone_is_not_recognised(initialised_db: str) -> None:
    """Inverse pin of the unification: a row in the old ``account`` table
    (the me.json mirror — the only thing that ever filled it) with NO
    account_snapshot must no longer light account_present nor NAV. If this
    starts passing as (True, 50000) someone re-introduced the dual-source
    split that caused the B051 production bug."""

    with Session(get_engine()) as session:
        session.add(
            Account(
                account_id="vestigial",
                name="Vestigial",
                base_currency="USD",
                cash=10_000.0,
                equity_value=40_000.0,
                as_of_date=date(2026, 6, 9),
            )
        )
        session.commit()
        assert aggregate_account_state(session, _FakeProvider({})) == (False, 0.0)
        assert aggregate_nav(session, _FakeProvider({})) == 0.0


# --- trust-nothing positions parse ------------------------------------------


def test_snapshot_positions_parse_drops_malformed_entries() -> None:
    snapshot = AccountSnapshot(
        id="parse-snap",
        snapshot_at=datetime(2026, 6, 9, 12, 0, 0),
        cash=100.0,
        base_currency="USD",
        positions=[
            {"symbol": "aapl", "shares": 10, "avg_cost": 150.0},
            {"symbol": "", "shares": 1},  # no symbol → dropped
            {"symbol": "MSFT", "shares": "garbage"},  # bad shares → dropped
            "not-a-dict",  # → dropped
        ],
        source="ui_edit",
        created_at=datetime(2026, 6, 9, 12, 0, 0),
    )
    positions, cash = snapshot_positions_and_cash(snapshot)
    assert positions == [("AAPL", 10.0)]
    assert cash == 100.0
    assert snapshot_positions_and_cash(None) == ([], 0.0)


# --- (★) route-level regression — the user-reported flow --------------------


def test_ui_saved_account_is_recognised_by_recommendations_and_home(
    initialised_db: str,
) -> None:
    """The exact production flow that broke: save the Account form (pure
    cash, new-user), then load Recommendations + Home. The ``account``
    table stays EMPTY throughout — exactly like production, where only the
    UI ever writes account state."""

    client = _authed_client()

    before = client.get("/api/recommendations/current").json()
    assert before["account_present"] is False

    put = client.put(
        "/api/execution/account",
        json={"cash": 25_000.0, "base_currency": "USD", "positions": []},
    )
    assert put.status_code == 200, put.text

    after = client.get("/api/recommendations/current").json()
    assert after["account_present"] is True

    # (d) the min_equity gate reads the snapshot equity, not the empty table.
    gates = {g["name"]: g for g in after["gate_checks"]}
    assert "25000.00" in gates["min_equity"]["detail"]

    # B046 soft-watch S1: Home NAV is the real cash balance, not 0.0.
    home = client.get("/api/home").json()
    assert home["nav"] == pytest.approx(25_000.0)


def test_ui_saved_account_with_positions_is_recognised(initialised_db: str) -> None:
    """Second leg of the user flow: re-save with holdings. Recommendations
    must keep recognising the account; NAV picks up cash (positions stay
    unmarked here — price_snapshot is empty — and degrade to nothing)."""

    client = _authed_client()
    put = client.put(
        "/api/execution/account",
        json={
            "cash": 1_000.0,
            "base_currency": "USD",
            "positions": [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.0}],
        },
    )
    assert put.status_code == 200, put.text

    payload = client.get("/api/recommendations/current").json()
    assert payload["account_present"] is True
    gates = {g["name"]: g for g in payload["gate_checks"]}
    assert "1000.00" in gates["min_equity"]["detail"]
