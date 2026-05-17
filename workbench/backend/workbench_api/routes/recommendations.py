"""Stub router for ``/api/recommendations`` — F002 schema, F010 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.recommendations import (
    ExportTicketRequest,
    ExportTicketResponse,
    RecommendationsResponse,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/current", response_model=RecommendationsResponse)
def get_current_recommendations(_user: AuthenticatedUserDep) -> RecommendationsResponse:
    raise not_implemented("F010")


@router.post("/export-ticket", response_model=ExportTicketResponse)
def export_ticket(
    body: ExportTicketRequest,
    _user: AuthenticatedUserDep,
) -> ExportTicketResponse:
    del body
    raise not_implemented("F010")
