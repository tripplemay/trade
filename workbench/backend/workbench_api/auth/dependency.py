"""FastAPI dependencies that adapt :mod:`workbench_api.auth.jwt_validator`
into HTTP responses.

The dependency translates auth errors into the conventional triad:

* Missing or invalid session cookie  → ``401 Unauthorized``
* Valid token whose email is off the allowlist → ``403 Forbidden``
* Misconfigured server (missing secret or allowlist email) → ``500 Internal Server Error``

Routes opt in by depending on :func:`require_authenticated_user`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from workbench_api.auth.jwt_validator import (
    AuthenticatedUser,
    EmailNotAllowedError,
    InvalidSessionTokenError,
    MissingEmailClaimError,
    MissingSessionCookieError,
    authenticate,
)
from workbench_api.settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_authenticated_user(
    request: Request,
    settings: SettingsDep,
) -> AuthenticatedUser:
    """FastAPI ``Depends`` target that enforces the single-user allowlist.

    The ``settings`` parameter is injected via FastAPI's dependency system so
    tests can override it with ``app.dependency_overrides[get_settings]``
    rather than monkeypatching module globals.
    """

    cfg = settings
    if not cfg.NEXTAUTH_SECRET or not cfg.ALLOWED_USER_EMAIL:
        # A 500 (not 401/403) signals the operator that the deployment is
        # misconfigured — fail loud so this never silently devolves into an
        # auth-open state. Production secrets are pre-staged by B021 prep #5.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workbench auth not configured (NEXTAUTH_SECRET or ALLOWED_USER_EMAIL missing).",
        )

    try:
        return authenticate(
            dict(request.cookies),
            secret=cfg.NEXTAUTH_SECRET,
            allowed_email=cfg.ALLOWED_USER_EMAIL,
        )
    except (MissingSessionCookieError, InvalidSessionTokenError, MissingEmailClaimError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Cookie"},
        ) from exc
    except EmailNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
