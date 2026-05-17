"""Stub router for ``/api/snapshots`` — F002 schema, F011 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.snapshots import SnapshotListResponse, SnapshotRefreshResponse

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=SnapshotListResponse)
def list_snapshots(_user: AuthenticatedUserDep) -> SnapshotListResponse:
    raise not_implemented("F011")


@router.post("/refresh", response_model=SnapshotRefreshResponse)
def refresh_snapshots(_user: AuthenticatedUserDep) -> SnapshotRefreshResponse:
    raise not_implemented("F011")
