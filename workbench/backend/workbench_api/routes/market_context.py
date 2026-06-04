"""Router for ``/api/market-context`` (B035 F003).

Auth-gated, same-origin, read-only. Returns the latest value per
market-context series as pure structured data (no AI text)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.market_context import MarketContextResponse
from workbench_api.services.market_context import get_market_context

router = APIRouter(tags=["market-context"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/market-context", response_model=MarketContextResponse)
def get_market_context_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> MarketContextResponse:
    return get_market_context(session)
