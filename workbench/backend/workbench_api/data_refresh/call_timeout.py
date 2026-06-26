"""B078 F001 — per-call wall-clock timeout for the wide A-share fetch loop.

The daily ``workbench-data-refresh`` job hung for three days (2026-06-22 → -25)
because a single ``akshare`` per-symbol fetch blocked on a network read with no
timeout, wedging the whole ~1500-name loop. The systemd service stayed stuck
``activating``, so every downstream daily refresh was blocked and A-share prices
/ universe froze on 06-22 (B075 wide-universe regression). This bounds each
per-symbol fetch to a wall-clock deadline so one hung symbol fails fast (counted
as a §34 partial-failure), and the loop completes and advances the date.

The fetch runs in a daemon worker thread; if it overruns ``timeout_seconds`` the
caller raises :class:`FetchTimeoutError` and moves on. A blocked C-level socket
read cannot be force-killed in CPython, so a hung worker thread leaks — but it is
a daemon (it never blocks process exit) and the systemd ``TimeoutStartSec``
watchdog is the ultimate backstop against a pathological run that leaks many. The
wide-block failure-RATE floor (``resolve_exit_decision``) still fails the job if
a real outage makes most symbols time out.

This is a defensive bound on a *hang*, not a change to fetch semantics: a fetch
that returns within the deadline behaves exactly as before, and a non-positive
deadline disables the bound entirely (runs inline, no worker thread) so existing
callers stay byte-identical.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class FetchTimeoutError(TimeoutError):
    """A per-call fetch exceeded its wall-clock deadline (B078 F001)."""


def call_with_timeout(
    timeout_seconds: float, fn: Callable[..., T], /, *args: object, **kwargs: object
) -> T:
    """Run ``fn(*args, **kwargs)`` under a wall-clock deadline.

    Returns the result when ``fn`` finishes within ``timeout_seconds``; re-raises
    whatever ``fn`` raised; raises :class:`FetchTimeoutError` when it overruns. A
    non-positive ``timeout_seconds`` disables the bound and runs ``fn`` inline (no
    worker thread), so a caller can switch the guard off with a single value and
    the call is byte-identical to a direct invocation."""

    if timeout_seconds <= 0:
        return fn(*args, **kwargs)

    result: list[T] = []
    error: list[BaseException] = []

    def worker() -> None:
        try:
            result.append(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 — re-raised to the caller below
            error.append(exc)

    thread = threading.Thread(target=worker, daemon=True, name="cn-fetch-timeout")
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise FetchTimeoutError(f"fetch exceeded {timeout_seconds:g}s deadline")
    if error:
        raise error[0]
    return result[0]
