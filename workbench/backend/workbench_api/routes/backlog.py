"""Stub router for ``/api/backlog`` CRUD — F002 schema, F012 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.backlog import (
    BacklogCreateRequest,
    BacklogDeleteResponse,
    BacklogEntry,
    BacklogListResponse,
    BacklogUpdateRequest,
)

router = APIRouter(prefix="/backlog", tags=["backlog"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=BacklogListResponse)
def list_backlog(_user: AuthenticatedUserDep) -> BacklogListResponse:
    raise not_implemented("F012")


@router.post("", response_model=BacklogEntry, status_code=201)
def create_backlog_entry(
    body: BacklogCreateRequest,
    _user: AuthenticatedUserDep,
) -> BacklogEntry:
    del body
    raise not_implemented("F012")


@router.patch("/{entry_id}", response_model=BacklogEntry)
def update_backlog_entry(
    entry_id: str,
    body: BacklogUpdateRequest,
    _user: AuthenticatedUserDep,
) -> BacklogEntry:
    del entry_id, body
    raise not_implemented("F012")


@router.delete("/{entry_id}", response_model=BacklogDeleteResponse)
def delete_backlog_entry(
    entry_id: str,
    _user: AuthenticatedUserDep,
) -> BacklogDeleteResponse:
    del entry_id
    raise not_implemented("F012")
