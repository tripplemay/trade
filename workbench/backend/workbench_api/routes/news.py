"""Router for ``/api/news/latest`` (B038 F001).

Auth-gated, same-origin, read-only. Returns the newest-first global
market-news feed as pure structured metadata (no AI text). Backs the
Home "Today's market news" section (personas §2 mockup)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.db.session import SessionDep
from workbench_api.schemas.news import LatestNewsResponse
from workbench_api.services.news import build_latest_news

router = APIRouter(tags=["news"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/news/latest", response_model=LatestNewsResponse)
def get_latest_news_route(
    _user: AuthenticatedUserDep,
    session: SessionDep,
) -> LatestNewsResponse:
    return build_latest_news(session)
