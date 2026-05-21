"""Router for ``/api/execution/*`` — B023 manual-execution workflow.

F002 ships three position-diff + account endpoints; F003 adds the four
ticket endpoints (POST tickets / GET tickets / GET tickets/{id} / POST
tickets/{id}/void). All endpoints are auth-gated via the existing
``require_authenticated_user`` dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import t
from workbench_api.schemas.execution import (
    AccountSnapshotPayload,
    AccountUpdateRequest,
    PositionDiffResponse,
)
from workbench_api.schemas.fills import (
    FillsListResponse,
    FillSubmitRequest,
    FillSubmitResponse,
)
from workbench_api.schemas.reconcile import (
    JournalHistoryResponse,
    ReconcileResponse,
    SlippageAnalyticsResponse,
)
from workbench_api.schemas.risk_panel import RiskPanelResponse
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
from workbench_api.services.fills import list_fills, submit_csv, submit_fills
from workbench_api.services.recommendations import _resolve_runs_dir
from workbench_api.services.reconcile import (
    get_journal_history,
    get_slippage_analytics,
    reconcile_ticket,
)
from workbench_api.services.risk_panel import get_risk_panel
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
    if body.cash < 0:
        raise HTTPException(
            status_code=422, detail=t("validation.cash_negative")
        )
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
        raise HTTPException(
            status_code=404, detail=t("ticket.not_found", ticket_id=ticket_id)
        )
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
            detail=t("ticket.cannot_void", ticket_id=ticket_id),
        )
    return summary


@router.post("/fills", response_model=FillSubmitResponse)
def post_fills_route(
    body: FillSubmitRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> FillSubmitResponse:
    """JSON path: ``{ticket_id, fills:[...], allow_unmatched?}``.

    The multipart CSV path is split into ``POST /fills/csv`` so each
    route has a single content type and FastAPI can produce a clean
    OpenAPI surface for the openapi-typescript pipeline.
    """

    return submit_fills(session, body, source="manual_entry")


@router.post("/fills/csv", response_model=FillSubmitResponse)
async def post_fills_csv_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    ticket_id: Annotated[str, Form(min_length=1)],
    csv_file: Annotated[UploadFile, File(description="CSV file with broker fill rows")],
    allow_unmatched: Annotated[bool, Form()] = False,
) -> FillSubmitResponse:
    """Multipart CSV upload path. Headers drive adapter detection
    (generic / Schwab / IBKR); row-level validation errors return as
    400 ``{detail: {errors: [{row, error}]}}`` so the frontend can
    highlight which rows to fix."""

    content = await csv_file.read()
    return submit_csv(session, ticket_id, content, allow_unmatched=allow_unmatched)


@router.get("/fills", response_model=FillsListResponse)
def list_fills_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    ticket_id: str = Query(min_length=1),
) -> FillsListResponse:
    return list_fills(session, ticket_id)


@router.post("/reconcile/{ticket_id}", response_model=ReconcileResponse)
def reconcile_ticket_route(
    ticket_id: str,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> ReconcileResponse:
    return reconcile_ticket(session, ticket_id)


@router.get("/journal-history", response_model=JournalHistoryResponse)
def journal_history_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    since: str | None = Query(
        default=None,
        description="ISO date. Only tickets with ticket_date >= since are returned.",
    ),
) -> JournalHistoryResponse:
    return get_journal_history(session, since=since)


@router.get("/slippage-analytics", response_model=SlippageAnalyticsResponse)
def slippage_analytics_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    window: str = Query(default="3m", pattern="^(3m|6m|1y)$"),
) -> SlippageAnalyticsResponse:
    return get_slippage_analytics(session, window=window)


@router.get("/risk-panel", response_model=RiskPanelResponse)
def risk_panel_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> RiskPanelResponse:
    return get_risk_panel(session)
