"""B022 F014 fixing-round 3 — in-memory error buffer + debug endpoint.

The new ``observability/error_buffer`` ring buffer captures every
unhandled-route exception that the app-level handler logs to
``workbench.unhandled``, and ``/api/debug/recent-errors`` exposes the
buffer to authenticated callers. The endpoint is the workaround for
Codex having no SSH access to production journalctl.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from workbench_api.observability import error_buffer


def test_record_and_get_round_trip() -> None:
    """record_error appends; get_recent_errors returns a snapshot copy
    with the most recent entry last. Caps at the buffer max."""

    error_buffer.clear_recent_errors()
    error_buffer.record_error("GET", "/api/dashboard", "OperationalError", "boom 1")
    error_buffer.record_error("POST", "/api/backlog", "IntegrityError", "boom 2")

    records = error_buffer.get_recent_errors()
    assert len(records) == 2
    assert [r["path"] for r in records] == ["/api/dashboard", "/api/backlog"]
    assert [r["exception_type"] for r in records] == [
        "OperationalError",
        "IntegrityError",
    ]
    # Returned snapshot must be a copy — mutating it should not bleed
    # back into the internal deque.
    records.clear()
    assert len(error_buffer.get_recent_errors()) == 2


def test_buffer_respects_max_cap() -> None:
    """The deque is bounded; oldest entries are dropped."""

    error_buffer.clear_recent_errors()
    for i in range(60):
        error_buffer.record_error("GET", f"/api/x{i}", "RuntimeError", f"e{i}")

    records = error_buffer.get_recent_errors()
    assert len(records) == 50
    # Newest are kept; the oldest 10 are dropped.
    assert records[0]["path"] == "/api/x10"
    assert records[-1]["path"] == "/api/x59"


def test_global_handler_populates_buffer() -> None:
    """A failing route → exception handler logs AND appends a buffer
    record. We exercise the closure-defined handler via TestClient
    against the real create_app() output."""

    from workbench_api.app import create_app

    app: FastAPI = create_app()

    debug_router = APIRouter()

    @debug_router.get("/__test_failing__")
    def _failing() -> None:
        raise RuntimeError("intentional test failure")

    app.include_router(debug_router)

    error_buffer.clear_recent_errors()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test_failing__")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}

    records = error_buffer.get_recent_errors()
    assert len(records) == 1
    assert records[0]["method"] == "GET"
    assert records[0]["path"] == "/__test_failing__"
    assert records[0]["exception_type"] == "RuntimeError"
    assert records[0]["exception_message"] == "intentional test failure"
