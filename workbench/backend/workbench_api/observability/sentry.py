"""Optional Sentry integration.

The spec is explicit: Sentry is opt-in. ``SENTRY_DSN`` unset is a no-op;
``SENTRY_DSN`` set without ``sentry-sdk`` installed logs a warning and
keeps booting — we will not refuse to start the workbench over a missing
observability vendor. Operators who genuinely want Sentry install
``sentry-sdk[fastapi]`` in their venv before exporting the env var.
"""

from __future__ import annotations

import logging
from typing import Any

from workbench_api.settings import Settings

_logger = logging.getLogger("workbench.observability.sentry")

_INITIALISED = False
"""Module-level guard so repeated ``init_sentry`` calls (one per worker
factory invocation in tests) do not stack multiple SDK clients."""


def init_sentry(settings: Settings) -> bool:
    """Initialise sentry-sdk if and only if SENTRY_DSN is set.

    Returns ``True`` when the SDK was actually initialised, ``False``
    when the call was a no-op (DSN unset or SDK absent).
    """

    global _INITIALISED
    if _INITIALISED:
        return True

    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn:
        _logger.debug("Sentry: SENTRY_DSN unset; skipping init.")
        return False

    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.asgi import (  # type: ignore[import-not-found]  # noqa: F401
            SentryAsgiMiddleware,
        )
    except ImportError:
        _logger.warning(
            "Sentry: SENTRY_DSN set but sentry-sdk not installed; skipping init. "
            "Install 'sentry-sdk[fastapi]' in the workbench venv to enable.",
        )
        return False

    kwargs: dict[str, Any] = {
        "dsn": dsn,
        "traces_sample_rate": 0.0,  # workbench is single-user; off by default.
        "send_default_pii": False,
        "release": _resolve_release(),
    }

    try:
        sentry_sdk.init(**kwargs)
    except Exception as exc:  # pragma: no cover - depends on Sentry SDK version
        _logger.warning("Sentry: init failed: %s", exc)
        return False

    _INITIALISED = True
    _logger.info("Sentry initialised", extra={"event": "sentry_ready"})
    return True


def _reset_for_tests() -> None:
    """Drop the module guard so tests can re-init."""

    global _INITIALISED
    _INITIALISED = False


def _resolve_release() -> str | None:
    """Best-effort release tag for Sentry; defers to git SHA already
    computed by ``workbench_api.app._resolve_version``.
    """

    try:
        from workbench_api.app import VERSION
    except Exception:  # pragma: no cover - workbench_api.app import side effects
        return None
    return VERSION
