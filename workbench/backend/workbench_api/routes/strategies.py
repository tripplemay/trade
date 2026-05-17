"""Router for ``/api/strategies`` — F002 schema, F007 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.schemas.strategies import StrategyDetail, StrategyListResponse
from workbench_api.services.strategies import get_strategy, list_strategies

router = APIRouter(prefix="/strategies", tags=["strategies"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=StrategyListResponse)
def list_strategies_route(_user: AuthenticatedUserDep) -> StrategyListResponse:
    return list_strategies()


@router.get("/{strategy_id}", response_model=StrategyDetail)
def get_strategy_route(strategy_id: str, _user: AuthenticatedUserDep) -> StrategyDetail:
    detail = get_strategy(strategy_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown strategy id: {strategy_id}",
        )
    return detail
