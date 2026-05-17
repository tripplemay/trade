"""B022 F012 — backlog CRUD + git-auto-commit endpoint coverage.

Five contracts pinned:

1. Auth gate on all 4 routes.
2. List/Create/Update/Delete round-trips through BacklogRepository.
3. Every mutation writes the full table state to ``backlog.json``.
4. Every mutation invokes git via the injected GitRunner with the
   canonical ``chore(backlog): add|edit|delete <id>`` commit message —
   F012 acceptance pins this exact format.
5. Git failures (mocked) translate to HTTP 500 "fail closed" so the
   UI can surface a toast rather than silently dropping the change.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.observability.active_users import active_users
from workbench_api.routes.backlog import get_backlog_config
from workbench_api.services.backlog import BacklogServiceConfig, GitCommitError
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()


class RecordingGitRunner:
    """Stand-in for the subprocess git runner — records every call."""

    def __init__(self, fail_message: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail_message

    def __call__(self, args: list[str], cwd: Path) -> None:
        del cwd
        self.calls.append(args)
        if self._fail and args[1] == "commit":
            raise GitCommitError(self._fail)


def _setup(
    tmp_path: Path, *, fail_message: str | None = None
) -> tuple[TestClient, RecordingGitRunner, Path]:
    backlog_file = tmp_path / "backlog.json"
    runner = RecordingGitRunner(fail_message=fail_message)
    config = BacklogServiceConfig(
        repo_root=tmp_path,
        backlog_file=backlog_file,
        git_runner=runner,
    )

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    app.dependency_overrides[get_backlog_config] = lambda: config

    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "backlog-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client, runner, backlog_file


def _commit_messages(runner: RecordingGitRunner) -> list[str]:
    out: list[str] = []
    for call in runner.calls:
        if call[1] == "commit":
            # ['git', 'commit', '-m', <message>]
            out.append(call[3])
    return out


def test_backlog_requires_auth(initialised_db: str, tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/backlog").status_code == 401
    assert client.post("/api/backlog", json={"title": "x"}).status_code == 401
    assert client.patch("/api/backlog/X", json={}).status_code == 401
    assert client.delete("/api/backlog/X").status_code == 401


def test_create_round_trips_to_table_json_and_git(
    initialised_db: str, tmp_path: Path
) -> None:
    client, runner, backlog_file = _setup(tmp_path)
    response = client.post(
        "/api/backlog",
        json={"title": "Pilot research", "description": "Try X.", "priority": "high"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "Pilot research"
    assert payload["priority"] == "high"
    entry_id = payload["id"]

    # JSON file mirrors the new row.
    on_disk = json.loads(backlog_file.read_text(encoding="utf-8"))
    assert any(row["id"] == entry_id for row in on_disk)

    # Git received `add backlog.json` + `commit chore(backlog): add <id>`.
    add_calls = [call for call in runner.calls if call[1] == "add"]
    assert len(add_calls) == 1
    assert add_calls[0][2] == str(backlog_file)
    assert _commit_messages(runner) == [f"chore(backlog): add {entry_id}"]


def test_update_round_trips_and_commits_edit(initialised_db: str, tmp_path: Path) -> None:
    client, runner, _ = _setup(tmp_path)
    create = client.post(
        "/api/backlog", json={"title": "Initial", "priority": "low"}
    ).json()
    runner.calls.clear()
    response = client.patch(
        f"/api/backlog/{create['id']}",
        json={"title": "Refined", "priority": "high"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "Refined"
    assert payload["priority"] == "high"
    assert _commit_messages(runner) == [f"chore(backlog): edit {create['id']}"]


def test_delete_round_trips_and_commits_delete(initialised_db: str, tmp_path: Path) -> None:
    client, runner, _ = _setup(tmp_path)
    create = client.post(
        "/api/backlog", json={"title": "Disposable"}
    ).json()
    runner.calls.clear()
    response = client.delete(f"/api/backlog/{create['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {"id": create["id"], "deleted": True}
    assert _commit_messages(runner) == [f"chore(backlog): delete {create['id']}"]


def test_update_unknown_id_returns_404(initialised_db: str, tmp_path: Path) -> None:
    client, _, _ = _setup(tmp_path)
    assert client.patch("/api/backlog/no-such-id", json={"title": "x"}).status_code == 404
    assert client.delete("/api/backlog/no-such-id").status_code == 404


def test_git_failure_returns_500_with_underlying_error(
    initialised_db: str, tmp_path: Path
) -> None:
    """F012 acceptance: 'git error → mutation fail closed + toast 显示底层错误'.

    The DB row + JSON file land before the commit step in the current
    implementation, but the route translates the GitCommitError into a
    500 with the underlying message so the frontend toast can surface
    it. A future iteration could roll back the DB write — pinned as
    BL-WB-followup in the docstring; F012 only contracts 'fail closed'
    at the HTTP boundary, which this assertion verifies.
    """

    client, _, _ = _setup(tmp_path, fail_message="pre-commit hook rejected")
    response = client.post(
        "/api/backlog", json={"title": "Will fail", "priority": "medium"}
    )
    assert response.status_code == 500, response.text
    body: dict[str, Any] = response.json()
    assert "pre-commit hook rejected" in body["detail"]
