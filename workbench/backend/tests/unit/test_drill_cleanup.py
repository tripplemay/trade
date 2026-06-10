"""B052 F001 — drill-data cleanup CLI.

Production bug (user-reported 2026-06-10): a pure-cash new account showed a
fake 59.60% master drawdown + tripped kill-switch because past L2 acceptance
drills left snapshots/tickets/fills in the append-only execution tables
(incl. the BL-B023-S2 red-state drill's artificial ~$126k NAV peak), and
``reconstruct_nav_history`` rebuilds over ALL history.

Pins, per the F001 acceptance:

* dry-run (default) deletes NOTHING and previews both delete + keep sets;
* ``--apply`` deletes exactly the pre-cutoff rows across the three
  execution-domain tables and empties ``risk_explanation_snapshot``;
* rows at/after the cutoff are fully preserved;
* cutoff resolves from a snapshot id (kept) or an ISO date; unknown id fails
  loudly without deleting;
* a REAL fill entered after the cutoff with a backdated ``filled_at`` is kept
  (the created_at-axis pin);
* §12.11.1 env guard: no env → loud non-zero exit before any DB access;
* empty tables → graceful zero-count run.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.cli import drill_cleanup
from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.models.risk_explanation_snapshot import RiskExplanationSnapshot
from workbench_api.db.require_production_db import ALLOW_DEV_DB_ENV

CUTOFF = datetime(2026, 6, 10, 9, 0, 0)
"""The user's first REAL snapshot — everything strictly before it is drill."""


def _snapshot(
    id_: str,
    at: datetime,
    *,
    cash: float,
    positions: list[dict[str, object]] | None = None,
) -> AccountSnapshot:
    return AccountSnapshot(
        id=id_,
        snapshot_at=at,
        cash=Decimal(str(cash)),
        base_currency="USD",
        positions=positions or [],
        source="ui_edit",
        created_at=at,
    )


def _ticket(id_: str, created_at: datetime) -> OrderTicket:
    return OrderTicket(
        id=id_,
        ticket_date=created_at.date(),
        snapshot_id="snap-x",
        target_positions_id="tp-x",
        markdown_path=f"runs/{id_}.md",
        status="generated",
        created_at=created_at,
    )


def _fill(
    id_: str,
    created_at: datetime,
    *,
    filled_at: datetime | None = None,
) -> FillJournalEntry:
    return FillJournalEntry(
        id=id_,
        ticket_id=f"tkt-{id_}",
        order_seq=1,
        symbol="AAPL",
        side="buy",
        shares=Decimal("10"),
        fill_price=Decimal("100"),
        commission=Decimal("0"),
        fees=Decimal("0"),
        currency="USD",
        filled_at=filled_at or created_at,
        source="manual_entry",
        created_at=created_at,
    )


def _seed_polluted_history(session: Session) -> None:
    """Drill rows before the cutoff (incl. the fake ~$126k peak) + the user's
    real rows at/after it."""

    session.add_all(
        [
            # --- drill rows (BEFORE cutoff) → must be deleted ---
            _snapshot("drill-base", datetime(2026, 6, 7, 10, 0, 0), cash=35_246.0),
            _snapshot("drill-peak", datetime(2026, 6, 8, 10, 0, 0), cash=126_000.0),
            _ticket("drill-ticket", datetime(2026, 6, 8, 11, 0, 0)),
            _fill("drill-fill-1", datetime(2026, 6, 8, 11, 30, 0)),
            _fill(
                # Backdated drill fill (wash-sale drills do this): created
                # during the drill → still swept by the created_at axis.
                "drill-fill-2",
                datetime(2026, 6, 8, 11, 31, 0),
                filled_at=datetime(2026, 5, 10, 16, 0, 0),
            ),
            # --- the user's REAL rows (AT/AFTER cutoff) → must be kept ---
            _snapshot("real-cash", CUTOFF, cash=50_000.0),
            _snapshot(
                "real-positions",
                datetime(2026, 6, 10, 12, 0, 0),
                cash=49_000.0,
                positions=[{"symbol": "SGOV", "shares": 10, "avg_cost": 100.0}],
            ),
            _ticket("real-ticket", datetime(2026, 6, 10, 13, 0, 0)),
            # REAL fill entered after cutoff with a backdated filled_at (old
            # broker CSV import) — the created_at axis must keep it.
            _fill(
                "real-backdated-fill",
                datetime(2026, 6, 10, 14, 0, 0),
                filled_at=datetime(2026, 6, 1, 16, 0, 0),
            ),
            # Stale explanation citing the fake drawdown → always deleted.
            RiskExplanationSnapshot(
                id=uuid4(),
                as_of_date=date(2026, 6, 9),
                master_dd=0.596,
                state="red",
                explanation="master drawdown 59.60% ...",
                created_at=datetime(2026, 6, 9, 3, 30, 0),
            ),
        ]
    )
    session.commit()


def _counts(session: Session) -> dict[str, int]:
    return {
        "snapshots": len(list(session.execute(select(AccountSnapshot)).scalars())),
        "tickets": len(list(session.execute(select(OrderTicket)).scalars())),
        "fills": len(list(session.execute(select(FillJournalEntry)).scalars())),
        "explanations": len(
            list(session.execute(select(RiskExplanationSnapshot)).scalars())
        ),
    }


