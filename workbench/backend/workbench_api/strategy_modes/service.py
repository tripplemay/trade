"""B057 F005 / B058 F003 — strategy-mode service.

* ``list_strategy_modes`` (B057 F005) builds the ``GET /api/strategy-modes``
  selector response from the canonical registry.
* ``enqueue_target_refresh`` / ``get_target_refresh_job`` (B058 F003) are the
  request-path side of the generic "refresh this mode's target on demand"
  primitive: enqueue a job row + poll it. **Self-contained per §12.10.2** — they
  only touch the registry + the ``target_refresh_job`` table; they NEVER import
  ``trade`` or the refresh worker (which imports trade). The worker daemon runs
  the producer off the request path.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workbench_api.db.repositories.target_refresh_job import TargetRefreshJobRepository
from workbench_api.schemas.strategy_modes import (
    StrategyModeInfo,
    StrategyModesResponse,
    TargetRefreshJobStatus,
    TargetRefreshResponse,
)
from workbench_api.strategy_modes.registry import list_modes, mode_for_strategy


class UnknownStrategyModeError(RuntimeError):
    """The requested ``strategy_id`` is not a registered platform mode."""


def list_strategy_modes() -> StrategyModesResponse:
    """Return every registered mode in selector order (flagship first)."""

    return StrategyModesResponse(
        modes=[
            StrategyModeInfo(
                id=mode.id,
                strategy_id=mode.strategy_id,
                display_name=mode.display_name,
                funding_state=mode.funding_state,
                is_research_state=mode.is_research_state,
                cadence=mode.cadence,
                description=mode.description,
            )
            for mode in list_modes()
        ]
    )


def enqueue_target_refresh(
    session: Session, strategy_id: str
) -> TargetRefreshResponse:
    """Enqueue a manual target-refresh job for ``strategy_id`` (no ``trade`` import).

    Validates the mode is registered; dedups an in-flight *queued* job (returns it
    rather than spawning a duplicate); commits the queued row so the off-path
    worker daemon (a separate process) sees it. Raises
    :class:`UnknownStrategyModeError` for an unregistered strategy."""

    if mode_for_strategy(strategy_id) is None:
        raise UnknownStrategyModeError(strategy_id)
    repo = TargetRefreshJobRepository(session)
    existing = repo.latest_queued(strategy_id)
    if existing is not None:
        return TargetRefreshResponse(
            job_id=existing.job_id, strategy_id=strategy_id, status=existing.status
        )
    job = repo.enqueue(strategy_id=strategy_id)
    session.commit()
    return TargetRefreshResponse(
        job_id=job.job_id, strategy_id=strategy_id, status=job.status
    )


def get_target_refresh_job(
    session: Session, job_id: str
) -> TargetRefreshJobStatus | None:
    """Poll a refresh job's status + result (``None`` if the job_id is unknown)."""

    row = TargetRefreshJobRepository(session).get_by_id(job_id)
    if row is None:
        return None
    return TargetRefreshJobStatus(
        job_id=row.job_id,
        strategy_id=row.strategy_id,
        status=row.status,
        as_of_date=row.as_of_date,
        saved_count=row.saved_count,
        data_source=row.data_source,
        error=row.error,
        error_kind=row.error_kind,
    )
