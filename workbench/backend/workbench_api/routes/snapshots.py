"""Router for ``/api/snapshots`` — F002 schema, F011 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.engine import get_engine
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


def _streaming_session_factory() -> sessionmaker[Session]:
    """B022 F014 fixing-round 2: SSE handler owns its session.

    FastAPI's ``get_session`` dependency tears down its session before
    the StreamingResponse body actually streams — the SSE generator
    then operates on a closed session and 500s on the first ORM call.
    The handler builds its own sessionmaker bound to the same engine
    and hands the factory to the generator, which opens / closes the
    session inside its own try/finally.
    """

    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


@router.post("/refresh")
def refresh_snapshots_route(
    _user: AuthenticatedUserDep,
) -> StreamingResponse:
    """POST /api/snapshots/refresh — streams SSE progress events.

    B049 F001: the generator reads the real on-disk data state (the unified
    prices + fundamentals CSVs the B045 data-refresh job wrote + the persisted
    coverage window), grades coverage, and on the final ``complete`` stage
    inserts/updates a SnapshotMeta row reflecting that real data before the
    event reaches the client, so a subsequent GET shows the refreshed entry.
    Read-only + self-contained (§12.10.2): no ``trade`` import, no subprocess.
    The session is owned by the generator (see ``_streaming_session_factory``
    docstring) — passing FastAPI's request-scoped session would close it before
    the first ORM call.
    """

    factory = _streaming_session_factory()
    return StreamingResponse(
        refresh_event_stream(factory),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache"},
    )
