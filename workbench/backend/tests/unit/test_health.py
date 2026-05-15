"""Unit tests for ``/api/health`` and the app factory.

F002 extends the response with ``db_connectivity``. The test now sets up a
fresh SQLite + schema via the shared ``initialised_db`` fixture so the
``SELECT 1`` probe inside the handler has a real DB to talk to.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from workbench_api.app import VERSION, create_app


def test_health_returns_ok_version_and_db_connectivity(initialised_db: str) -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == VERSION
    assert payload["db_connectivity"] == "ok"


def test_health_does_not_require_auth(initialised_db: str) -> None:
    """Nginx upstream probe + external uptime monitors hit /api/health
    without any cookie; F001 + F002 keep it open by contract.
    """

    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_500_when_db_unreachable(monkeypatch, tmp_path) -> None:
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


def test_create_app_is_independent_instance() -> None:
    app_one = create_app()
    app_two = create_app()
    assert app_one is not app_two
