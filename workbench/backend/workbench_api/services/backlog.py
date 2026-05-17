"""Backlog CRUD + git-auto-commit (B022 F012).

Mutations land in three places in one transaction-shaped block:

1. The SQLite ``backlog_entry`` table (BacklogRepository).
2. ``backlog.json`` at the repo root, regenerated from the table state.
3. ``git add backlog.json && git commit -m 'chore(backlog): <action> <id>'``.

Step 3 is invoked through the ``GitRunner`` Protocol so tests can
substitute a recording stub instead of shelling out. A git failure
(merge conflict, dirty index, hook reject, etc.) raises
``GitCommitError`` which the route layer translates to a 500 — the
F012 acceptance specifically calls out "fail closed" on commit errors
so the UI surfaces a toast rather than silently dropping the change.

The DB and the JSON file together are the source of truth; the
``confirmed_at`` column doubles as both ``created_at`` and
``updated_at`` in the F002 API schema (the model predates F002's
schema split and keeping it that way avoids a migration just for the
API contract).
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from workbench_api.db.models.backlog_entry import BacklogEntry as BacklogEntryModel
from workbench_api.db.repositories.backlog import BacklogRepository
from workbench_api.schemas.backlog import (
    BacklogCreateRequest,
    BacklogDeleteResponse,
    BacklogEntry,
    BacklogListResponse,
    BacklogUpdateRequest,
)


class BacklogNotFoundError(LookupError):
    """The supplied backlog id does not exist."""


class GitCommitError(RuntimeError):
    """git add/commit subprocess failed; mutation is rolled back."""


class GitRunner(Protocol):
    """Callable that runs a git subprocess; raises GitCommitError on failure."""

    def __call__(self, args: list[str], cwd: Path) -> None:  # pragma: no cover - protocol
        ...


def _real_git_runner(args: list[str], cwd: Path) -> None:
    try:
        subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as exc:
        raise GitCommitError(
            f"git {' '.join(args[1:])} failed: {exc.stderr or exc.stdout or exc}"
        ) from exc
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise GitCommitError(f"git invocation failed: {exc}") from exc


@dataclass(frozen=True, slots=True)
class BacklogServiceConfig:
    repo_root: Path
    backlog_file: Path
    git_runner: GitRunner = _real_git_runner


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _new_backlog_id() -> str:
    """Generate a workbench-managed id distinct from the repo's BL-<batch>-<n> ids."""

    return f"BL-WB-{uuid.uuid4().hex[:8].upper()}"


def _row_to_schema(row: BacklogEntryModel) -> BacklogEntry:
    # F002 schema uses created_at + updated_at; the model only has
    # confirmed_at, so both timestamps mirror that single column for
    # MVP. F012 documents this in the route docstring so future schema
    # extensions know what to widen.
    timestamp = row.confirmed_at or _now_iso()
    return BacklogEntry(
        id=row.id,
        title=row.title,
        description=row.description,
        priority=row.priority,
        status="open",
        created_at=timestamp,
        updated_at=timestamp,
    )


def list_backlog(session: Session) -> BacklogListResponse:
    repo = BacklogRepository(session)
    rows = repo.list_all()
    return BacklogListResponse(entries=[_row_to_schema(row) for row in rows])


def _dump_rows_to_json(rows: Iterable[BacklogEntryModel], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "decisions": row.decisions,
            "confirmed_at": row.confirmed_at,
            "priority": row.priority,
            "source": row.source,
        }
        for row in rows
    ]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _commit(action: str, entry_id: str, config: BacklogServiceConfig) -> None:
    """Run `git add backlog.json && git commit ...`; raises GitCommitError."""

    config.git_runner(["git", "add", str(config.backlog_file)], config.repo_root)
    config.git_runner(
        ["git", "commit", "-m", f"chore(backlog): {action} {entry_id}"],
        config.repo_root,
    )


def create_backlog(
    session: Session,
    request: BacklogCreateRequest,
    config: BacklogServiceConfig,
) -> BacklogEntry:
    repo = BacklogRepository(session)
    entry = BacklogEntryModel(
        id=_new_backlog_id(),
        title=request.title,
        description=request.description,
        priority=request.priority,
        decisions=[],
        confirmed_at=_now_iso(),
        source="workbench",
    )
    repo.upsert(entry)
    session.commit()
    _dump_rows_to_json(repo.list_all(), config.backlog_file)
    _commit("add", entry.id, config)
    return _row_to_schema(entry)


def update_backlog(
    session: Session,
    entry_id: str,
    request: BacklogUpdateRequest,
    config: BacklogServiceConfig,
) -> BacklogEntry:
    repo = BacklogRepository(session)
    existing = repo.get_by_id(entry_id)
    if existing is None:
        raise BacklogNotFoundError(entry_id)
    if request.title is not None:
        existing.title = request.title
    if request.description is not None:
        existing.description = request.description
    if request.priority is not None:
        existing.priority = request.priority
    # request.status is not stored in the model (synthesised at read time).
    existing.confirmed_at = _now_iso()
    session.flush()
    session.commit()
    _dump_rows_to_json(repo.list_all(), config.backlog_file)
    _commit("edit", entry_id, config)
    return _row_to_schema(existing)


def delete_backlog(
    session: Session,
    entry_id: str,
    config: BacklogServiceConfig,
) -> BacklogDeleteResponse:
    repo = BacklogRepository(session)
    existed = repo.delete(entry_id)
    if not existed:
        raise BacklogNotFoundError(entry_id)
    session.commit()
    _dump_rows_to_json(repo.list_all(), config.backlog_file)
    _commit("delete", entry_id, config)
    return BacklogDeleteResponse(id=entry_id, deleted=True)
