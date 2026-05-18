"""Router for ``/api/execution/*`` — B023 manual-execution workflow.

F002 ships three position-diff + account endpoints; F003 adds the four
ticket endpoints (POST tickets / GET tickets / GET tickets/{id} / POST
tickets/{id}/void). All endpoints are auth-gated via the existing
``require_authenticated_user`` dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.execution import (
    AccountSnapshotPayload,
    AccountUpdateRequest,
    PositionDiffResponse,
)
from workbench_api.schemas.tickets import (
    GenerateTicketRequest,
    GenerateTicketResponse,
    TicketDetail,
    TicketListResponse,
    TicketSummary,
)
from workbench_api.services.execution import (
    get_latest_account,
    get_position_diff,
    update_account,
)
from workbench_api.services.recommendations import _resolve_runs_dir
from workbench_api.services.tickets import (
    generate_ticket,
    get_ticket_detail,
    list_tickets,
    void_ticket,
)
from workbench_api.settings import Settings, get_settings

router = APIRouter(prefix="/execution", tags=["execution"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _runs_root(settings: Settings) -> Path:
    return _resolve_runs_dir(settings.WORKBENCH_RUNS_DIR)


@router.get("/position-diff", response_model=PositionDiffResponse)
def get_position_diff_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    as_of: str | None = Query(
        default=None,
        description="ISO-8601 date the diff is reported for; defaults to today.",
    ),
) -> PositionDiffResponse:
    return get_position_diff(session, as_of=as_of)


@router.get("/account/latest", response_model=AccountSnapshotPayload | None)
def get_latest_account_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> AccountSnapshotPayload | None:
    return get_latest_account(session)


@router.put("/account", response_model=AccountSnapshotPayload)
def put_account_route(
    body: AccountUpdateRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> AccountSnapshotPayload:
    return update_account(session, body)


@router.post("/tickets", response_model=GenerateTicketResponse)
def post_ticket_route(
    body: GenerateTicketRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> GenerateTicketResponse:
    return generate_ticket(session, body, runs_dir=_runs_root(settings))


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    return list_tickets(session, limit=limit, offset=offset)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket_route(
    ticket_id: str,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> TicketDetail:
    detail = get_ticket_detail(session, ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"ticket not found: {ticket_id}")
    return detail


@router.post("/tickets/{ticket_id}/void", response_model=TicketSummary)
def void_ticket_route(
    ticket_id: str,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> TicketSummary:
    summary = void_ticket(session, ticket_id)
    if summary is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"ticket {ticket_id} cannot be voided "
                f"(not found or already executed/voided)"
            ),
        )
    return summary
