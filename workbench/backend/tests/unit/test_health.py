"""Unit tests for ``/api/health`` and the app factory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from workbench_api.app import VERSION, create_app


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["version"], str)
    assert payload["version"] != ""


def test_health_does_not_require_auth() -> None:
    """Nginx upstream probe + external uptime monitors hit /api/health
    without any cookie; F001 must keep it open by contract.
    """

    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200


def test_create_app_is_independent_instance() -> None:
    app_one = create_app()
    app_two = create_app()
    assert app_one is not app_two


def test_version_constant_matches_response() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.json()["version"] == VERSION
