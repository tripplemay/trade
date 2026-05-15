"""Unit tests for :mod:`workbench_api.auth.jwt_validator`.

Covers the four canonical paths the F001 acceptance demands at the protocol
layer (cookie extraction → signature/expiry → email claim → allowlist):

* Valid token whose email matches the allowlist
* Missing cookie
* Tampered / wrong-secret signature
* Expired token
* Valid signature whose email is not on the allowlist
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from jose import jwt

from workbench_api.auth.jwt_validator import (
    JWT_ALGORITHM,
    SESSION_COOKIE_NAMES,
    AuthenticatedUser,
    EmailNotAllowedError,
    InvalidSessionTokenError,
    MissingEmailClaimError,
    MissingSessionCookieError,
    authenticate,
    decode_session_token,
    extract_session_token,
)

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


def _make_token(claims: dict[str, Any], *, secret: str = SECRET) -> str:
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def _baseline_claims(email: str = ALLOWED_EMAIL, *, ttl: int = 3600) -> dict[str, Any]:
    now = int(time.time())
    return {
        "email": email,
        "sub": "user-id-1",
        "iat": now,
        "exp": now + ttl,
    }


def test_extract_prefers_secure_cookie_when_both_present() -> None:
    cookies = {
        "authjs.session-token": "insecure-value",
        "__Secure-authjs.session-token": "secure-value",
    }
    assert extract_session_token(cookies) == "secure-value"


def test_extract_falls_back_to_dev_cookie() -> None:
    cookies = {"authjs.session-token": "dev-value"}
    assert extract_session_token(cookies) == "dev-value"


def test_extract_raises_when_no_session_cookie() -> None:
    with pytest.raises(MissingSessionCookieError):
        extract_session_token({"unrelated": "x"})


def test_session_cookie_names_cover_v5_defaults() -> None:
    # If Auth.js renames the cookie this list must be updated together with
    # the upstream change; the test pins the expectation.
    assert SESSION_COOKIE_NAMES == (
        "__Secure-authjs.session-token",
        "authjs.session-token",
    )


def test_decode_accepts_valid_token() -> None:
    token = _make_token(_baseline_claims())
    claims = decode_session_token(token, SECRET)
    assert claims["email"] == ALLOWED_EMAIL


def test_decode_rejects_wrong_secret() -> None:
    token = _make_token(_baseline_claims())
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(token, secret="different-secret")


def test_decode_rejects_expired_token() -> None:
    token = _make_token(_baseline_claims(ttl=-60))
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(token, SECRET)


def test_decode_rejects_token_without_exp() -> None:
    token = _make_token({"email": ALLOWED_EMAIL, "sub": "x"})
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(token, SECRET)


def test_authenticate_happy_path_returns_user() -> None:
    cookies = {"authjs.session-token": _make_token(_baseline_claims())}
    user = authenticate(cookies, secret=SECRET, allowed_email=ALLOWED_EMAIL)
    assert isinstance(user, AuthenticatedUser)
    assert user.email == ALLOWED_EMAIL


def test_authenticate_treats_email_case_insensitively() -> None:
    cookies = {"authjs.session-token": _make_token(_baseline_claims(email="Owner@Example.COM"))}
    user = authenticate(cookies, secret=SECRET, allowed_email="owner@example.com")
    assert user.email == "Owner@Example.COM"


def test_authenticate_rejects_missing_email_claim() -> None:
    cookies = {
        "authjs.session-token": _make_token(
            {"sub": "user-id-1", "iat": int(time.time()), "exp": int(time.time()) + 3600}
        )
    }
    with pytest.raises(MissingEmailClaimError):
        authenticate(cookies, secret=SECRET, allowed_email=ALLOWED_EMAIL)


def test_authenticate_rejects_non_allowlisted_email() -> None:
    cookies = {
        "authjs.session-token": _make_token(_baseline_claims(email="stranger@example.com"))
    }
    with pytest.raises(EmailNotAllowedError):
        authenticate(cookies, secret=SECRET, allowed_email=ALLOWED_EMAIL)


def test_authenticate_propagates_missing_cookie() -> None:
    with pytest.raises(MissingSessionCookieError):
        authenticate({}, secret=SECRET, allowed_email=ALLOWED_EMAIL)
