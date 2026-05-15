"""Integration-style tests for the auth FastAPI dependency.

We mount ``require_authenticated_user`` on a tiny throwaway app and exercise
every response the F001 acceptance demands at the HTTP layer:

* 200 with allowlisted JWT cookie
* 401 with no cookie / malformed cookie / wrong-secret cookie / expired
* 403 with valid signature but non-allowlisted email
* 500 when server-side allowlist env vars are missing
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import JWT_ALGORITHM, AuthenticatedUser
from workbench_api.settings import Settings, get_settings

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]

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


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    def probe(user: AuthenticatedUserDep) -> dict[str, str]:
        return {"email": user.email}

    return app


@pytest.fixture
def client_with_settings() -> Iterator[tuple[TestClient, FastAPI]]:
    app = _build_app()
    with TestClient(app) as client:
        yield client, app


def _override_settings(app: FastAPI, settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: settings


def _configured() -> Settings:
    return Settings(NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL)


def test_probe_returns_200_with_allowlisted_cookie(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    client, app = client_with_settings
    _override_settings(app, _configured())
    client.cookies.set("authjs.session-token", _make_token(_baseline_claims()))
    response = client.get("/probe")
    assert response.status_code == 200
    assert response.json() == {"email": ALLOWED_EMAIL}


def test_probe_returns_401_without_cookie(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    client, app = client_with_settings
    _override_settings(app, _configured())
    response = client.get("/probe")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Cookie"


def test_probe_returns_401_with_wrong_secret_cookie(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    client, app = client_with_settings
    _override_settings(app, _configured())
    client.cookies.set(
        "authjs.session-token",
        _make_token(_baseline_claims(), secret="different-secret"),
    )
    response = client.get("/probe")
    assert response.status_code == 401


def test_probe_returns_401_with_expired_cookie(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    client, app = client_with_settings
    _override_settings(app, _configured())
    client.cookies.set("authjs.session-token", _make_token(_baseline_claims(ttl=-60)))
    response = client.get("/probe")
    assert response.status_code == 401


def test_probe_returns_403_for_non_allowlisted_email(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    client, app = client_with_settings
    _override_settings(app, _configured())
    client.cookies.set(
        "authjs.session-token",
        _make_token(_baseline_claims(email="stranger@example.com")),
    )
    response = client.get("/probe")
    assert response.status_code == 403


def test_probe_returns_500_when_server_misconfigured(
    client_with_settings: tuple[TestClient, FastAPI],
) -> None:
    """Missing NEXTAUTH_SECRET / ALLOWED_USER_EMAIL must fail loud, not open."""

    client, app = client_with_settings
    _override_settings(app, Settings(NEXTAUTH_SECRET=None, ALLOWED_USER_EMAIL=None))
    client.cookies.set("authjs.session-token", _make_token(_baseline_claims()))
    response = client.get("/probe")
    assert response.status_code == 500
