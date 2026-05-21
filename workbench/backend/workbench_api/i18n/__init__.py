"""B024 F004 — backend i18n (HTTPException detail localisation).

The contract mirrors the frontend i18n module:

* `LOCALES` = `('zh-CN', 'en')`; default `zh-CN`.
* `detect_locale(request)` is a FastAPI dependency. The order of
  preference is **`?locale=` query > `Accept-Language` header > default**.
  The negotiator drops to `en` / `zh-CN` when a browser sends a
  regional tag (`en-US`, `zh-TW`) whose base maps to a supported
  locale; anything else collapses to the default.
* The wired locale lives in a per-request `ContextVar` so service-
  layer callers (which don't take the FastAPI request) can call
  `t('errors.x', ...)` without threading locale through every signature.
* `t(key, locale=None, **kwargs)` resolves the message from the chosen
  locale, falling back to the default locale's copy when missing, and
  finally to the key string itself. `str.format(**kwargs)` interpolates
  the named placeholders.

`messages.py` is the dict-of-dict bundle (no new dependency).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Final

from fastapi import Request

from .messages import MESSAGES

LOCALES: Final[tuple[str, ...]] = ("zh-CN", "en")
DEFAULT_LOCALE: Final[str] = "zh-CN"

_LOCALE_VAR: ContextVar[str] = ContextVar("workbench_locale", default=DEFAULT_LOCALE)


def negotiate_locale(
    accept_language: str | None, query_locale: str | None
) -> str:
    """Pick the best-matching supported locale.

    Priority: explicit `?locale=` query > first matching `Accept-Language`
    entry (with `en-US` → `en`, `zh-TW`/`zh-Hant` → `zh-CN` fallback)
    > `DEFAULT_LOCALE`.
    """

    if query_locale and query_locale in LOCALES:
        return query_locale
    if accept_language:
        for part in accept_language.split(","):
            tag = part.split(";")[0].strip()
            if not tag:
                continue
            if tag in LOCALES:
                return tag
            base = tag.split("-")[0]
            if base == "en":
                return "en"
            if base == "zh":
                return "zh-CN"
    return DEFAULT_LOCALE


async def detect_locale(request: Request) -> str:
    """FastAPI dep: pick the locale, stash it in the request's ContextVar.

    Mounted as a global app dependency (see `workbench_api.app`) so every
    route + transitive service call observes a consistent locale via
    `get_current_locale()` without re-reading the headers.

    **Must be `async`** — FastAPI routes sync dependencies through
    `run_in_threadpool`, and `ContextVar.set` made inside that thread
    does not propagate back to the event-loop task that runs the route
    handler. Keeping the dep async makes it run in the same task as the
    route, so the `_LOCALE_VAR.set(locale)` mutation is visible to every
    downstream `t(...)` call.
    """

    query_locale = request.query_params.get("locale")
    accept_language = request.headers.get("accept-language")
    locale = negotiate_locale(accept_language, query_locale)
    _LOCALE_VAR.set(locale)
    return locale


def get_current_locale() -> str:
    """Return the locale wired by :func:`detect_locale` for this request."""

    return _LOCALE_VAR.get()


def t(key: str, locale: str | None = None, /, **kwargs: object) -> str:
    """Resolve a message and interpolate ``{placeholder}`` arguments.

    When `locale` is `None`, fall back to the request-scoped value set
    by :func:`detect_locale`. If a key is missing in the chosen locale,
    fall back to the default locale's copy; if it is missing there too,
    return the literal key (a deliberate visible-failure signal).
    """

    chosen = locale or _LOCALE_VAR.get()
    bundle = MESSAGES.get(chosen)
    template: str | None = None
    if bundle is not None:
        template = bundle.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LOCALE].get(key)
    if template is None:
        return key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


__all__ = [
    "DEFAULT_LOCALE",
    "LOCALES",
    "detect_locale",
    "get_current_locale",
    "negotiate_locale",
    "t",
]
