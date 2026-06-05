"""Router for ``/api/advisor`` (B036 F003).

Auth-gated, same-origin, read-only. Returns the latest precomputed AI
advice per sleeve. Pure structured data + citations; the advice text is
generated upstream (precompute) and gated by the red-team safety eval —
this route never calls the model."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.advisor import AdvisorResponse
from workbench_api.services.advisor import get_advisor

router = APIRouter(tags=["advisor"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/advisor", response_model=AdvisorResponse)
def get_advisor_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> AdvisorResponse:
    return get_advisor(session)
