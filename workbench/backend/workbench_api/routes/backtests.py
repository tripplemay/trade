"""Stub router for ``/api/backtests`` — F002 schema, F008 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.backtests import BacktestRunRequest, BacktestRunResponse

router = APIRouter(prefix="/backtests", tags=["backtests"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(body: BacktestRunRequest, _user: AuthenticatedUserDep) -> BacktestRunResponse:
    del body
    raise not_implemented("F008")


@router.get("/{run_id}", response_model=BacktestRunResponse)
def get_backtest(run_id: str, _user: AuthenticatedUserDep) -> BacktestRunResponse:
    del run_id
    raise not_implemented("F008")
