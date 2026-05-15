"""Structured JSON logging for the workbench backend.

Every log line is a single JSON object with at least:

* ``timestamp`` — RFC3339 UTC, second resolution.
* ``level``     — Python logging level name.
* ``logger``    — dotted logger name.
* ``event``     — message after %-substitution.
* ``request_id``— populated from ``REQUEST_ID_VAR`` if the
                   :class:`RequestIDMiddleware` set it for the current
                   request.
* ``user_id``   — populated from ``USER_ID_VAR`` once
                   :func:`workbench_api.auth.dependency.require_authenticated_user`
                   has stashed the validated email.

Extra ``logger.info("event", extra={"key": "value"})`` keys are merged
into the payload without overriding the reserved fields above.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from workbench_api.settings import Settings

REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("workbench_request_id", default=None)
USER_ID_VAR: ContextVar[str | None] = ContextVar("workbench_user_id", default=None)

_RESERVED_LOG_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class JSONLogFormatter(logging.Formatter):
    """Render a ``LogRecord`` as one JSON object.

    Drop-in replacement for the default formatter. Safe under threaded /
    async workloads — context-local fields come from ``ContextVar``.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _format_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = REQUEST_ID_VAR.get()
        if request_id is not None:
            payload["request_id"] = request_id
        user_id = USER_ID_VAR.get()
        if user_id is not None:
            payload["user_id"] = user_id

        # Merge extras that callers passed via ``logger.info("...", extra={...})``.
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_KEYS or key in payload:
                continue
            if key.startswith("_"):
                continue
            payload[key] = _coerce_jsonable(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, separators=(",", ":"), default=str)


def _format_timestamp(epoch: float) -> str:
    # RFC3339 UTC. ``time.gmtime`` is locale-free; ``%Y-%m-%dT%H:%M:%SZ``
    # matches what most log aggregators ingest without re-parsing.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _coerce_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def setup_logging(settings: Settings, *, level: int = logging.INFO) -> None:
    """Wire root + uvicorn loggers to the JSON formatter.

    Always logs to stdout (systemd captures that into the journal). If
    ``settings.WORKBENCH_LOG_DIR`` exists and is writable, also rotate to
    ``${dir}/app.log`` so the deploy can `tail` without `journalctl`. Errors
    creating the file handler degrade to stdout-only with a warning — we
    must not refuse to boot just because /var/log/workbench is missing.
    """

    handlers: list[logging.Handler] = []
    json_formatter = JSONLogFormatter()

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(json_formatter)
    handlers.append(stream_handler)

    log_dir = Path(settings.WORKBENCH_LOG_DIR)
    file_handler: logging.Handler | None = None
    try:
        if log_dir.is_dir():
            file_handler = RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=8,
                encoding="utf-8",
            )
            file_handler.setFormatter(json_formatter)
            handlers.append(file_handler)
    except OSError as exc:  # pragma: no cover - depends on host filesystem
        logging.getLogger("workbench.observability").warning(
            "log dir %s present but not writable (%s); stdout-only logging.",
            log_dir,
            exc,
        )

    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)

    # Take over uvicorn's loggers so its lifecycle / access lines join the
    # JSON stream too. Without this, uvicorn keeps its plaintext default.
    for uvicorn_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_name)
        u_logger.handlers.clear()
        for handler in handlers:
            u_logger.addHandler(handler)
        u_logger.setLevel(level)
        u_logger.propagate = False
