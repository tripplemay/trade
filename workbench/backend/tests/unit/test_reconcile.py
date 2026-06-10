"""B023 F005 — Reconcile + journal-history + slippage-analytics tests.

Acceptance pins:
1. Reconcile end-to-end inserts a new ``account_snapshot`` with
   ``source=fill_reconcile`` whose positions reflect the prior snapshot
   + the fills.
2. Re-running reconcile is idempotent — second call does NOT insert a
   duplicate snapshot and returns ``already_reconciled=True``.
3. Journal-history renders 12-month seed data sortable/filterable.
4. Slippage bps = (fill_price − reference) / reference × 10_000 signed
   per side ("buy" positive when overpaying, "sell" positive when
   underselling — both = unfavorable for the user).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.observability.active_users import active_users
from workbench_api.services.reconcile import (
    _apply_fills_to_positions,
    _compute_slippage_bps,
)
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
        {"email": ALLOWED_EMAIL, "sub": "reconcile-test", "iat": now, "exp": now + 3600},
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
    source: str = "bootstrap",
    snapshot_at: datetime | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=snap_id,
                snapshot_at=snapshot_at or datetime(2026, 5, 18, 10, 0, 0),
                cash=Decimal(str(cash)),
                base_currency="USD",
                positions=positions,
                source=source,
                created_at=snapshot_at or datetime(2026, 5, 18, 10, 0, 0),
            )
        )
        session.commit()


def _seed_ticket(
    *,
    ticket_id: str,
    snapshot_id: str = "snap-prior",
    status: str = "generated",
    ticket_date: date | None = None,
    created_at: datetime | None = None,
    executed_at: datetime | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            OrderTicket(
                id=ticket_id,
                ticket_date=ticket_date or date(2026, 5, 19),
                snapshot_id=snapshot_id,
                target_positions_id=f"tp-{ticket_id}",
                markdown_path=f"docs/runs/2026-05-19/order-ticket-{ticket_id}.md",
                status=status,
                created_at=created_at or datetime(2026, 5, 19, 10, 0, 0),
                executed_at=executed_at,
            )
        )
        session.commit()


def _seed_fills(
    *, ticket_id: str, rows: list[dict[str, Any]], source: str = "manual_entry"
) -> None:
    with Session(get_engine()) as session:
        for index, row in enumerate(rows):
            session.add(
                FillJournalEntry(
                    id=f"fill-{ticket_id}-{index}",
                    ticket_id=ticket_id,
                    order_seq=row.get("order_seq", index + 1),
                    symbol=row["symbol"],
                    side=row["side"],
                    shares=Decimal(str(row["shares"])),
                    fill_price=Decimal(str(row["fill_price"])),
                    commission=Decimal(str(row.get("commission", 0))),
                    fees=Decimal(str(row.get("fees", 0))),
                    currency=row.get("currency", "USD"),
                    filled_at=row.get("filled_at", datetime(2026, 5, 19, 16, 0, 0)),
                    source=source,
                    notes=row.get("notes"),
                    created_at=datetime(2026, 5, 19, 17, 0, 0),
                )
            )
        session.commit()


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------


def test_reconcile_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.post("/api/execution/reconcile/anything")
    assert response.status_code == 401


def test_journal_history_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/journal-history")
    assert response.status_code == 401


def test_slippage_analytics_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    client = TestClient(app)
    response = client.get("/api/execution/slippage-analytics")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Reconcile happy / unhappy paths
# ---------------------------------------------------------------------------


def test_reconcile_unknown_ticket_returns_404(initialised_db: str, tmp_path: Path) -> None:
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/does-not-exist")
    assert response.status_code == 404


def test_reconcile_no_fills_returns_409(initialised_db: str, tmp_path: Path) -> None:
    _seed_snapshot(snap_id="snap-prior", cash=100_000, positions=[])
    _seed_ticket(ticket_id="tkt-1")
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-1")
    assert response.status_code == 409


def test_reconcile_voided_ticket_returns_409(initialised_db: str, tmp_path: Path) -> None:
    _seed_snapshot(snap_id="snap-prior", cash=100_000, positions=[])
    _seed_ticket(ticket_id="tkt-1", status="voided")
    _seed_fills(
        ticket_id="tkt-1",
        rows=[
            {
                "symbol": "SPY",
                "side": "buy",
                "shares": 10,
                "fill_price": 500.0,
            }
        ],
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-1")
    assert response.status_code == 409


def test_reconcile_e2e_inserts_post_fill_snapshot(
    initialised_db: str, tmp_path: Path
) -> None:
    """Acceptance #1 — reconcile end-to-end produces the expected
    post-fill snapshot (positions delta + cash delta + source flag)."""

    _seed_snapshot(
        snap_id="snap-prior",
        cash=100_000.0,
        positions=[
            {"symbol": "SPY", "shares": 10, "avg_cost": 500.0},
        ],
    )
    _seed_ticket(ticket_id="tkt-1")
    _seed_fills(
        ticket_id="tkt-1",
        rows=[
            {
                "order_seq": 1,
                "symbol": "SPY",
                "side": "buy",
                "shares": 20,
                "fill_price": 510.0,
            },
            {
                "order_seq": 2,
                "symbol": "IEF",
                "side": "buy",
                "shares": 50,
                "fill_price": 94.0,
                "commission": 0.5,
                "fees": 0.1,
            },
        ],
    )

    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-1")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["already_reconciled"] is False
    assert payload["ticket_id"] == "tkt-1"
    assert payload["slippage_summary"]["fill_count"] == 2
    assert payload["snapshot_id"].startswith("snap-")

    # Inspect the persisted snapshot.
    with Session(get_engine()) as session:
        new_snap = session.get(AccountSnapshot, payload["snapshot_id"])
        assert new_snap is not None
        assert new_snap.source == "fill_reconcile"
        positions_by_symbol = {p["symbol"]: p for p in new_snap.positions}
        # SPY: prior 10 @ 500 + 20 @ 510 → 30 shares, avg ≈ 506.667
        assert positions_by_symbol["SPY"]["shares"] == pytest.approx(30.0)
        assert positions_by_symbol["SPY"]["avg_cost"] == pytest.approx(506.666666666, rel=1e-6)
        # IEF: 50 shares @ 94 (new)
        assert positions_by_symbol["IEF"]["shares"] == pytest.approx(50.0)
        assert positions_by_symbol["IEF"]["avg_cost"] == pytest.approx(94.0)
        # Cash: 100_000 - (20*510) - (50*94) - 0.5 - 0.1 = 100_000 - 10_200 - 4_700 - 0.6 = 85_099.4
        assert float(new_snap.cash) == pytest.approx(85_099.4)

        # Ticket flipped to executed + executed_at stamped.
        ticket = session.get(OrderTicket, "tkt-1")
        assert ticket is not None
        assert ticket.status == "executed"
        assert ticket.executed_at is not None


def test_reconcile_is_idempotent(initialised_db: str, tmp_path: Path) -> None:
    """Acceptance #2 — re-running reconcile does not duplicate the
    post-fill snapshot."""

    _seed_snapshot(
        snap_id="snap-prior",
        cash=100_000.0,
        positions=[{"symbol": "SPY", "shares": 10, "avg_cost": 500.0}],
    )
    _seed_ticket(ticket_id="tkt-1")
    _seed_fills(
        ticket_id="tkt-1",
        rows=[{"symbol": "SPY", "side": "buy", "shares": 5, "fill_price": 505.0}],
    )
    client = _authed_client(_settings(tmp_path))

    first = client.post("/api/execution/reconcile/tkt-1").json()
    second = client.post("/api/execution/reconcile/tkt-1").json()

    assert first["already_reconciled"] is False
    assert second["already_reconciled"] is True
    # Snapshot count for source=fill_reconcile must stay at 1.
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    with Session(get_engine()) as session:
        stmt = (
            sa_select(func.count())
            .select_from(AccountSnapshot)
            .where(AccountSnapshot.source == "fill_reconcile")
        )
        count = session.execute(stmt).scalar_one()
        assert count == 1


def test_slippage_bps_sign_convention() -> None:
    """Acceptance #4 — bps signed correctly per side.

    Buy at 510 vs reference 500: paid more → positive (unfavorable).
    Sell at 510 vs reference 500: received more → negative (favorable).
    Buy at 490 vs reference 500: paid less → negative (favorable).
    Sell at 490 vs reference 500: received less → positive (unfavorable).
    """

    approx = pytest.approx
    assert _compute_slippage_bps(side="buy", fill_price=510, reference_price=500) == approx(200.0)
    assert _compute_slippage_bps(side="sell", fill_price=510, reference_price=500) == approx(-200.0)
    assert _compute_slippage_bps(side="buy", fill_price=490, reference_price=500) == approx(-200.0)
    assert _compute_slippage_bps(side="sell", fill_price=490, reference_price=500) == approx(200.0)
    # Zero / non-positive reference → 0 (defensive).
    assert _compute_slippage_bps(side="buy", fill_price=100, reference_price=0) == 0.0


def test_reconcile_includes_signed_per_fill_slippage(
    initialised_db: str, tmp_path: Path
) -> None:
    _seed_snapshot(
        snap_id="snap-prior",
        cash=10_000,
        positions=[
            {"symbol": "SPY", "shares": 10, "avg_cost": 500.0},
            {"symbol": "IEF", "shares": 20, "avg_cost": 100.0},
        ],
    )
    _seed_ticket(ticket_id="tkt-1")
    _seed_fills(
        ticket_id="tkt-1",
        rows=[
            # Buy SPY above reference → +200 bps
            {"order_seq": 1, "symbol": "SPY", "side": "buy", "shares": 5, "fill_price": 510.0},
            # Sell IEF above reference → −200 bps (favorable)
            {"order_seq": 2, "symbol": "IEF", "side": "sell", "shares": 5, "fill_price": 102.0},
        ],
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.post("/api/execution/reconcile/tkt-1").json()
    by_symbol = {f["symbol"]: f for f in payload["fill_slippages"]}
    assert by_symbol["SPY"]["slippage_bps"] == pytest.approx(200.0)
    assert by_symbol["IEF"]["slippage_bps"] == pytest.approx(-200.0)


# ---------------------------------------------------------------------------
# Journal history + slippage analytics
# ---------------------------------------------------------------------------


def test_journal_history_lists_12_months_seeded(
    initialised_db: str, tmp_path: Path
) -> None:
    """Acceptance #3 — 12 monthly tickets render."""

    _seed_snapshot(snap_id="snap-prior", cash=10_000, positions=[])
    for month_offset in range(12):
        base = datetime(2026, 5, 18) - timedelta(days=30 * month_offset)
        _seed_ticket(
            ticket_id=f"tkt-month-{month_offset}",
            snapshot_id="snap-prior",
            status="executed",
            ticket_date=base.date(),
            created_at=base,
            executed_at=base + timedelta(hours=5),
        )

    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/journal-history").json()
    assert len(payload["items"]) == 12
    # Newest-first ordering.
    dates = [item["ticket_date"] for item in payload["items"]]
    assert dates == sorted(dates, reverse=True)


