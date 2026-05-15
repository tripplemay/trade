"""Workbench FastAPI app factory.

B020 shipped a single ``/health`` route. B021 F001 moved the public surface
under the ``/api`` prefix that nginx (`proxy_pass /api/* → 127.0.0.1:8723`)
routes to in production, and added the first auth-gated route. F002
extended ``/api/health`` with a ``db_connectivity`` probe. F006 finishes
the health surface by adding uptime, the freshness + size of the latest
backup, and the active-user count, and wires the structured logging /
request-id middleware / optional Sentry init that operators use to debug
production. The endpoint stays unauthenticated — nginx upstream probes
and external uptime monitors call it without a session cookie.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.observability.active_users import active_users
from workbench_api.observability.backup_status import read_backup_status
from workbench_api.observability.logging import setup_logging
from workbench_api.observability.middleware import RequestIDMiddleware
from workbench_api.observability.sentry import init_sentry
from workbench_api.settings import Settings, get_settings

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_health_logger = logging.getLogger("workbench.health")


class HealthResponse(BaseModel):
    """Response schema for ``GET /api/health``."""

    status: str
    version: str
    db_connectivity: str
    uptime_seconds: float
    last_backup_age_seconds: float | None
    last_backup_size_bytes: int | None
    active_user_count: int


class ProtectedTestResponse(BaseModel):
    """Response schema for ``GET /api/protected-test`` (auth probe)."""

    status: str
    email: str


def _resolve_version() -> str:
    """Best-effort short git SHA; ``dev`` when unavailable.

    Resolution failure is non-fatal — /api/health remains responsive — and
    signals an out-of-tree deployment. B021 F004 will replace this with a
    build-time injected value.
    """

    repo_root = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "dev"
    sha = result.stdout.strip()
    return sha or "dev"


VERSION: str = _resolve_version()
STARTED_AT_MONOTONIC: float = time.monotonic()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    init_sentry(settings)
    _health_logger.info(
        "workbench started",
        extra={"event": "workbench_start", "version": VERSION},
    )
    yield


def create_app() -> FastAPI:
    """Application factory used by uvicorn and the test client."""

    app = FastAPI(
        title="Workbench API",
        version=VERSION,
        description="Research-only workbench backend.",
        lifespan=_lifespan,
    )
    app.add_middleware(RequestIDMiddleware)

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=HealthResponse)
    def health(session: SessionDep, settings: SettingsDep) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            # Log the underlying error so the operator can see it in
            # `journalctl -u workbench-backend`; the response carries only a
            # short token so the public probe never leaks DB internals.
            _health_logger.exception("health: SELECT 1 failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="db_unreachable",
            ) from exc

        uptime = max(0.0, time.monotonic() - STARTED_AT_MONOTONIC)
        backup = read_backup_status(settings.WORKBENCH_BACKUP_LOG)

        return HealthResponse(
            status="ok",
            version=VERSION,
            db_connectivity="ok",
            uptime_seconds=round(uptime, 3),
            last_backup_age_seconds=(
                round(backup.last_backup_age_seconds, 3)
                if backup.last_backup_age_seconds is not None
                else None
            ),
            last_backup_size_bytes=backup.last_backup_size_bytes,
            active_user_count=active_users.count(),
        )

    @api.get("/protected-test", response_model=ProtectedTestResponse)
    def protected_test(user: AuthenticatedUserDep) -> ProtectedTestResponse:
        return ProtectedTestResponse(status="ok", email=user.email)

    app.include_router(api)

    return app


app = create_app()
