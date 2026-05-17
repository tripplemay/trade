"""Router for ``/api/snapshots`` — F002 schema, F011 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.snapshots import SnapshotListResponse
from workbench_api.services.snapshots import (
    list_snapshots,
    refresh_event_stream,
)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=SnapshotListResponse)
def list_snapshots_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> SnapshotListResponse:
    return list_snapshots(session)


@router.post("/refresh")
def refresh_snapshots_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> StreamingResponse:
    """POST /api/snapshots/refresh — streams SSE progress events.

    The synthetic generator yields 5 stages; the final ``complete``
    stage inserts/updates a SnapshotMeta row before the event reaches
    the client so a subsequent GET shows the refreshed entry.
    """

    return StreamingResponse(
        refresh_event_stream(session),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache"},
    )
