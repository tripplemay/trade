"""Workbench FastAPI app factory.

B020 shipped a single ``/health`` route. B021 F001 moves the public surface
under the ``/api`` prefix that nginx (`proxy_pass /api/* → 127.0.0.1:8723`)
will route to in production, and adds the first auth-gated route used by the
acceptance suite. Public ``/api/health`` stays unauthenticated so the nginx
upstream probe and external uptime monitors keep working.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


class HealthResponse(BaseModel):
    """Response schema for ``GET /api/health``."""

    status: str
    version: str


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


def create_app() -> FastAPI:
    """Application factory used by uvicorn and the test client."""

    app = FastAPI(
        title="Workbench API",
        version=VERSION,
        description="Research-only workbench backend.",
    )

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=VERSION)

    @api.get("/protected-test", response_model=ProtectedTestResponse)
    def protected_test(user: AuthenticatedUserDep) -> ProtectedTestResponse:
        return ProtectedTestResponse(status="ok", email=user.email)

    app.include_router(api)

    return app


app = create_app()
