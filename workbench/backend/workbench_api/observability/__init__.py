"""Observability surface for the workbench backend (B021 F006).

The package consolidates four concerns the spec carved out:

* ``logging``      — JSON formatter + setup helpers; emits one structured
                      line per record, decorated with the current
                      ``request_id`` and ``user_id`` from contextvars.
* ``middleware``   — ASGI/Starlette ``RequestIDMiddleware`` that mints (or
                      forwards) ``X-Request-ID`` per request and stashes
                      it on ``request.state`` + the contextvar that the
                      JSON formatter reads.
* ``active_users`` — single-process recent-email registry used by
                      ``/api/health`` to surface ``active_user_count``.
* ``backup_status``— ``/api/health`` reads the workbench backup log tail
                      to surface ``last_backup_age_seconds`` +
                      ``last_backup_size_bytes``. Failures degrade to
                      ``None`` rather than 5xx.
* ``sentry``       — opt-in initialisation gated on ``SENTRY_DSN``. Unset
                      is a no-op; a set DSN with the SDK missing logs a
                      warning instead of crashing the process.
"""

from workbench_api.observability.active_users import ActiveUserRegistry, active_users
from workbench_api.observability.backup_status import BackupStatus, read_backup_status
from workbench_api.observability.logging import (
    REQUEST_ID_VAR,
    USER_ID_VAR,
    JSONLogFormatter,
    setup_logging,
)
from workbench_api.observability.middleware import RequestIDMiddleware
from workbench_api.observability.sentry import init_sentry

__all__ = [
    "ActiveUserRegistry",
    "BackupStatus",
    "JSONLogFormatter",
    "REQUEST_ID_VAR",
    "RequestIDMiddleware",
    "USER_ID_VAR",
    "active_users",
    "init_sentry",
    "read_backup_status",
    "setup_logging",
]
