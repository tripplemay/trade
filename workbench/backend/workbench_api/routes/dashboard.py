"""Stub router for ``GET /api/dashboard`` — F002 schema, F006 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.dashboard import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=DashboardResponse)
def get_dashboard(_user: AuthenticatedUserDep) -> DashboardResponse:
    raise not_implemented("F006")
