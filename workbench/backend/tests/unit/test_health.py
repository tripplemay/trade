"""Unit tests for the B020 /health endpoint and app factory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from workbench_api.app import VERSION, create_app


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["version"], str)
    assert payload["version"] != ""


def test_create_app_is_independent_instance() -> None:
    """Each call to create_app yields a fresh FastAPI instance.

    Prevents accidental shared mutable state across the test suite as B021+
    starts adding stateful middleware and dependencies.
    """

    app_one = create_app()
    app_two = create_app()
    assert app_one is not app_two


def test_version_constant_matches_response() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.json()["version"] == VERSION
