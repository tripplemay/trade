"""Tests for the request-id middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from workbench_api.observability.logging import REQUEST_ID_VAR
from workbench_api.observability.middleware import RequestIDMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    def echo(request: Request) -> dict[str, str | None]:
        return {
            "via_state": getattr(request.state, "request_id", None),
            "via_contextvar": REQUEST_ID_VAR.get(),
        }

    return app


def test_middleware_mints_request_id_when_absent() -> None:
    client = TestClient(_make_app())
    response = client.get("/echo")
    assert response.status_code == 200
    body = response.json()
    minted = body["via_state"]
    assert isinstance(minted, str) and minted
    assert body["via_contextvar"] == minted
    assert response.headers["X-Request-ID"] == minted


def test_middleware_forwards_caller_supplied_request_id() -> None:
    client = TestClient(_make_app())
    response = client.get("/echo", headers={"X-Request-ID": "trace-1234"})
    body = response.json()
    assert body["via_state"] == "trace-1234"
    assert body["via_contextvar"] == "trace-1234"
    assert response.headers["X-Request-ID"] == "trace-1234"


def test_middleware_resets_contextvars_after_request() -> None:
    client = TestClient(_make_app())
    client.get("/echo")
    # After the request unwinds the contextvar must be back to its default.
    assert REQUEST_ID_VAR.get() is None
