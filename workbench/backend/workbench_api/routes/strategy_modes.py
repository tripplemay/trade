"""Router for ``/api/strategy-modes`` — B057 F005 selector + B058 F003 refresh.

The ``refresh-target`` endpoints are the generic manual target-refresh primitive.
The request path NEVER imports ``trade`` (§12.10.2): ``POST`` only enqueues a job
row, the worker daemon runs the producer off-path, and ``GET`` polls the job.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import t
from workbench_api.schemas.strategy_modes import (
    StrategyModesResponse,
    TargetRefreshJobStatus,
    TargetRefreshResponse,
)
from workbench_api.strategy_modes.service import (
    UnknownStrategyModeError,
    enqueue_target_refresh,
    get_target_refresh_job,
    list_strategy_modes,
)

router = APIRouter(prefix="/strategy-modes", tags=["strategy-modes"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=StrategyModesResponse)
def list_strategy_modes_route(_user: AuthenticatedUserDep) -> StrategyModesResponse:
    """Enumerate the platform's strategy modes (Master + regime + future).

    The frontend mode selector reads this; research-state modes are marked so
    the surface can show 研究态 / 前向验证中 honestly (B057 §1 capability ≠ funding).
    """

    return list_strategy_modes()


@router.get("/refresh-target/{job_id}", response_model=TargetRefreshJobStatus)
def get_refresh_target_route(
    job_id: str,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> TargetRefreshJobStatus:
    """Poll a manual target-refresh job (read-only; never imports ``trade``).

    Registered before the literal-prefixed POST so the dynamic ``{job_id}`` does
    not shadow another path."""

    result = get_target_refresh_job(session, job_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("strategy_modes.refresh_job_not_found", job_id=job_id),
        )
    return result


@router.post(
    "/{strategy_id}/refresh-target",
    response_model=TargetRefreshResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_target_route(
    strategy_id: str,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> TargetRefreshResponse:
    """Enqueue a manual target refresh for ``strategy_id`` (returns 202 + job_id).

    Off the request path the worker daemon runs the mode's target producer and
    writes a fresh ``recommendation_snapshot`` — generating the target on demand
    (the regime mode no longer waits for its monthly timer, B058 S1)."""

    try:
        return enqueue_target_refresh(session, strategy_id)
    except UnknownStrategyModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("strategy_modes.unknown_mode", id=strategy_id),
        ) from exc
