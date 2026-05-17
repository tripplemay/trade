"""B022 F011 — snapshots list + SSE refresh endpoint coverage.

Pins the four contracts the frontend depends on:

1. Auth gate on both routes (anon → 401).
2. List shape — SnapshotSummary rows reflect the SnapshotMeta repo.
3. SSE refresh — POST returns ``text/event-stream``; the stream carries
   at minimum a ``stage: complete`` event.
4. DB side-effect — after a refresh, SnapshotMetaRepository has at
   least one row (the synthetic _persist_snapshot inserted by the
   complete stage). Subsequent GET surfaces the row.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.db.engine import get_engine
from workbench_api.db.models.snapshot_meta import SnapshotMeta
from workbench_api.observability.active_users import active_users
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    active_users.clear()


def _authed_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "snapshots-test", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def _seed_snapshot(snapshot_id: str = "snap-fixture") -> None:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            SnapshotMeta(
                snapshot_id=snapshot_id,
                manifest_path=f"data/public-cache/{snapshot_id}/manifest.json",
                quality_status="ok",
                created_at=datetime(2026, 5, 17, 12, 0, 0),
            )
        )
        session.commit()


def test_snapshots_list_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/snapshots").status_code == 401
    assert client.post("/api/snapshots/refresh").status_code == 401


def test_snapshots_list_returns_repo_rows(initialised_db: str) -> None:
    _seed_snapshot("snap-A")
    _seed_snapshot("snap-B")
    client = _authed_client()
    payload = client.get("/api/snapshots").json()
    ids = [row["id"] for row in payload["snapshots"]]
    assert sorted(ids) == ["snap-A", "snap-B"]
    assert payload["snapshots"][0]["quality_status"] == "ok"


def test_snapshots_refresh_streams_sse_events_and_inserts_row(
    initialised_db: str,
) -> None:
    client = _authed_client()
    response = client.post("/api/snapshots/refresh")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    # Split into events by the blank-line delimiter; each event must
    # start with `data: `.
    events: list[dict[str, object]] = []
    for raw in body.split("\n\n"):
        line = raw.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: "):]))
    stages = [event["stage"] for event in events]
    assert "complete" in stages, stages
    # The complete stage persists a SnapshotMeta row → next GET surfaces it.
    follow_up = client.get("/api/snapshots").json()
    assert len(follow_up["snapshots"]) >= 1
    snapshot_ids = [row["id"] for row in follow_up["snapshots"]]
    assert any(sid.startswith("snap-") for sid in snapshot_ids)
