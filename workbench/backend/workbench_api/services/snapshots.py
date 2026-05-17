"""Snapshots list + SSE-streamed refresh (B022 F011).

GET path reads the SnapshotMeta repo and shapes rows into the schema
the frontend's DataTable consumes; nothing fancy.

POST refresh is the more interesting surface — it streams a sequence
of stage events back as Server-Sent Events so the frontend can render
live progress. The real ``scripts/refresh_public_snapshot`` subprocess
hasn't been wired into the workbench yet (B023 takes that on); F011
ships a *synthetic* 5-stage progress generator that gives the modal
something to render and inserts a SnapshotMeta row on completion so
the list reflects the refresh.

The synthetic stages mirror the shape the real subprocess will emit
(prepare → fetch → process → store → complete), so swapping in the
real wiring later only touches the body of ``_iter_stages``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from workbench_api.db.models.snapshot_meta import SnapshotMeta
from workbench_api.db.repositories.snapshot import SnapshotMetaRepository
from workbench_api.schemas.snapshots import (
    SnapshotListResponse,
    SnapshotSummary,
)

# Sleep between synthetic stages. Kept very short so the modal feels
# responsive in dev and tests finish quickly; F014 Codex L2 runs the
# real subprocess on the VM where the cadence is dictated by I/O.
_STAGE_DELAY_SECONDS: float = 0.05


def list_snapshots(session: Session) -> SnapshotListResponse:
    """Return SnapshotMeta rows reshaped into the page's row schema."""

    repo = SnapshotMetaRepository(session)
    rows = repo.list_all()
    summaries: list[SnapshotSummary] = []
    for row in rows:
        created_at = row.created_at
        as_of = created_at.date().isoformat()
        summaries.append(
            SnapshotSummary(
                id=row.snapshot_id,
                as_of_date=as_of,
                created_at=created_at.isoformat(),
                quality_status=row.quality_status,
                file_path=row.manifest_path,
            )
        )
    return SnapshotListResponse(snapshots=summaries)


def _format_sse(event: dict[str, object]) -> str:
    """Wrap a JSON payload in the canonical SSE ``data:`` framing."""

    return f"data: {json.dumps(event)}\n\n"


async def _iter_stages(job_id: str) -> AsyncIterator[dict[str, object]]:
    """Yield the 5-stage synthetic progress event sequence."""

    stages: list[tuple[str, str]] = [
        ("prepare", "Resolving snapshot config + cache paths."),
        ("fetch", "Downloading public data + verifying checksums."),
        ("process", "Building manifest + computing quality status."),
        ("store", "Writing manifest to disk + indexing."),
        ("complete", "Refresh complete."),
    ]
    for stage, detail in stages:
        await asyncio.sleep(_STAGE_DELAY_SECONDS)
        yield {
            "job_id": job_id,
            "stage": stage,
            "detail": detail,
            "ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        }


async def refresh_event_stream(session: Session) -> AsyncIterator[str]:
    """Run the synthetic refresh and yield SSE-encoded events.

    The final ``complete`` stage commits a SnapshotMeta row so the
    Snapshots page's list refresh shows the new entry. Failures inside
    the loop yield a ``stage: error`` event and re-raise so FastAPI
    closes the connection — the frontend treats lack of ``complete``
    as a failed run and surfaces a toast.
    """

    job_id = uuid.uuid4().hex[:12]
    try:
        async for event in _iter_stages(job_id):
            if event["stage"] == "complete":
                _persist_snapshot(session, job_id, str(event["detail"]))
            yield _format_sse(event)
    except Exception as exc:  # pragma: no cover - safety net
        yield _format_sse(
            {
                "job_id": job_id,
                "stage": "error",
                "detail": str(exc),
                "ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            }
        )
        raise


def _persist_snapshot(session: Session, job_id: str, detail: str) -> None:
    """Insert (or refresh) the SnapshotMeta row for this run."""

    del detail  # currently unused — placeholder until real manifest data lands
    repo = SnapshotMetaRepository(session)
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    repo.upsert(
        SnapshotMeta(
            snapshot_id=f"snap-{job_id}",
            manifest_path=f"data/public-cache/{job_id}/manifest.json",
            quality_status="ok",
            created_at=now,
        )
    )
    session.commit()
