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

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import detect_locale, t
from workbench_api.observability.active_users import active_users
from workbench_api.observability.backup_status import read_backup_status
from workbench_api.observability.error_buffer import (
    ErrorRecord,
    get_recent_errors,
    record_error,
)
from workbench_api.observability.logging import setup_logging
from workbench_api.observability.middleware import RequestIDMiddleware
from workbench_api.observability.sentry import init_sentry
from workbench_api.routes import advisor as advisor_routes
from workbench_api.routes import backlog as backlog_routes
from workbench_api.routes import backtests as backtests_routes
from workbench_api.routes import dashboard as dashboard_routes
from workbench_api.routes import execution as execution_routes
from workbench_api.routes import home as home_routes
from workbench_api.routes import market_context as market_context_routes
from workbench_api.routes import recommendations as recommendations_routes
from workbench_api.routes import reports as reports_routes
from workbench_api.routes import snapshots as snapshots_routes
from workbench_api.routes import strategies as strategies_routes
from workbench_api.settings import Settings, get_settings

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_health_logger = logging.getLogger("workbench.health")
_unhandled_logger = logging.getLogger("workbench.unhandled")


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


class RecentErrorsResponse(BaseModel):
    """Response schema for ``GET /api/debug/recent-errors``.

    B022 F014 fixing-round 3 diagnostic surface. See
    ``observability/error_buffer.py`` for the rationale.
    """

    count: int
    records: list[ErrorRecord]


DEFAULT_RELEASE_SHA_FILE: Path = Path("/srv/workbench/current/RELEASE_SHA")
"""Production: ``workbench-deploy.yml`` writes the head SHA into this file
at the release dir root (Stage release artifacts step, line 130). The
``current`` symlink the deploy script flips makes this path stable across
releases, so the backend can read the active commit without depending on
a ``.git`` tree (the release tarball ships no git metadata).
"""


def _resolve_version(release_sha_file: Path = DEFAULT_RELEASE_SHA_FILE) -> str:
    """Identify the running commit for ``/api/health``.

    Three-stage fallback:

    1. **Production marker** — the deploy workflow stages a ``RELEASE_SHA``
       file alongside ``backend/`` and ``frontend/``; deploy.sh flips
       ``/srv/workbench/current`` to point at it. Reading that file is the
       authoritative path on the VM because the wheel-installed
       workbench_api package lives in the shared venv, not in the release
       dir, so ``Path(__file__).parents[N]`` cannot locate the release.
    2. **Local git** — dev workstations have ``.git`` reachable from the
       repo root; ``git rev-parse --short HEAD`` resolves the live commit.
    3. **``dev``** — neither path produced a usable SHA; this is the
       expected value in fresh CI containers and one-off shell sessions.

    Failure is non-fatal — /api/health remains responsive in every case.
    """

    try:
        sha = release_sha_file.read_text(encoding="utf-8").strip()
    except OSError:
        sha = ""
    if sha:
        return sha

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
    return result.stdout.strip() or "dev"


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
        # B024 F004 — wire locale detection on every request so any
        # downstream `raise HTTPException(detail=t(...))` resolves
        # against the negotiated locale via the request-scoped
        # ContextVar. Dep is read-only (no auth coupling) so it's safe
        # to mount globally including on /api/health.
        dependencies=[Depends(detect_locale)],
    )
    app.add_middleware(RequestIDMiddleware)

    # B022 F014 fixing-round 2: capture every route exception with a full
    # traceback into the structured logger so journalctl shows the
    # underlying cause. The default FastAPI 500 handler discards the
    # exception silently, which is what made dashboard/recommendations/
    # backlog 500s opaque during Codex L2 reverify. Returning the same
    # `{"detail": "Internal Server Error"}` shape keeps the public
    # surface unchanged — we only add the journal entry.
    @app.exception_handler(Exception)
    async def _log_unhandled_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        _unhandled_logger.exception(
            "unhandled route exception",
            extra={
                "event": "unhandled_route_exception",
                "method": request.method,
                "path": request.url.path,
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        # B022 F014 fixing-round 3: also stash a compact record in the
        # process-local ring buffer so /api/debug/recent-errors can
        # surface the cause when journalctl is unavailable.
        record_error(
            method=request.method,
            path=request.url.path,
            exception_type=exc.__class__.__name__,
            exception_message=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal Server Error"},
        )

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
                detail=t("health.db_unreachable"),
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

    @api.get("/debug/recent-errors", response_model=RecentErrorsResponse)
    def debug_recent_errors(_user: AuthenticatedUserDep) -> RecentErrorsResponse:
        """B022 F014 fixing-round 3: in-process error buffer surface.

        Auth-gated (same allowlisted email as every other workbench
        route) so it never leaks publicly. Returns the most recent N
        unhandled-exception events captured by the global handler so
        the evaluator can diagnose 500s without journalctl. See
        ``observability/error_buffer.py``.
        """

        records = get_recent_errors()
        return RecentErrorsResponse(count=len(records), records=records)

    # B022 F002 — register the 7 vertical-slice schemas + 501 stubs so the
    # OpenAPI → TypeScript pipeline emits stable types for F006-F012. Real
    # handler bodies replace these in their owning features; the route
    # surface itself stays frozen here.
    api.include_router(dashboard_routes.router)
    api.include_router(home_routes.router)
    api.include_router(strategies_routes.router)
    api.include_router(backtests_routes.router)
    api.include_router(reports_routes.router)
    api.include_router(recommendations_routes.router)
    api.include_router(market_context_routes.router)
    api.include_router(advisor_routes.router)
    api.include_router(snapshots_routes.router)
    api.include_router(backlog_routes.router)
    api.include_router(execution_routes.router)

    app.include_router(api)

    return app


app = create_app()
