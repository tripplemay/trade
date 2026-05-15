"""SQLAlchemy 2.x engine factory.

The engine is built lazily on first call so test fixtures can swap
``WORKBENCH_DB_URL`` via env-var overrides before the engine spins up.
``SQLite`` connections need ``check_same_thread=False`` to work with
FastAPI's thread-pool dispatch and a static pool to share an in-memory DB
across a test process.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from workbench_api.settings import get_settings


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        # FastAPI dispatches handlers on a thread pool; SQLite's default
        # one-connection-per-thread rule trips that. ``check_same_thread``
        # is the canonical SQLAlchemy escape hatch.
        return {"connect_args": {"check_same_thread": False}}
    return {}


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.WORKBENCH_DB_URL
    return create_engine(url, **_engine_kwargs(url), future=True)


def reset_engine() -> None:
    """Drop the memoized engine.

    Used by tests that need to point at a different ``WORKBENCH_DB_URL``
    after the cache has filled. Production code should not call this.
    """

    get_engine.cache_clear()
