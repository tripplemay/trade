"""Stub router for ``/api/strategies`` — F002 schema, F007 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.strategies import StrategyDetail, StrategyListResponse

router = APIRouter(prefix="/strategies", tags=["strategies"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=StrategyListResponse)
def list_strategies(_user: AuthenticatedUserDep) -> StrategyListResponse:
    raise not_implemented("F007")


@router.get("/{strategy_id}", response_model=StrategyDetail)
def get_strategy(strategy_id: str, _user: AuthenticatedUserDep) -> StrategyDetail:
    del strategy_id
    raise not_implemented("F007")
