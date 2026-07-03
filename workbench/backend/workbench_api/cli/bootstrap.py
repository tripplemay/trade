"""``workbench-bootstrap`` — idempotent loader for the run-time DB.

Reads two repo-root files (both optional, both missing is OK on a fresh
clone):

* ``accounts/me.json``  — research-account state, mirrored into ``account``
  **and** ``account_snapshot`` (B051: ``account_snapshot`` is the single
  source of truth every read path consumes — NAV, recommendations
  ``account_present``, execution — so the seed must land there too; the
  ``account`` row is kept only as a backward-compat mirror). The snapshot
  id is deterministic (``snap-bootstrap-<account_id>``) and ``snapshot_at``
  is me.json's ``as_of_date``, so re-runs upsert in place and a later UI
  edit (``snapshot_at`` = now) always stays the ``latest()`` winner.
* ``backlog.json``      — research backlog, mirrored into ``backlog_entry``

Each row is upserted via the Repository layer so re-running the command is
a no-op.

Designed to be safe to run before *or* after ``alembic upgrade head`` is
applied to the live DB; if tables are missing the command fails loudly so
operators notice.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine, reset_engine
from workbench_api.db.models import Account, BacklogEntry
from workbench_api.db.models.account_snapshot import (
    DEFAULT_STRATEGY_ID,
    AccountSnapshot,
)
from workbench_api.db.repositories import AccountRepository, BacklogRepository
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.symbol_name import SymbolNameRepository
from workbench_api.db.session import get_session
from workbench_api.settings import get_settings
from workbench_api.symbols.names import CURATED_SYMBOL_NAMES


def _coerce_account(payload: dict[str, Any]) -> Account:
    return Account(
        account_id=str(payload["account_id"]),
        name=str(payload.get("name", payload["account_id"])),
        base_currency=str(payload.get("base_currency", "USD")),
        cash=Decimal(str(payload.get("cash", "0"))),
        equity_value=Decimal(str(payload.get("equity_value", "0"))),
        as_of_date=date.fromisoformat(str(payload["as_of_date"])),
    )


def _coerce_position(entry: Any) -> dict[str, Any]:
    """Validate one me.json position entry into the stored JSON shape.

    Fails loudly on a malformed entry (CLI seed posture — a bad seed file
    should stop the operator, not silently drop a holding)."""

    if not isinstance(entry, dict) or not str(entry.get("symbol", "")).strip():
        raise ValueError(f"accounts/me.json position must be an object with a symbol: {entry!r}")
    position: dict[str, Any] = {
        "symbol": str(entry["symbol"]).strip().upper(),
        "shares": float(entry.get("shares", 0.0)),
        "avg_cost": float(entry.get("avg_cost", 0.0)),
    }
    if entry.get("sleeve"):
        position["sleeve"] = str(entry["sleeve"])
    return position


def _coerce_account_snapshot(payload: dict[str, Any]) -> AccountSnapshot:
    """Build the ``account_snapshot`` seed row for one me.json account (B051).

    Deterministic id + ``snapshot_at`` = ``as_of_date`` midnight keep the
    command idempotent and let any later UI edit win ``latest()``. A future
    ``as_of_date`` is clamped to *now* — otherwise the seed row would
    outrank every subsequent UI edit in ``latest()`` (ordered by
    ``snapshot_at``), re-introducing the exact "UI-saved account is
    invisible" bug B051 fixes. Note an me.json ``equity_value`` without a
    ``positions`` list cannot be represented here (snapshot equity is
    derived mark-to-market from positions); such a seed contributes cash
    only to NAV.
    """

    as_of = date.fromisoformat(str(payload["as_of_date"]))
    # Naive-UTC like the UI write path (services.execution.update_account).
    now = datetime.now(UTC).replace(tzinfo=None)
    snapshot_at = min(datetime.combine(as_of, time.min), now)
    raw_positions = payload.get("positions", []) or []
    if not isinstance(raw_positions, list):
        raise ValueError("accounts/me.json positions must be a list of objects")
    return AccountSnapshot(
        id=f"snap-bootstrap-{payload['account_id']}",
        snapshot_at=snapshot_at,
        # B057 F004 — the bootstrap seeds the Master account. Set strategy_id
        # explicitly (not via the column default) so the deterministic-id re-run
        # merges as an UPDATE without nulling the column (column defaults apply on
        # INSERT only, never on the merge-driven UPDATE that idempotency relies on).
        strategy_id=DEFAULT_STRATEGY_ID,
        cash=Decimal(str(payload.get("cash", "0"))),
        base_currency=str(payload.get("base_currency", "USD")),
        positions=[_coerce_position(entry) for entry in raw_positions],
        source="bootstrap",
        created_at=snapshot_at,
    )


def _coerce_backlog(payload: dict[str, Any]) -> BacklogEntry:
    return BacklogEntry(
        id=str(payload["id"]),
        title=str(payload["title"]),
        description=str(payload.get("description", "")),
        priority=str(payload.get("priority", "medium")),
        decisions=list(payload.get("decisions", []) or []),
        confirmed_at=str(payload.get("confirmed_at", "")),
        source=payload.get("source"),
    )


def _import_accounts(session: Session, accounts_path: Path) -> int:
    if not accounts_path.exists():
        return 0
    raw = json.loads(accounts_path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else [raw]
    repo = AccountRepository(session)
    snapshot_repo = AccountSnapshotRepository(session)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"accounts/me.json entry must be an object: {row!r}")
        repo.upsert(_coerce_account(row))
        # B051: the read paths (NAV / recommendations / execution) consume
        # account_snapshot only, so the seed must write it too.
        snapshot_repo.upsert(_coerce_account_snapshot(row))
    return len(rows)


def _import_backlog(session: Session, backlog_path: Path) -> int:
    if not backlog_path.exists():
        return 0
    raw = json.loads(backlog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("backlog.json must be a JSON array of entries.")
    repo = BacklogRepository(session)
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError(f"backlog.json entry must be an object: {row!r}")
        repo.upsert(_coerce_backlog(row))
    return len(raw)


def _import_symbol_names(session: Session) -> int:
    """B079 F001 — seed the curated static symbol → display-name rows.

    Idempotent (batch upsert keyed on symbol): re-runs replace in place. The
    live A-share akshare capture (``source="akshare_spot"``) later overrides the
    static English CN fallback for the tickers it covers.
    """

    return SymbolNameRepository(session).upsert_names(
        CURATED_SYMBOL_NAMES, source="curated"
    )


def run(repo_root: Path) -> dict[str, int]:
    """Programmatic entry point used by tests."""

    reset_engine()
    get_engine()  # Resolve the URL eagerly so a misconfig surfaces here.

    accounts_path = repo_root / "accounts" / "me.json"
    backlog_path = repo_root / "backlog.json"

    session_gen = get_session()
    session = next(session_gen)
    try:
        n_accounts = _import_accounts(session, accounts_path)
        n_backlog = _import_backlog(session, backlog_path)
        n_symbol_names = _import_symbol_names(session)
        # Trigger the generator's commit on a clean close.
        with contextlib.suppress(StopIteration):
            next(session_gen)
        return {
            "accounts": n_accounts,
            "backlog": n_backlog,
            "symbol_names": n_symbol_names,
        }
    except Exception:
        session_gen.throw(SystemExit("rollback"))
        raise


def _resolve_repo_root() -> Path:
    # workbench/backend/workbench_api/cli/bootstrap.py → repo root is parents[4]
    return Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workbench-bootstrap",
        description="Mirror accounts/me.json + backlog.json into the workbench DB. Idempotent.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to inferring from this file's path).",
    )
    args = parser.parse_args(argv)

    repo_root = (args.repo_root or _resolve_repo_root()).resolve()
    settings = get_settings()
    print(
        f"workbench-bootstrap: db={settings.WORKBENCH_DB_URL} repo-root={repo_root}",
        file=sys.stderr,
    )

    try:
        counts = run(repo_root)
    except OperationalError as exc:
        print(
            f"error: database not initialised ({exc.__class__.__name__}). "
            "Run scripts/migrate.sh first.",
            file=sys.stderr,
        )
        return 2

    print(
        f"workbench-bootstrap: imported accounts={counts['accounts']} "
        f"backlog={counts['backlog']} symbol_names={counts['symbol_names']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
