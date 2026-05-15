"""Unit tests for ``/api/health`` and the app factory.

F002 introduced ``db_connectivity``. F006 adds ``uptime_seconds``,
``last_backup_age_seconds``, ``last_backup_size_bytes`` and
``active_user_count``. The tests below exercise:

* the happy path (all six fields present)
* the auth-free contract (nginx upstream + uptime monitors)
* the 500 path when the DB is unreachable
* the backup-status surface when the log file exists vs is missing
* ``active_user_count`` reflecting the auth-dependency's side effect
"""

from __future__ import annotations

import calendar
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import VERSION, create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_active_users() -> None:
    """Each health test starts with an empty active-user registry."""

    active_users.clear()


def test_health_returns_all_b021_fields(initialised_db: str) -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == VERSION
    assert payload["db_connectivity"] == "ok"
    assert isinstance(payload["uptime_seconds"], (int, float))
    assert payload["uptime_seconds"] >= 0
    assert "last_backup_age_seconds" in payload  # may be null when no log
    assert "last_backup_size_bytes" in payload
    assert isinstance(payload["active_user_count"], int)


def test_health_does_not_require_auth(initialised_db: str) -> None:
    """Nginx upstream probe + external uptime monitors hit /api/health
    without any cookie; F001 + F002 keep it open by contract.
    """

    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_500_when_db_unreachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pointing the workbench at a directory with no write permission makes
    ``CREATE TABLE`` fail and the engine's first query throw. The handler
    must surface that as 500 rather than silently returning ok.
    """

    bad_url = f"sqlite:////proc/this-is-not-a-real-path/{tmp_path.name}.db"
    monkeypatch.setenv("WORKBENCH_DB_URL", bad_url)
    from workbench_api.db.engine import reset_engine

    reset_engine()
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 500
    assert response.json()["detail"] == "db_unreachable"


def test_health_surfaces_backup_status_when_log_present(
    initialised_db: str, tmp_path: Path
) -> None:
    """When the configured backup log has a recent OK line, /api/health
    reports the age + size fields as numbers (not None)."""

    log = tmp_path / "backup.log"
    # Build a log line ~60 seconds in the past so the age is roughly known.
    past_epoch = int(time.time()) - 60
    past_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(past_epoch))
    log.write_text(
        f"{past_iso} OK backup snapshot_bytes=2048 gzip_bytes=789 "
        f"duration_s=2 remote=gs://b/daily/x.gz\n",
        encoding="utf-8",
    )

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(WORKBENCH_BACKUP_LOG=str(log))
    client = TestClient(app)
    payload = client.get("/api/health").json()

    assert payload["last_backup_size_bytes"] == 789
    assert payload["last_backup_age_seconds"] is not None
    # Allow some slack for test execution overhead.
    assert 50.0 <= payload["last_backup_age_seconds"] <= 120.0


def test_health_returns_null_backup_fields_when_log_missing(
    initialised_db: str, tmp_path: Path
) -> None:
    bogus_log = tmp_path / "absent.log"
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        WORKBENCH_BACKUP_LOG=str(bogus_log)
    )
    client = TestClient(app)
    payload = client.get("/api/health").json()
    assert payload["last_backup_age_seconds"] is None
    assert payload["last_backup_size_bytes"] is None


def _make_token(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, SECRET, algorithm=JWT_ALGORITHM)


def test_health_reflects_active_user_count_after_protected_request(
    initialised_db: str,
) -> None:
    """A successful auth pass through /api/protected-test must show up
    on the very next /api/health probe.
    """

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)

    # No traffic yet.
    assert client.get("/api/health").json()["active_user_count"] == 0

    now = int(time.time())
    token = _make_token(
        {"email": ALLOWED_EMAIL, "sub": "user-1", "iat": now, "exp": now + 3600}
    )
    client.cookies.set("authjs.session-token", token)
    protected = client.get("/api/protected-test")
    assert protected.status_code == 200

    refreshed = client.get("/api/health").json()
    assert refreshed["active_user_count"] == 1


def test_create_app_is_independent_instance() -> None:
    app_one = create_app()
    app_two = create_app()
    assert app_one is not app_two


# Anchor `calendar` import — used in the timestamp helper above when
# debugging individual test failures.
_ = calendar
