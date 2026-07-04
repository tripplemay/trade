"""Router for ``/api/monitoring`` — B080 strategy-lifecycle monitoring (read-only).

F001 surfaces the trial registry (the DSR ``N`` per strategy). Pure request-path
read of the ``trial_registry`` table — never imports ``trade`` (§12.10.2); the
worker + bootstrap own writes off-path. Advisory/research metadata only — no
execution affordance.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.db.session import SessionDep
from workbench_api.schemas.monitoring import (
    MetricRow,
    MetricsResponse,
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
