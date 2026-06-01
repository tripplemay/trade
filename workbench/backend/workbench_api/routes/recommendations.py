"""Router for ``/api/recommendations`` — F002 schema, F010 body."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.recommendations import (
    ExportTicketRequest,
    ExportTicketResponse,
    RecommendationsResponse,
    SleeveNewsResponse,
)
from workbench_api.services.recommendations import (
    _resolve_runs_dir,
    export_ticket,
    get_current_recommendations,
    get_sleeve_news,
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


@router.get("/news", response_model=SleeveNewsResponse)
def get_sleeve_news_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    sleeve: Annotated[str, Query(min_length=1, description="Sleeve label (required).")],
    topic: Annotated[str | None, Query(description="Filter by deterministic topic tag.")] = None,
    source: Annotated[str | None, Query(description="Filter by news source.")] = None,
    form_type: Annotated[str | None, Query(description="Filter by SEC form type.")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items returned.")] = 20,
) -> SleeveNewsResponse:
    """B034 F003 — relevance-sorted news for one sleeve.

    Auth-gated, same-origin, read-only. Returns **only structured
    fields** (no AI-generated text — B034 non-generative boundary)."""

    return get_sleeve_news(
        session,
        sleeve=sleeve,
        topic=topic,
        source=source,
        form_type=form_type,
        limit=limit,
    )


@router.post("/export-ticket", response_model=ExportTicketResponse)
def export_ticket_route(
    body: ExportTicketRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ExportTicketResponse:
    return export_ticket(session, body, runs_dir=_runs_root(settings))
