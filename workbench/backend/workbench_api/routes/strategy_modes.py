"""Router for ``GET /api/strategy-modes`` — B057 F005 mode selector data."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.schemas.strategy_modes import StrategyModesResponse
from workbench_api.strategy_modes.service import list_strategy_modes

router = APIRouter(prefix="/strategy-modes", tags=["strategy-modes"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("", response_model=StrategyModesResponse)
def list_strategy_modes_route(_user: AuthenticatedUserDep) -> StrategyModesResponse:
    """Enumerate the platform's strategy modes (Master + regime + future).

    The frontend mode selector reads this; research-state modes are marked so
    the surface can show 研究态 / 前向验证中 honestly (B057 §1 capability ≠ funding).
    """

    return list_strategy_modes()
