"""Router for ``/api/backlog`` — F002 schema, F012 body."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
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


def _default_config() -> BacklogServiceConfig:
    """Anchor repo_root at the actual repo root. The route constructs
    the config per-request so dependency_overrides can swap git_runner
    in tests without monkeypatching globals.

    routes/backlog.py lives 5 levels deep under the repo
    (routes/ → workbench_api/ → backend/ → workbench/ → repo), so
    parents[4] is the repo root. The B022 F014 fix corrected the
    prior parents[3] anchor, which pointed at ``workbench/`` and
    therefore wrote ``backlog.json`` outside the tracked source tree.
    """

    repo_root = Path(__file__).resolve().parents[4]
    return BacklogServiceConfig(
        repo_root=repo_root,
        backlog_file=repo_root / "backlog.json",
    )


def get_backlog_config() -> BacklogServiceConfig:
    return _default_config()


BacklogConfigDep = Annotated[BacklogServiceConfig, Depends(get_backlog_config)]


def _git_failed(exc: GitCommitError) -> HTTPException:
    """Map git failures to 500 — F012 acceptance: 'fail closed'."""

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Backlog git commit failed: {exc}",
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
            detail=f"Unknown backlog id: {exc}",
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
            detail=f"Unknown backlog id: {exc}",
        ) from exc
    except GitCommitError as exc:
        raise _git_failed(exc) from exc
