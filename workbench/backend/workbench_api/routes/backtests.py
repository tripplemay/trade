"""Router for ``/api/backtests`` — F002 schema, F008 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.schemas.backtests import BacktestRunRequest, BacktestRunResponse
from workbench_api.services.backtests import (
    UnknownStrategyError,
    get_backtest,
    run_backtest,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest_route(
    body: BacktestRunRequest,
    _user: AuthenticatedUserDep,
) -> BacktestRunResponse:
    try:
        return run_backtest(body)
    except UnknownStrategyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown strategy id: {exc}",
        ) from exc


@router.get("/{run_id}", response_model=BacktestRunResponse)
def get_backtest_route(run_id: str, _user: AuthenticatedUserDep) -> BacktestRunResponse:
    result = get_backtest(run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached backtest with run_id={run_id}",
        )
    return result
