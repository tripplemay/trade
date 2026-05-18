"""Router for ``/api/execution/*`` — B023 manual-execution workflow.

F002 ships three endpoints:

* ``GET  /api/execution/position-diff``  — read latest snapshot + targets, build diff.
* ``GET  /api/execution/account/latest`` — latest ``account_snapshot`` row.
* ``PUT  /api/execution/account``        — insert a new snapshot (source=ui_edit).

All endpoints are auth-gated via the existing
``require_authenticated_user`` dependency. Later features (F003 tickets,
F004 fills, F005 reconcile) add to this module without altering F002.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.execution import (
    AccountSnapshotPayload,
    AccountUpdateRequest,
    PositionDiffResponse,
)
from workbench_api.services.execution import (
    get_latest_account,
    get_position_diff,
    update_account,
)

router = APIRouter(prefix="/execution", tags=["execution"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


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
