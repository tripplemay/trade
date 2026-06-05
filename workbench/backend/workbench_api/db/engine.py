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

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from workbench_api.settings import get_settings

SQLITE_BUSY_TIMEOUT_MS = 30_000
"""How long a SQLite connection waits on a held lock before raising
``database is locked``. The B036 advisor precompute exposed real lock
contention: it holds a session (grounding reads) while
``gateway.advise → cost_guard`` opens a **separate** connection to update
``llm_budget_log`` — the first such concurrent-write path in production.
A generous busy timeout lets the (sub-millisecond) lock holders clear
instead of failing the run."""


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        # FastAPI dispatches handlers on a thread pool; SQLite's default
        # one-connection-per-thread rule trips that. ``check_same_thread``
        # is the canonical SQLAlchemy escape hatch. ``timeout`` is the
        # DBAPI-level busy timeout (seconds) — a second belt alongside the
        # PRAGMA below.
        return {
            "connect_args": {
                "check_same_thread": False,
                "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
            }
        }
    return {}


def _install_sqlite_pragmas(engine: Engine) -> None:
    """Enable WAL + a busy timeout on every SQLite connection.

    WAL lets readers and a writer proceed concurrently (a reader no longer
    blocks a writer), which is what the advisor precompute needs: its
    grounding-read session and the cost-guard's separate write connection
    must not deadlock. The busy timeout covers the brief writer-vs-writer
    overlap. Both are no-ops on non-SQLite engines (this only registers for
    SQLite)."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn: Any, _record: Any) -> None:  # noqa: ANN401
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.WORKBENCH_DB_URL
    engine = create_engine(url, **_engine_kwargs(url), future=True)
    if url.startswith("sqlite"):
        _install_sqlite_pragmas(engine)
    return engine


def reset_engine() -> None:
    """Drop the memoized engine.

    Used by tests that need to point at a different ``WORKBENCH_DB_URL``
    after the cache has filled. Production code should not call this.
    """

    get_engine.cache_clear()
