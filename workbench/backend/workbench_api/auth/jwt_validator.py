"""Validate NextAuth/Auth.js session JWTs on the backend.

NextAuth.js v5 signs JWE-encrypted cookies by default. ``workbench/frontend/
src/lib/auth.ts`` overrides ``jwt.encode`` / ``jwt.decode`` so the cookie is a
plain HS256 JWS instead, sharing ``NEXTAUTH_SECRET`` with the backend. That
lets python-jose verify the same token without porting Auth.js's HKDF + JWE
key derivation to Python.

Cookie name handling: Auth.js v5 uses ``authjs.session-token`` in
non-HTTPS contexts and ``__Secure-authjs.session-token`` once the cookie is
issued ``Secure`` (production behind ``trade.guangai.ai``). The validator
checks the production name first so the prefix-based browser hardening is
honored even in test setups that send both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

JWT_ALGORITHM: str = "HS256"

# Auth.js v5 default cookie names. Order matters: the ``__Secure-`` variant
# wins when both are present so a downgrade attack that injects the insecure
# cookie alongside the legitimate Secure one is ignored.
SESSION_COOKIE_NAMES: tuple[str, ...] = (
    "__Secure-authjs.session-token",
    "authjs.session-token",
)


class AuthError(Exception):
    """Base class for authentication failures surfaced to the HTTP layer."""


class MissingSessionCookieError(AuthError):
    """The request carried no Auth.js session cookie."""


class InvalidSessionTokenError(AuthError):
    """The session cookie was present but failed signature / expiry checks."""


class MissingEmailClaimError(AuthError):
    """The verified token did not include an ``email`` claim."""


class EmailNotAllowedError(AuthError):
    """The verified email is not on the single-user allowlist."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Result of a successful session validation."""

    email: str


def extract_session_token(cookies: dict[str, str]) -> str:
    """Return the first present Auth.js session cookie.

    Raises ``MissingSessionCookieError`` when neither name is set.
    """

    for name in SESSION_COOKIE_NAMES:
        token = cookies.get(name)
        if token:
            return token
    raise MissingSessionCookieError(
        "No Auth.js session cookie present (expected "
        f"one of {SESSION_COOKIE_NAMES})."
    )


def decode_session_token(token: str, secret: str) -> dict[str, Any]:
    """Verify ``token`` against ``secret`` and return its claims.

    ``jose`` validates signature and ``exp`` automatically. Any failure
    (bad signature, expired, malformed) surfaces as
    ``InvalidSessionTokenError``.
    """

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require_exp": True, "verify_exp": True},
        )
    except ExpiredSignatureError as exc:
        raise InvalidSessionTokenError("Session token expired.") from exc
    except JWTError as exc:
        raise InvalidSessionTokenError(f"Session token failed validation: {exc}") from exc
    return claims


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def authenticate(
    cookies: dict[str, str],
    *,
    secret: str,
    allowed_email: str,
) -> AuthenticatedUser:
    """End-to-end: cookie → verified token → email → allowlist check.

    Each failure mode maps to its own exception so the FastAPI dependency
    layer can translate them into distinct HTTP responses (401 vs 403).
    """

    token = extract_session_token(cookies)
    claims = decode_session_token(token, secret)

    email_claim = claims.get("email")
    if not isinstance(email_claim, str) or not email_claim:
        raise MissingEmailClaimError("Session token missing 'email' claim.")

    if _normalize_email(email_claim) != _normalize_email(allowed_email):
        raise EmailNotAllowedError(
            "Authenticated email is not on the workbench allowlist."
        )

    return AuthenticatedUser(email=email_claim)
