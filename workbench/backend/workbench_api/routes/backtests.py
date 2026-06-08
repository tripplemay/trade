"""Router for ``/api/backtests`` — B047 async (enqueue + poll).

``POST /run`` enqueues a backtest_run and returns ``202`` with a ``run_id``;
the frontend polls ``GET /{run_id}`` until ``status`` is ``done`` / ``error``.
The request path never imports ``trade`` (§12.10.2) — the worker runs the real
engine off-path.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.i18n import t
from workbench_api.schemas.backtests import (
    BacktestDataRangeResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from workbench_api.services.backtests import (
    UnknownStrategyError,
    get_backtest,
    get_data_range,
    run_backtest,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.post("/run", response_model=BacktestRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_backtest_route(
    body: BacktestRunRequest,
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> BacktestRunResponse:
    try:
        return run_backtest(session, body)
    except UnknownStrategyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("backtest.unknown_strategy", id=str(exc)),
        ) from exc


@router.get("/data-range", response_model=BacktestDataRangeResponse)
def get_data_range_route(
    session: SessionDep,
    _user: AuthenticatedUserDep,
) -> BacktestDataRangeResponse:
    """Expose the real data-coverage window (read-only; never imports ``trade``,
    §12.10.2). Registered before ``/{run_id}`` so the literal path is not
    shadowed by the dynamic segment."""

    return get_data_range(session)


@router.get("/{run_id}", response_model=BacktestRunResponse)
def get_backtest_route(
    run_id: str, session: SessionDep, _user: AuthenticatedUserDep
) -> BacktestRunResponse:
    result = get_backtest(session, run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("backtest.run_not_found", run_id=run_id),
        )
    return result
