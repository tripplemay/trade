"""B022 F007 — /api/docs/{path} sanitiser + reader.

The sanitiser is the entire safety surface here; the reader is a single
file read. Tests pin:

* Traversal rejection (``..`` segments, absolute paths, root escape).
* 404 for sanitised-but-missing paths (no oracle for tree enumeration).
* 200 with the expected content_type for a real fixture file.
* Auth gate (anon → 401) so the docs reader cannot leak repo content
  to anonymous traffic.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.observability.active_users import active_users
from workbench_api.services.docs import (
    DocsNotFoundError,
    InvalidDocsPathError,
    load_doc,
    sanitize_repo_path,
)
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_active_users() -> None:
    active_users.clear()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "docs-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


# ----- Unit-level sanitiser checks (no HTTP layer involved). ---------------


def test_sanitize_rejects_empty_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidDocsPathError):
        sanitize_repo_path("", root=tmp_path)


def test_sanitize_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidDocsPathError):
        sanitize_repo_path("/etc/passwd", root=tmp_path)


def test_sanitize_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidDocsPathError):
        sanitize_repo_path("../../etc/passwd", root=tmp_path)


def test_sanitize_accepts_relative_path(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "spec.md"
    resolved = sanitize_repo_path("docs/spec.md", root=tmp_path)
    assert resolved == target.resolve()


def test_load_doc_404_on_missing(tmp_path: Path) -> None:
    with pytest.raises(DocsNotFoundError):
        load_doc("nope.md", root=tmp_path)


def test_load_doc_returns_markdown_content(tmp_path: Path) -> None:
    (tmp_path / "spec.md").write_text("# Hello", encoding="utf-8")
    result = load_doc("spec.md", root=tmp_path)
    assert result.path == "spec.md"
    assert result.content_type == "markdown"
    assert result.body == "# Hello"


# ----- HTTP-layer checks. --------------------------------------------------


def test_docs_endpoint_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/docs/README.md").status_code == 401


def test_docs_endpoint_rejects_traversal(initialised_db: str) -> None:
    client = _authed_client()
    # FastAPI normalises ``..`` segments in the URL before the handler sees
    # them; encode the parent traversal so the route does receive it raw.
    response = client.get("/api/docs/%2E%2E%2Fetc%2Fpasswd")
    assert response.status_code == 400, response.text


def test_docs_endpoint_404_on_missing(initialised_db: str) -> None:
    client = _authed_client()
    response = client.get("/api/docs/this-file-does-not-exist.md")
    assert response.status_code == 404
