"""``workbench-bootstrap`` happy-path + idempotency coverage.

B051: the me.json mirror now ALSO seeds ``account_snapshot`` — the single
source of truth every read path consumes (NAV / recommendations
``account_present`` / execution). The ``account`` row stays as a
backward-compat mirror only.
"""

from __future__ import annotations

import contextlib
import json
from decimal import Decimal
from pathlib import Path

from workbench_api.cli.bootstrap import run
from workbench_api.db.repositories import AccountRepository, BacklogRepository
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.symbol_name import SymbolNameRepository
from workbench_api.db.session import get_session
from workbench_api.monitoring.trial_backfill import HISTORICAL_TRIALS
from workbench_api.monitoring.trial_backfill_b081 import (
    B081_AB_TRIALS,
    B081_AUDIT_TRIALS,
)
from workbench_api.monitoring.trial_backfill_b082 import B082_TRIALS
from workbench_api.monitoring.trial_backfill_b083 import B083_TRIALS
from workbench_api.services.nav import aggregate_account_state
from workbench_api.symbols.names import CURATED_SYMBOL_NAMES

_N_CURATED = len(CURATED_SYMBOL_NAMES)
_N_TRIALS = (  # B080 27 + B081 F004 8 + B081 F005 audit 6 + B082 F002 6 + B083 F002 1
    len(HISTORICAL_TRIALS)
    + len(B081_AB_TRIALS)
    + len(B081_AUDIT_TRIALS)
    + len(B082_TRIALS)
    + len(B083_TRIALS)
)


def _seed_repo_root(repo_root: Path) -> None:
    (repo_root / "accounts").mkdir(parents=True, exist_ok=True)
    (repo_root / "accounts" / "me.json").write_text(
        json.dumps(
            {
                "account_id": "research-mvp",
                "name": "Research MVP",
                "base_currency": "USD",
                "cash": "250000",
                "equity_value": "0",
                "as_of_date": "2026-05-15",
            }
        )
    )
    (repo_root / "backlog.json").write_text(
        json.dumps(
            [
                {
                    "id": "BL-X-1",
                    "title": "Task one",
                    "description": "First seed",
                    "priority": "low",
                    "decisions": ["d1"],
                    "confirmed_at": "2026-05-15",
                    "source": "unit-test",
                },
                {
                    "id": "BL-X-2",
                    "title": "Task two",
                    "description": "Second seed",
                    "priority": "high",
                    "decisions": [],
                    "confirmed_at": "2026-05-15",
                },
            ]
        )
    )


