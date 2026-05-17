"""Router for ``GET /api/dashboard`` — F002 schema, F006 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.dashboard import DashboardResponse
from workbench_api.services.dashboard import build_dashboard
from workbench_api.settings import Settings, get_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> DashboardResponse:
    """B022 F006 vertical slice — see services.dashboard for the field-by-field
    aggregation rationale. The route stays thin so it can be exercised
    end-to-end via httpx without monkeypatching anything beyond the auth
    + settings dependency overrides.
    """

    return build_dashboard(session, settings)
