"""Router for ``/api/recommendations`` — F002 schema, F010 body."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.recommendations import (
    ExportTicketRequest,
    ExportTicketResponse,
    RecommendationsResponse,
)
from workbench_api.services.recommendations import (
    _resolve_runs_dir,
    export_ticket,
    get_current_recommendations,
)
from workbench_api.settings import Settings, get_settings

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _runs_root(settings: Settings) -> Path:
    return _resolve_runs_dir(settings.WORKBENCH_RUNS_DIR)


@router.get("/current", response_model=RecommendationsResponse)
def get_current_recommendations_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> RecommendationsResponse:
    return get_current_recommendations(session)


@router.post("/export-ticket", response_model=ExportTicketResponse)
def export_ticket_route(
    body: ExportTicketRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ExportTicketResponse:
    return export_ticket(session, body, runs_dir=_runs_root(settings))