def test_bootstrap_imports_repo_root_files(initialised_db: str, tmp_path: Path) -> None:
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    _seed_repo_root(repo_root)

    counts = run(repo_root)
    assert counts == {
        "accounts": 1, "backlog": 2, "symbol_names": _N_CURATED,
        "trials": _N_TRIALS, "oos_cards": 1,
    }

    gen = get_session()
    session = next(gen)
    account = AccountRepository(session).get_by_id("research-mvp")
    assert account is not None
    assert account.cash == Decimal("250000")
    # B051: the seed also lands in account_snapshot (the table every read
    # path consumes), so a me.json-seeded install is recognised end-to-end.
    snapshot = AccountSnapshotRepository(session).latest()
    assert snapshot is not None
    assert snapshot.id == "snap-bootstrap-research-mvp"
    assert snapshot.source == "bootstrap"
    assert snapshot.cash == Decimal("250000")
    assert snapshot.positions == []
    present, nav = aggregate_account_state(session)
    assert present is True
    assert nav == 250000.0
    backlog = {row.id: row for row in BacklogRepository(session).list_all()}
    assert set(backlog) == {"BL-X-1", "BL-X-2"}
    assert backlog["BL-X-2"].priority == "high"
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_is_idempotent(initialised_db: str, tmp_path: Path) -> None:
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    _seed_repo_root(repo_root)

    run(repo_root)
    counts = run(repo_root)
    assert counts == {
        "accounts": 1, "backlog": 2, "symbol_names": _N_CURATED,
        "trials": _N_TRIALS, "oos_cards": 1,
    }

    gen = get_session()
    session = next(gen)
    assert AccountRepository(session).count() == 1
    # B079 F001: the curated seed upserts in place — re-running does not stack rows.
    assert SymbolNameRepository(session).count() == _N_CURATED
    # B051: the deterministic snapshot id upserts in place — re-running the
    # seed must not stack a second snapshot row.
    assert AccountSnapshotRepository(session).count() == 1
    assert BacklogRepository(session).count() == 2
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_positions_round_trip_into_snapshot(
    initialised_db: str, tmp_path: Path
) -> None:
    """An me.json carrying a positions list lands verbatim (normalised
    symbol case) in the snapshot — the round-trip shape AccountSnapshot
    was designed for."""

    repo_root = tmp_path / "fake-repo"
    (repo_root / "accounts").mkdir(parents=True)
    (repo_root / "accounts" / "me.json").write_text(
        json.dumps(
            {
                "account_id": "research-mvp",
                "base_currency": "USD",
                "cash": "1000",
                "as_of_date": "2026-06-01",
                "positions": [
                    {"symbol": "aapl", "shares": 10, "avg_cost": 150.0, "sleeve": "regime"},
                ],
            }
        )
    )

    run(repo_root)

    gen = get_session()
    session = next(gen)
    snapshot = AccountSnapshotRepository(session).latest()
    assert snapshot is not None
    assert snapshot.positions == [
        {"symbol": "AAPL", "shares": 10.0, "avg_cost": 150.0, "sleeve": "regime"}
    ]
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_future_as_of_date_never_outranks_a_ui_edit(
    initialised_db: str, tmp_path: Path
) -> None:
    """A future me.json ``as_of_date`` is clamped to *now* — un-clamped, the
    seed row's future ``snapshot_at`` would win ``latest()`` over every
    subsequent UI edit, re-introducing the exact B051 "UI-saved account is
    invisible" bug via a date-ordering flip."""

    from datetime import UTC, datetime

    from workbench_api.db.models.account_snapshot import AccountSnapshot

    repo_root = tmp_path / "fake-repo"
    (repo_root / "accounts").mkdir(parents=True)
    (repo_root / "accounts" / "me.json").write_text(
        json.dumps(
            {
                "account_id": "research-mvp",
                "cash": "1000",
                "as_of_date": "2099-01-01",  # operator typo / target date
            }
        )
    )

    run(repo_root)

    gen = get_session()
    session = next(gen)
    seeded = AccountSnapshotRepository(session).latest()
    assert seeded is not None
    now = datetime.now(UTC).replace(tzinfo=None)
    assert seeded.snapshot_at <= now

    # A UI edit written right after the seed must become latest().
    ui_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        AccountSnapshot(
            id="snap-ui-after-seed",
            snapshot_at=ui_at,
            cash=Decimal("2000"),
            base_currency="USD",
            positions=[],
            source="ui_edit",
            created_at=ui_at,
        )
    )
    session.commit()
    latest = AccountSnapshotRepository(session).latest()
    assert latest is not None
    assert latest.source == "ui_edit"
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_handles_missing_files(initialised_db: str, tmp_path: Path) -> None:
    """A fresh clone may have no accounts/me.json and no backlog.json; the
    CLI must succeed with zero imports rather than crashing.
    """

    repo_root = tmp_path / "empty-repo"
    repo_root.mkdir()
    counts = run(repo_root)
    # B079 F001: the curated symbol-name seed is code-resident (not a repo file),
    # so it lands even on a bare clone with no accounts/backlog files.
    assert counts == {
        "accounts": 0, "backlog": 0, "symbol_names": _N_CURATED,
        "trials": _N_TRIALS, "oos_cards": 1,
    }

    gen = get_session()
    session = next(gen)
    names = SymbolNameRepository(session).get_names(["AAPL", "0700.HK", "600519.SH"])
    assert names["AAPL"] == "Apple Inc."
    assert names["0700.HK"] == "Tencent"
    with contextlib.suppress(StopIteration):
        next(gen)
