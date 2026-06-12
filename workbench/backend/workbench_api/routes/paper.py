"""Router for ``/api/paper/*`` (B056 F003).

Auth-gated, same-origin. The paper-trading (forward-simulation) page:

* ``GET /paper/strategies`` — selectable strategies + which have an account.
* ``GET /paper/{strategy_id}`` — the full 6-section view (summary / NAV curve +
  SPY / per-asset P&L / drift / rebalance log / settings state).
* ``POST /paper/activate`` — start a forward simulation for a strategy.

Self-contained per §12.10: reads the paper tables + recommendation_snapshot +
price_snapshot and the shared mark-to-market helpers — never imports ``trade``.
The forward NAV / P&L are REAL already-computed values, never a prediction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.paper.service import PaperAccountExistsError
from workbench_api.paper.targets import PAPER_STRATEGIES
from workbench_api.schemas.paper import (
    ActivatePaperRequest,
    ActivatePaperResponse,
    PaperStrategiesResponse,
    PaperView,
)
from workbench_api.services.paper import (
    activate_view_account,
    build_paper_view,
    list_paper_strategies,
)

router = APIRouter(tags=["paper"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]

_KNOWN_STRATEGY_IDS = frozenset(sid for sid, _ in PAPER_STRATEGIES)


@router.get("/paper/strategies", response_model=PaperStrategiesResponse)
def get_paper_strategies_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> PaperStrategiesResponse:
    return list_paper_strategies(session)


@router.get("/paper/{strategy_id}", response_model=PaperView)
def get_paper_view_route(
    strategy_id: str,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> PaperView:
    return build_paper_view(session, strategy_id)


@router.post("/paper/activate", response_model=ActivatePaperResponse)
def activate_paper_route(
    request: ActivatePaperRequest,
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> ActivatePaperResponse:
    if request.strategy_id not in _KNOWN_STRATEGY_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown paper strategy '{request.strategy_id}'",
        )
    now = datetime.now(UTC)
    try:
        _account, positions = activate_view_account(
            session,
            strategy_id=request.strategy_id,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            on_date=now.date(),
            now=now,
        )
        session.commit()
    except PaperAccountExistsError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"paper account already active for '{request.strategy_id}'",
        ) from exc
    return ActivatePaperResponse(
        strategy_id=request.strategy_id, activated=True, positions=positions
    )
