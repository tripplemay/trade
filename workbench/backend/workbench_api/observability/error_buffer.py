"""In-memory ring buffer of recent unhandled exceptions.

B022 F014 fixing-round 3: Codex has no SSH access to the production VM
(``Connection closed by 198.18.1.39 port 22``) and therefore cannot
pull ``journalctl -u workbench-backend``. Without journalctl the
``workbench.unhandled`` structured logs we added in round-2 are
invisible to the evaluator, so 500-class failures stay opaque even
when we know which path is failing.

This buffer is the in-process complement: every time the app-level
exception handler fires it appends a small record (no traceback body,
only class / message / path / timestamp) to a bounded deque, and an
authenticated debug endpoint reads it back. Size is intentionally
small so the buffer cannot grow into a memory leak.

The buffer is process-local. In single-process uvicorn (workbench's
deploy shape) that's the entire app surface. If we ever fan out to
multiple workers, this becomes per-worker and the operator needs to
hit the endpoint a few times to canvas all workers — or we move to a
shared store. Not a concern at MVP scale.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import Lock

from typing_extensions import TypedDict  # pydantic v2 on py<3.12 requires this


class ErrorRecord(TypedDict):
    """Single captured unhandled-exception event."""

    ts: str
    method: str
    path: str
    exception_type: str
    exception_message: str


_MAX_RECORDS: int = 50
"""Cap the buffer at 50. Big enough to see a cluster of failures
during a single Codex L2 sweep; small enough to bound memory."""

_lock = Lock()
_records: deque[ErrorRecord] = deque(maxlen=_MAX_RECORDS)


def record_error(
    method: str, path: str, exception_type: str, exception_message: str
) -> None:
    """Append one error event. Called by the app-level exception handler."""

    with _lock:
        _records.append(
            ErrorRecord(
                ts=datetime.now(tz=UTC).isoformat(timespec="seconds"),
                method=method,
                path=path,
                exception_type=exception_type,
                exception_message=exception_message,
            )
        )


def get_recent_errors() -> list[ErrorRecord]:
    """Return a snapshot of recent records, newest last.

    Returns a copy so callers cannot mutate the deque under the lock.
    """

    with _lock:
        return list(_records)


def clear_recent_errors() -> None:
    """Drop all captured records. Test helper + manual reset surface."""

    with _lock:
        _records.clear()
