"""Router for ``/api/monitoring`` — B080 strategy-lifecycle monitoring (read-only).

F001 surfaces the trial registry (the DSR ``N`` per strategy). Pure request-path
read of the ``trial_registry`` table — never imports ``trade`` (§12.10.2); the
worker + bootstrap own writes off-path. Advisory/research metadata only — no
execution affordance.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.db.session import SessionDep
from workbench_api.monitoring.reverify_service import (
    UnknownStrategyError,
    enqueue_reverify,
    get_reverify_job,
)
from workbench_api.schemas.monitoring import (
    MetricRow,
    MetricsResponse,
    ReverifyJobStatus,
    ReverifyRequest,
    ReverifyResponse,
    TrialRow,
    TrialsResponse,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/trials", response_model=TrialsResponse)
def list_trials_route(
    session: SessionDep,
    _user: AuthenticatedUserDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> TrialsResponse:
    """The registered trial log + the per-strategy trial count (DSR ``N``)."""

    repo = TrialRegistryRepository(session)
    rows = repo.list_recent(limit=limit)
    counts = repo.counts_by_strategy()
    trials = [
        TrialRow(
            id=r.id,
            batch=r.batch,
            strategy_id=r.strategy_id,
            parameter_hash=r.parameter_hash,
            params=r.params,
            universe=r.universe,
            window_start=r.window_start,
            window_end=r.window_end,
            oos_split=r.oos_split,
            metrics=r.metrics,
            verdict=r.verdict,
            source_ref=r.source_ref,
            notes=r.notes,
        )
        for r in rows
    ]
    return TrialsResponse(
        trials=trials, counts_by_strategy=counts, total=sum(counts.values())
    )


@router.get("/metrics", response_model=MetricsResponse)
def list_metrics_route(
    session: SessionDep,
    _user: AuthenticatedUserDep,
    strategy_id: Annotated[str | None, Query()] = None,
) -> MetricsResponse:
    """L0 monitoring metrics (rolling IC / tracking / exposure / turnover). Optional
    ``strategy_id`` filter. Advisory-only — thresholds in ``meta`` are hints, not
    a trade signal."""

    repo = MonitoringMetricRepository(session)
    rows = repo.list_by_strategy(strategy_id) if strategy_id else repo.list_all()
    metrics = [
        MetricRow(
            strategy_id=r.strategy_id,
            as_of=r.as_of,
            metric=r.metric,
            value=r.value,
            meta=r.meta,
        )
        for r in rows
    ]
    return MetricsResponse(metrics=metrics, total=len(metrics))


@router.post(
    "/reverify", response_model=ReverifyResponse, status_code=status.HTTP_202_ACCEPTED
)
def enqueue_reverify_route(
    payload: ReverifyRequest,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> ReverifyResponse:
    """Enqueue a frozen re-validation (deduped). The worker runs the long fetch +
    backtest off the request path; poll GET /reverify/{job_id} for the result."""

    try:
        job = enqueue_reverify(
            session, strategy_id=payload.strategy_id, as_of=payload.as_of
        )
    except UnknownStrategyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown reverify strategy: {exc}",
        ) from exc
    session.commit()
    return ReverifyResponse(
        job_id=job.job_id, strategy_id=job.strategy_id, status=job.status
    )


@router.get("/reverify/{job_id}", response_model=ReverifyJobStatus)
def get_reverify_route(
    job_id: str,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> ReverifyJobStatus:
    """Poll a re-validation job's status + terminal result (report ref / verdict)."""

    job = get_reverify_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return ReverifyJobStatus(
        job_id=job.job_id,
        strategy_id=job.strategy_id,
        status=job.status,
        as_of=job.as_of,
        report_ref=job.report_ref,
        verdict=job.verdict,
        error=job.error,
        error_kind=job.error_kind,
    )
