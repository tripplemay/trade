"""Workbench FastAPI app factory (B020 skeleton — exposes only /health)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for ``GET /health``."""

    status: str
    version: str


def _resolve_version() -> str:
    """Best-effort short git SHA; ``dev`` when unavailable.

    B020 settings disallow env-var injection, so the version string is sourced
    from the working tree at process start. Resolution failure is non-fatal —
    /health remains responsive — and signals an out-of-tree deployment, which
    B021 will replace with a build-time injected value.
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
        description="Research-only workbench backend. B020 scaffolding.",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=VERSION)

    return app


app = create_app()
