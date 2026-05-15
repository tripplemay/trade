"""Recent active-user registry.

The workbench is single-user, so ``active_user_count`` is 0 or 1 in
practice — but the spec field exists to (a) prove the auth wiring works
end-to-end and (b) give Codex L2 verification a real metric to assert.

Implementation is intentionally tiny:

* in-memory ``dict[email, last_seen_monotonic]``
* ``touch(email)`` writes the entry
* ``count(now=None)`` prunes entries older than ``window_seconds`` and
  returns the resulting size
* a process-wide singleton ``active_users`` is reused by the auth
  dependency and the /api/health handler

Persistence across restarts is a non-goal — we explicitly want the
counter to start empty on reboot so an old session that the operator
forgot about cannot inflate the metric forever.
"""

from __future__ import annotations

import time
from threading import Lock

DEFAULT_WINDOW_SECONDS: float = 15 * 60


class ActiveUserRegistry:
    """Thread-safe registry of recently-active workbench users."""

    def __init__(self, *, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self._window_seconds = window_seconds
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    def touch(self, email: str, *, now: float | None = None) -> None:
        ts = now if now is not None else time.monotonic()
        with self._lock:
            self._seen[email] = ts

    def count(self, *, now: float | None = None) -> int:
        cutoff = (now if now is not None else time.monotonic()) - self._window_seconds
        with self._lock:
            stale = [email for email, ts in self._seen.items() if ts < cutoff]
            for email in stale:
                self._seen.pop(email, None)
            return len(self._seen)

    def clear(self) -> None:
        """Reset the registry — exposed for tests, not for production use."""

        with self._lock:
            self._seen.clear()


# Process-wide singleton. The workbench-backend systemd unit runs a single
# worker (uvicorn --workers 1) so cross-process synchronisation is not
# required. If that ever changes, swap this for a Redis-backed implementation.
active_users: ActiveUserRegistry = ActiveUserRegistry()
