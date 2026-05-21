"""Router for ``/api/backlog`` — F002 schema, F012 body."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import t
from workbench_api.schemas.backlog import (
    BacklogCreateRequest,
    BacklogDeleteResponse,
    BacklogEntry,
    BacklogListResponse,
    BacklogUpdateRequest,
)
from workbench_api.services.backlog import (
    BacklogNotFoundError,
    BacklogServiceConfig,
    GitCommitError,
    create_backlog,
    delete_backlog,
    list_backlog,
    update_backlog,
)

router = APIRouter(prefix="/backlog", tags=["backlog"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]

_logger = logging.getLogger("workbench.backlog")

PROD_RELEASE_CURRENT: Path = Path("/srv/workbench/current")
"""B021 deploy symlink; presence marks the production VM."""

PROD_BACKLOG_DIR: Path = Path("/var/lib/workbench/backlog")
"""Writable prod home for backlog.json.

The systemd unit (workbench/deploy/systemd/workbench-backend.service)
grants ``ReadWritePaths=/var/lib/workbench``; the service can mkdir
``backlog/`` on demand.
"""


def _noop_git_runner(args: list[str], cwd: Path) -> None:
    """Production git_runner — log and skip.

    Production runs from a wheel install under
    ``/srv/workbench/.../site-packages``; there is no git working tree
    rooted at the prod backlog dir, so the dev-time
    ``git add backlog.json && git commit`` step has nothing to commit
    against. We persist the JSON file (durable on the systemd-managed
    data dir + the daily SQLite backup) and skip the commit instead of
    failing closed. The dev workflow keeps the git auto-commit trail
    via ``_real_git_runner``.

    Documented limitation: prod backlog mutations don't surface in the
    repo's git history. B023 owns proper auditable persistence; for
    B022 the durability guarantees come from the SQLite row + the
    daily backup, not from git.
    """

    del cwd
    _logger.info(
        "skipping git commit in production",
        extra={
            "event": "backlog_git_skipped_prod",
            "git_args": " ".join(args),
        },
    )


def _default_config() -> BacklogServiceConfig:
    """Anchor repo_root + backlog.json depending on environment.

    Two environments:

    1. **Production** (``/srv/workbench/current`` exists). The backend
       runs from a wheel-installed package whose path is unrelated to
       any git working tree; ``Path(__file__).parents[N]`` resolves
       somewhere under the venv. Falling back to a system writable dir
       (``/var/lib/workbench/backlog``) + a no-op git_runner lets the
       feature work; the SQLite row is the durable record.

    2. **Dev / source checkout**. ``routes/backlog.py`` lives 5 levels
       deep under the repo (routes/ → workbench_api/ → backend/ →
       workbench/ → repo); ``parents[4]`` is the repo root. The
       dev-time real git runner keeps the auto-commit trail.

    The route constructs the config per-request so dependency_overrides
    can swap git_runner in tests without monkeypatching globals.
    """

    from workbench_api.services.backlog import _real_git_runner

    if PROD_RELEASE_CURRENT.exists():
        PROD_BACKLOG_DIR.mkdir(parents=True, exist_ok=True)
        return BacklogServiceConfig(
            repo_root=PROD_BACKLOG_DIR,
            backlog_file=PROD_BACKLOG_DIR / "backlog.json",
            git_runner=_noop_git_runner,
        )
    repo_root = Path(__file__).resolve().parents[4]
    return BacklogServiceConfig(
        repo_root=repo_root,
        backlog_file=repo_root / "backlog.json",
        git_runner=_real_git_runner,
    )


def get_backlog_config() -> BacklogServiceConfig:
    return _default_config()


BacklogConfigDep = Annotated[BacklogServiceConfig, Depends(get_backlog_config)]


def _git_failed(exc: GitCommitError) -> HTTPException:
    """Map git failures to 500 — F012 acceptance: 'fail closed'."""

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=t("backlog.git_commit_failed", detail=str(exc)),
    )


@router.get("", response_model=BacklogListResponse)
def list_backlog_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> BacklogListResponse:
    return list_backlog(session)


@router.post("", response_model=BacklogEntry, status_code=201)
def create_backlog_route(
    body: BacklogCreateRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    config: BacklogConfigDep,
) -> BacklogEntry:
    try:
        return create_backlog(session, body, config)
    except GitCommitError as exc:
        raise _git_failed(exc) from exc


@router.patch("/{entry_id}", response_model=BacklogEntry)
def update_backlog_route(
    entry_id: str,
    body: BacklogUpdateRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    config: BacklogConfigDep,
) -> BacklogEntry:
    try:
        return update_backlog(session, entry_id, body, config)
    except BacklogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("backlog.not_found", id=str(exc)),
        ) from exc
    except GitCommitError as exc:
        raise _git_failed(exc) from exc


@router.delete("/{entry_id}", response_model=BacklogDeleteResponse)
def delete_backlog_route(
    entry_id: str,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    config: BacklogConfigDep,
) -> BacklogDeleteResponse:
    try:
        return delete_backlog(session, entry_id, config)
    except BacklogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("backlog.not_found", id=str(exc)),
        ) from exc
    except GitCommitError as exc:
        raise _git_failed(exc) from exc
