"""B080 F003 — reverify worker step (drains the reverify_job queue).

Mirrors the target-refresh worker: ``process_next_reverify`` claims one queued job,
runs the (long) data-append + frozen backtest + three landings, and writes the
terminal state; ``recover_orphaned_reverify`` sweeps rows left ``running`` by a
crashed process at startup. Wired into the existing backtest worker's poll loop —
no separate long-running daemon. Never raises (a bad job → ``error`` row, loop
continues), matching the B053 worker discipline.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.repositories.reverify_job import ReverifyJobRepository
from workbench_api.monitoring.reverify_runner import run_reverify

logger = logging.getLogger(__name__)


def recover_orphaned_reverify(session: Session) -> int:
    """Startup sweep: reclaim ``running`` reverify rows as ``error``/interrupted."""

    n = ReverifyJobRepository(session).recover_orphaned_running(
        error="worker restarted mid-reverify", error_kind="interrupted"
    )
    if n:
        session.commit()
        logger.info("recovered %d orphaned reverify job(s)", n)
    return n


def _resolve_roots(as_of: date) -> tuple[Path, Path, Path]:
    """Resolve (b070_root, reverify_root, repo_root) under WORKBENCH_DATA_ROOT.

    On the VM ``WORKBENCH_DATA_ROOT`` is the writable data dir; the md report lands
    under ``<data_root>/docs/test-reports/auto/`` (the deployed repo tree is
    read-only under ProtectSystem=strict). Locally it falls back to the repo root."""

    data_root = os.environ.get("WORKBENCH_DATA_ROOT")
    base = Path(data_root) if data_root else Path(__file__).resolve().parents[4]
    b070_root = base / "research" / "b070" if data_root else base / "data" / "research" / "b070"
    reverify_root = (
        base / "research" / "reverify" / as_of.isoformat()
        if data_root
        else base / "data" / "research" / "reverify" / as_of.isoformat()
    )
    return b070_root, reverify_root, base


def process_next_reverify(session: Session) -> bool:
    """Claim + run the next queued reverify job. Returns True if one was handled."""

    repo = ReverifyJobRepository(session)
    job = repo.claim_next_queued()
    if job is None:
        return False
    session.commit()  # persist the claim before the long run
    job_id, strategy_id = job.job_id, job.strategy_id
    as_of = date.fromisoformat(job.as_of) if job.as_of else datetime.now(UTC).date()
    try:
        b070_root, reverify_root, repo_root = _resolve_roots(as_of)
        result = run_reverify(
            session,
            strategy_id=strategy_id,
            as_of=as_of,
            repo_root=repo_root,
            b070_root=b070_root,
            reverify_root=reverify_root,
        )
        repo.save_result(
            job_id, report_ref=result["report_ref"], verdict=result["verdict"]
        )
        session.commit()
        logger.info("reverify %s done: %s", job_id, result.get("verdict"))
    except Exception as exc:  # noqa: BLE001 — a bad job must not kill the worker loop
        session.rollback()
        repo.save_error(job_id, str(exc)[:2000], error_kind=type(exc).__name__)
        session.commit()
        logger.warning("reverify %s failed: %s", job_id, exc)
    return True