def test_dry_run_is_default_and_deletes_nothing(
    initialised_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with Session(get_engine()) as session:
        _seed_polluted_history(session)

    assert drill_cleanup.main(["--keep-from", CUTOFF.isoformat()]) == 0

    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "nothing was deleted" in out
    # The preview lists both sections in full.
    for fragment in ("drill-base", "drill-peak", "drill-ticket", "drill-fill-1"):
        assert fragment in out
    for fragment in ("real-cash", "real-positions", "real-ticket", "real-backdated-fill"):
        assert fragment in out
    assert "126000.00" in out  # the fake peak's cash is visible for boundary review

    with Session(get_engine()) as session:
        assert _counts(session) == {
            "snapshots": 4,
            "tickets": 2,
            "fills": 3,
            "explanations": 1,
        }


def test_apply_deletes_exactly_before_cutoff(
    initialised_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with Session(get_engine()) as session:
        _seed_polluted_history(session)

    assert drill_cleanup.main(["--keep-from", CUTOFF.isoformat(), "--apply"]) == 0

    out = capsys.readouterr().out
    assert (
        "deleted: account_snapshot=2, order_ticket=1, fill_journal_entry=2, "
        "risk_explanation_snapshot=1" in out
    )
    assert "workbench-risk-explanation.service" in out  # regenerate hint

    with Session(get_engine()) as session:
        snapshots = {s.id for s in session.execute(select(AccountSnapshot)).scalars()}
        tickets = {t.id for t in session.execute(select(OrderTicket)).scalars()}
        fills = {f.id for f in session.execute(select(FillJournalEntry)).scalars()}
        assert snapshots == {"real-cash", "real-positions"}
        assert tickets == {"real-ticket"}
        # The created_at axis keeps the real backdated-filled_at fill.
        assert fills == {"real-backdated-fill"}
        assert _counts(session)["explanations"] == 0


def test_keep_from_snapshot_id_resolves_and_keeps_that_snapshot(
    initialised_db: str,
) -> None:
    with Session(get_engine()) as session:
        _seed_polluted_history(session)

    assert drill_cleanup.main(["--keep-from", "real-cash", "--apply"]) == 0

    with Session(get_engine()) as session:
        snapshots = {s.id for s in session.execute(select(AccountSnapshot)).scalars()}
        assert snapshots == {"real-cash", "real-positions"}


def test_unknown_snapshot_id_fails_loudly_without_deleting(
    initialised_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with Session(get_engine()) as session:
        _seed_polluted_history(session)

    assert drill_cleanup.main(["--keep-from", "no-such-snapshot", "--apply"]) == 2
    err = capsys.readouterr().err
    assert "no-such-snapshot" in err

    with Session(get_engine()) as session:
        assert _counts(session)["snapshots"] == 4  # untouched


def test_env_guard_blocks_scratch_db_before_any_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§12.11.1 — without WORKBENCH_DB_URL the CLI must exit non-zero before
    opening any session (never silently target the dev scratch DB)."""

    monkeypatch.delenv("WORKBENCH_DB_URL", raising=False)
    monkeypatch.delenv(ALLOW_DEV_DB_ENV, raising=False)

    def _boom() -> object:  # pragma: no cover — must never run
        raise AssertionError("get_engine() called — guard did not fire first")

    monkeypatch.setattr(drill_cleanup, "get_engine", _boom)
    assert drill_cleanup.main(["--keep-from", "2026-06-10"]) == 1
    assert "::error::" in capsys.readouterr().err


def test_empty_tables_are_graceful(
    initialised_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert drill_cleanup.main(["--keep-from", "2026-06-10"]) == 0
    out = capsys.readouterr().out
    assert "account_snapshot (snapshot_at < cutoff): 0" in out

    assert drill_cleanup.main(["--keep-from", "2026-06-10", "--apply"]) == 0
    out = capsys.readouterr().out
    assert (
        "deleted: account_snapshot=0, order_ticket=0, fill_journal_entry=0, "
        "risk_explanation_snapshot=0" in out
    )
    # No explanations were deleted → no misleading regenerate hint.
    assert "workbench-risk-explanation.service" not in out


def test_iso_date_cutoff_is_midnight(initialised_db: str) -> None:
    """An ISO date resolves to midnight: a snapshot ON the date is kept."""

    with Session(get_engine()) as session:
        session.add_all(
            [
                _snapshot("before", datetime(2026, 6, 9, 23, 59, 0), cash=1.0),
                _snapshot("on-date", datetime(2026, 6, 10, 0, 0, 0), cash=2.0),
            ]
        )
        session.commit()

    assert drill_cleanup.main(["--keep-from", "2026-06-10", "--apply"]) == 0

    with Session(get_engine()) as session:
        ids = {s.id for s in session.execute(select(AccountSnapshot)).scalars()}
        assert ids == {"on-date"}


def test_module_never_imports_trade() -> None:
    """§12.10.2 — pure DB operations; the cleanup CLI must not import the
    trade package."""

    import ast
    from pathlib import Path

    src = (
        Path(drill_cleanup.__file__).read_text(encoding="utf-8")
        if hasattr(drill_cleanup, "__file__") and drill_cleanup.__file__
        else ""
    )
    assert src, "drill_cleanup module source not found"
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            assert all(not a.name.startswith("trade") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not (node.level == 0 and (module == "trade" or module.startswith("trade.")))