def test_journal_history_since_filter(initialised_db: str, tmp_path: Path) -> None:
    _seed_snapshot(snap_id="snap-prior", cash=10_000, positions=[])
    _seed_ticket(
        ticket_id="tkt-old",
        ticket_date=date(2026, 1, 1),
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    _seed_ticket(
        ticket_id="tkt-new",
        ticket_date=date(2026, 5, 1),
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    )
    client = _authed_client(_settings(tmp_path))
    payload = client.get(
        "/api/execution/journal-history?since=2026-04-01"
    ).json()
    assert [item["ticket_id"] for item in payload["items"]] == ["tkt-new"]


def test_slippage_analytics_invalid_window_returns_422(
    initialised_db: str, tmp_path: Path
) -> None:
    client = _authed_client(_settings(tmp_path))
    response = client.get("/api/execution/slippage-analytics?window=bogus")
    # FastAPI's regex validation surfaces as 422.
    assert response.status_code == 422


def test_slippage_analytics_aggregates_rolling_window(
    initialised_db: str, tmp_path: Path
) -> None:
    """Seeds two executed tickets within the 3-month window and asserts
    the rolling_avg_bps is the mean of their per-ticket avg bps."""

    _seed_snapshot(
        snap_id="snap-prior",
        cash=10_000,
        positions=[{"symbol": "SPY", "shares": 10, "avg_cost": 500.0}],
    )
    today = datetime.now().replace(microsecond=0)
    for index, day_offset in enumerate([5, 30]):
        ticket_id = f"tkt-recent-{index}"
        executed_at = today - timedelta(days=day_offset)
        _seed_ticket(
            ticket_id=ticket_id,
            status="executed",
            ticket_date=executed_at.date(),
            created_at=executed_at - timedelta(hours=1),
            executed_at=executed_at,
        )
        _seed_fills(
            ticket_id=ticket_id,
            rows=[
                {
                    "symbol": "SPY",
                    "side": "buy",
                    "shares": 1,
                    "fill_price": 510.0 if index == 0 else 505.0,
                }
            ],
        )

    client = _authed_client(_settings(tmp_path))
    payload = client.get("/api/execution/slippage-analytics?window=3m").json()
    # Per-ticket avg bps: 200, 100 → mean 150.
    assert payload["rolling_avg_bps"] == pytest.approx(150.0, rel=1e-6)
    assert payload["window"] == "3m"
    assert len(payload["trend"]) >= 1


# --- B048 F002: sleeve tag preserved through reconcile rebuild ------------


def _fill(symbol: str, side: str, shares: float, price: float) -> SimpleNamespace:
    """A minimal fill object matching the attrs _apply_fills_to_positions reads."""

    return SimpleNamespace(
        symbol=symbol, side=side, shares=shares, fill_price=price,
        commission=0.0, fees=0.0,
    )


def test_apply_fills_preserves_prior_sleeve_tag() -> None:
    """A held position's sleeve tag survives a reconcile rebuild (buy adds
    shares, tag stays); a symbol introduced by a fill has no prior tag."""

    prior = [
        {"symbol": "SPY", "shares": 100.0, "avg_cost": 500.0, "sleeve": "momentum"},
        {"symbol": "GLD", "shares": 10.0, "avg_cost": 180.0, "sleeve": "risk_parity"},
    ]
    fills = [
        _fill("SPY", "buy", 10.0, 510.0),   # accumulate a tagged holding
        _fill("EEM", "buy", 5.0, 40.0),     # brand-new symbol, no prior tag
    ]
    new_positions, _cash, violations = _apply_fills_to_positions(prior, fills)
    assert violations == []
    by_symbol = {p["symbol"]: p for p in new_positions}
    assert by_symbol["SPY"]["sleeve"] == "momentum"
    assert by_symbol["SPY"]["shares"] == 110.0
    assert by_symbol["GLD"]["sleeve"] == "risk_parity"
    # New symbol from a fill carries no fabricated tag (reader → unclassified).
    assert "sleeve" not in by_symbol["EEM"]


def test_apply_fills_tagless_prior_stays_tagless() -> None:
    """A pre-B048 prior position (no sleeve key) stays byte-identical —
    reconcile never invents a tag."""

    prior = [{"symbol": "IEF", "shares": 50.0, "avg_cost": 94.0}]
    fills = [_fill("IEF", "sell", 10.0, 95.0)]
    new_positions, _cash, violations = _apply_fills_to_positions(prior, fills)
    assert violations == []
    assert new_positions == [{"symbol": "IEF", "shares": 40.0, "avg_cost": 94.0}]


# ---------------------------------------------------------------------------
# B053 F001 — impossible-state guards: oversell / negative cash are rejected
# (409) instead of silently "corrected". Fail-fast, not silent clamp.
# ---------------------------------------------------------------------------


def test_apply_fills_detects_oversell_violation() -> None:
    """Selling more than held records a violation (not a silent floor-to-0)
    and reports the held vs sold counts + the line number."""

    prior = [{"symbol": "SPY", "shares": 10.0, "avg_cost": 500.0}]
    fills = [_fill("SPY", "sell", 25.0, 505.0)]
    new_positions, _cash, violations = _apply_fills_to_positions(prior, fills)
    assert violations == [
        {"symbol": "SPY", "sell_shares": 25.0, "held_shares": 10.0, "line": 1}
    ]
    # Position is still floored so the caller can compute, but it will reject.
    by_symbol = {p["symbol"]: p for p in new_positions}
    assert by_symbol["SPY"]["shares"] == 0.0


def test_apply_fills_sell_exactly_to_zero_is_not_a_violation() -> None:
    """Selling the full held quantity is legal — no violation."""

    prior = [{"symbol": "SPY", "shares": 50.0, "avg_cost": 500.0}]
    fills = [_fill("SPY", "sell", 50.0, 510.0)]
    new_positions, _cash, violations = _apply_fills_to_positions(prior, fills)
    assert violations == []
    by_symbol = {p["symbol"]: p for p in new_positions}
    assert by_symbol["SPY"]["shares"] == 0.0


def test_apply_fills_sell_within_float_epsilon_is_not_a_violation() -> None:
    """A sub-micro-share float residual (0.3 held vs 0.1+0.2 sold) is benign
    noise, floored to 0 without flagging an oversell."""

    prior = [{"symbol": "SPY", "shares": 0.3, "avg_cost": 500.0}]
    fills = [_fill("SPY", "sell", 0.1 + 0.2, 510.0)]  # 0.30000000000000004
    _new_positions, _cash, violations = _apply_fills_to_positions(prior, fills)
    assert violations == []


def test_reconcile_oversell_returns_409_with_line_info(
    initialised_db: str, tmp_path: Path
) -> None:
    """End-to-end: a sell exceeding held shares is rejected 409 with the
    offending symbol + sold/held counts, and nothing is persisted."""

    _seed_snapshot(
        snap_id="snap-prior",
        cash=100_000.0,
        positions=[{"symbol": "SPY", "shares": 10, "avg_cost": 500.0}],
    )
    _seed_ticket(ticket_id="tkt-os")
    _seed_fills(
        ticket_id="tkt-os",
        rows=[{"order_seq": 1, "symbol": "SPY", "side": "sell", "shares": 20, "fill_price": 510.0}],
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-os")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "SPY" in detail
    assert "20" in detail and "10" in detail

    # Nothing persisted: no fill_reconcile snapshot, ticket still generated.
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    with Session(get_engine()) as session:
        count = session.execute(
            sa_select(func.count())
            .select_from(AccountSnapshot)
            .where(AccountSnapshot.source == "fill_reconcile")
        ).scalar_one()
        assert count == 0
        ticket = session.get(OrderTicket, "tkt-os")
        assert ticket is not None
        assert ticket.status == "generated"
        assert ticket.executed_at is None


def test_reconcile_negative_cash_returns_409(
    initialised_db: str, tmp_path: Path
) -> None:
    """A buy that would overdraw cash is rejected 409 (no silent max(0,...))
    with the shortfall surfaced; nothing is persisted."""

    _seed_snapshot(snap_id="snap-prior", cash=100.0, positions=[])
    _seed_ticket(ticket_id="tkt-nc")
    _seed_fills(
        ticket_id="tkt-nc",
        rows=[{"order_seq": 1, "symbol": "SPY", "side": "buy", "shares": 10, "fill_price": 500.0}],
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-nc")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    # Shortfall = 10*500 - 100 = 4900.
    assert "4900" in detail

    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    with Session(get_engine()) as session:
        count = session.execute(
            sa_select(func.count())
            .select_from(AccountSnapshot)
            .where(AccountSnapshot.source == "fill_reconcile")
        ).scalar_one()
        assert count == 0
        ticket = session.get(OrderTicket, "tkt-nc")
        assert ticket is not None
        assert ticket.status == "generated"


def test_reconcile_sell_exactly_to_zero_succeeds(
    initialised_db: str, tmp_path: Path
) -> None:
    """Boundary: selling the entire held quantity reconciles normally."""

    _seed_snapshot(
        snap_id="snap-prior",
        cash=100_000.0,
        positions=[{"symbol": "SPY", "shares": 10, "avg_cost": 500.0}],
    )
    _seed_ticket(ticket_id="tkt-z")
    _seed_fills(
        ticket_id="tkt-z",
        rows=[{"order_seq": 1, "symbol": "SPY", "side": "sell", "shares": 10, "fill_price": 510.0}],
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-z")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["already_reconciled"] is False
    with Session(get_engine()) as session:
        new_snap = session.get(AccountSnapshot, payload["snapshot_id"])
        assert new_snap is not None
        by_symbol = {p["symbol"]: p for p in new_snap.positions}
        assert by_symbol["SPY"]["shares"] == 0.0
        # Cash credited by the sale: 100_000 + 10*510 = 105_100.
        assert float(new_snap.cash) == pytest.approx(105_100.0)


def test_reconcile_cash_exactly_zero_succeeds(
    initialised_db: str, tmp_path: Path
) -> None:
    """Boundary: spending cash down to exactly 0 is legal (not negative)."""

    _seed_snapshot(snap_id="snap-prior", cash=5_000.0, positions=[])
    _seed_ticket(ticket_id="tkt-c0")
    _seed_fills(
        ticket_id="tkt-c0",
        rows=[{"order_seq": 1, "symbol": "SPY", "side": "buy", "shares": 10, "fill_price": 500.0}],
    )
    client = _authed_client(_settings(tmp_path))
    response = client.post("/api/execution/reconcile/tkt-c0")
    assert response.status_code == 200, response.text
    payload = response.json()
    with Session(get_engine()) as session:
        new_snap = session.get(AccountSnapshot, payload["snapshot_id"])
        assert new_snap is not None
        assert float(new_snap.cash) == pytest.approx(0.0)
