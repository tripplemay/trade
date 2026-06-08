"""Snapshots list + SSE-streamed refresh (B022 F011, B049 F001).

GET path reads the SnapshotMeta repo and shapes rows into the schema
the frontend's DataTable consumes; nothing fancy.

POST refresh streams a sequence of stage events back as Server-Sent
Events so the frontend can render live progress. **B049 F001 (milestone-C
close-out):** the refresh now reflects the *real* on-disk data state. It
reads the unified prices + fundamentals CSVs the B045 data-refresh job
wrote (``data_refresh/inventory``) and the persisted coverage window,
grades the coverage, and records a SnapshotMeta row whose ``manifest_path``
and ``quality_status`` reflect the real data — replacing the F011 synthetic
5-stage animation (fixed sleeps) and the constant ``"ok"`` placeholder row.

The request path stays read-only and self-contained (§12.10.2): it reads
CSV/DB and writes only its own SnapshotMeta row — no ``trade`` import, no
subprocess, no execution. The heavy data fetch remains the B045 daily
``data_refresh.cli`` timer job; this surface only catalogs what that wrote.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workbench_api.data_refresh import inventory
from workbench_api.db.models.snapshot_meta import SnapshotMeta
from workbench_api.db.repositories.backtest_data_window import (
    BacktestDataWindowRepository,
)
from workbench_api.db.repositories.snapshot import SnapshotMetaRepository
from workbench_api.schemas.snapshots import (
    SnapshotListResponse,
    SnapshotSummary,
)

_logger = logging.getLogger("workbench.snapshots")


def list_snapshots(session: Session) -> SnapshotListResponse:
    """Return SnapshotMeta rows reshaped into the page's row schema.

    DB failure → log + return an empty list so the Snapshots page can
    render its empty state. B022 F014 fixing-round 3: Codex L2 still
    observed /api/snapshots 500 after round-2 because only the SSE
    refresh path was rewritten — this read path mirrored the
    dashboard / recommendations / backlog list shape that already got
    the degrade and was missed.
    """

    repo = SnapshotMetaRepository(session)
    try:
        rows = repo.list_all()
    except SQLAlchemyError as exc:
        _logger.warning(
            "snapshots list skipped due to DB error",
            extra={
                "event": "snapshots_list_db_error",
                "exception_message": str(exc),
            },
            exc_info=True,
        )
        session.rollback()
        return SnapshotListResponse(snapshots=[])
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


def _event(job_id: str, stage: str, detail: str) -> dict[str, object]:
    return {
        "job_id": job_id,
        "stage": stage,
        "detail": detail,
        "ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
    }


def _window_detail(session: Session, prices: inventory.CsvInventory) -> str:
    """Describe the coverage window, preferring the persisted backtest window.

    The data-refresh job writes the authoritative ``backtest_data_window`` row;
    when present it carries the conservative ``first_usable_signal_date`` the
    backtest page clamps to. Falls back to the prices CSV's own date range when
    no refresh has persisted a window yet."""

    try:
        window = BacktestDataWindowRepository(session).get_window()
    except SQLAlchemyError:
        session.rollback()
        window = None
    if window is not None:
        return (
            f"Coverage {window.data_start.isoformat()}–{window.data_end.isoformat()} "
            f"(first usable {window.first_usable_signal_date.isoformat()})."
        )
    if prices.data_start is not None and prices.data_end is not None:
        return (
            f"Coverage {prices.data_start.isoformat()}–{prices.data_end.isoformat()} "
            "(from prices CSV)."
        )
    return "No coverage window persisted yet — run the data-refresh job."


async def _iter_refresh_stages(
    session: Session, job_id: str
) -> AsyncIterator[dict[str, object]]:
    """Read the real on-disk data state and yield real progress events.

    Each stage is a genuine read of the data the B045 data-refresh job wrote —
    the cadence is dictated by file/DB I/O, not a fixed sleep. The final
    ``complete`` stage persists a SnapshotMeta row reflecting the real coverage.
    """

    root = inventory.data_root()
    yield _event(job_id, "locate", f"Resolving data root {root}.")

    prices = inventory.prices_inventory(root)
    if prices.present:
        yield _event(
            job_id,
            "read_prices",
            f"Prices: {prices.symbols} symbols, {prices.rows} rows.",
        )
    else:
        yield _event(job_id, "read_prices", f"Prices CSV not found at {prices.path}.")

    fundamentals = inventory.fundamentals_inventory(root)
    if fundamentals.present:
        yield _event(
            job_id,
            "read_fundamentals",
            f"Fundamentals: {fundamentals.symbols} symbols, {fundamentals.rows} rows.",
        )
    else:
        yield _event(
            job_id,
            "read_fundamentals",
            f"Fundamentals CSV not found at {fundamentals.path}.",
        )

    quality = inventory.grade_quality(prices, fundamentals)
    yield _event(
        job_id,
        "grade",
        f"{_window_detail(session, prices)} Quality: {quality}.",
    )

    snapshot_id = f"snap-{job_id}"
    manifest_path = str(prices.path)
    _persist_snapshot(session, snapshot_id, manifest_path, quality)
    yield _event(
        job_id,
        "complete",
        f"Recorded {snapshot_id} (quality {quality}).",
    )


async def refresh_event_stream(
    session_factory: Callable[[], Session],
) -> AsyncIterator[str]:
    """Run the real refresh and yield SSE-encoded progress events.

    **B022 F014 fixing-round 2:** the previous signature took a Session
    from FastAPI's ``get_session`` dependency. That session is torn
    down by the dependency generator the moment the route handler
    returns its StreamingResponse — i.e. *before* this async generator
    starts streaming. The first ORM call then raised against a closed
    session and Codex L2 saw ``unreachable: HTTP 500`` in the modal.

    Fix: the route passes a ``session_factory`` (an unbound
    sessionmaker call) and we own the session inside this generator's
    ``try/finally``, outliving the streaming response and any other
    FastAPI cleanup.

    The ``complete`` stage commits a SnapshotMeta row so the Snapshots
    page's list refresh shows the new entry. Failures inside the loop
    yield a ``stage: error`` event and re-raise so the client treats
    lack of ``complete`` as a failed run.
    """

    job_id = uuid.uuid4().hex[:12]
    session = session_factory()
    try:
        async for event in _iter_refresh_stages(session, job_id):
            yield _format_sse(event)
    except Exception as exc:
        session.rollback()
        yield _format_sse(
            {
                "job_id": job_id,
                "stage": "error",
                "detail": str(exc),
                "ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            }
        )
        raise
    finally:
        session.close()


def _persist_snapshot(
    session: Session, snapshot_id: str, manifest_path: str, quality_status: str
) -> None:
    """Insert (or refresh) the SnapshotMeta row for this run.

    Records the real ``manifest_path`` (the unified prices CSV this snapshot
    catalogs) and the real ``quality_status`` graded from coverage — no
    placeholder."""

    repo = SnapshotMetaRepository(session)
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    repo.upsert(
        SnapshotMeta(
            snapshot_id=snapshot_id,
            manifest_path=manifest_path,
            quality_status=quality_status,
            created_at=now,
        )
    )
    session.commit()
