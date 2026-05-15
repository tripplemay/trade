"""``workbench-bootstrap`` — idempotent loader for the run-time DB.

Reads two repo-root files (both optional, both missing is OK on a fresh
clone):

* ``accounts/me.json``  — research-account state, mirrored into ``account``
* ``backlog.json``      — research backlog, mirrored into ``backlog_entry``

Each row is upserted via the Repository layer so re-running the command is
a no-op. Snapshots are not bootstrapped from a JSON file in B021 — that
table is populated by the snapshot pipeline directly (B009+ adapter work in
B022).

Designed to be safe to run before *or* after ``alembic upgrade head`` is
applied to the live DB; if tables are missing the command fails loudly so
operators notice.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine, reset_engine
from workbench_api.db.models import Account, BacklogEntry
from workbench_api.db.repositories import AccountRepository, BacklogRepository
from workbench_api.db.session import get_session
from workbench_api.settings import get_settings


def _coerce_account(payload: dict[str, Any]) -> Account:
    return Account(
        account_id=str(payload["account_id"]),
        name=str(payload.get("name", payload["account_id"])),
        base_currency=str(payload.get("base_currency", "USD")),
        cash=Decimal(str(payload.get("cash", "0"))),
        equity_value=Decimal(str(payload.get("equity_value", "0"))),
        as_of_date=date.fromisoformat(str(payload["as_of_date"])),
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
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"accounts/me.json entry must be an object: {row!r}")
        repo.upsert(_coerce_account(row))
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
        # Trigger the generator's commit on a clean close.
        with contextlib.suppress(StopIteration):
            next(session_gen)
        return {"accounts": n_accounts, "backlog": n_backlog}
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
        f"backlog={counts['backlog']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
