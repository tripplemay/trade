"""Router for ``/api/home`` (B037 F001).

Auth-gated, same-origin, read-only. Returns the daily-engagement Home
payload — NAV + mark-to-market Day P&L + per-sleeve breakdown. Marks the
latest account positions to market using the ``price_snapshot`` table;
it never touches an execution surface (no-execution boundary)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.home import HomeResponse
from workbench_api.services.home import build_home
from workbench_api.settings import Settings, get_settings

router = APIRouter(tags=["home"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/home", response_model=HomeResponse)
def get_home_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> HomeResponse:
    return build_home(session, settings)
