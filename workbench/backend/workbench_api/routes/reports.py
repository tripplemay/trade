"""Router for ``/api/reports`` (F009 body) + ``/api/docs/{path}`` (F007 body)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.i18n import t
from workbench_api.schemas.reports import DocsResponse, ReportDetail, ReportListResponse
from workbench_api.services.dashboard import _resolve_reports_dir
from workbench_api.services.docs import (
    DocsNotFoundError,
    InvalidDocsPathError,
    load_doc,
)
from workbench_api.services.reports import (
    ReportNotFoundError,
    get_report,
    list_reports,
)
from workbench_api.settings import Settings, get_settings

router = APIRouter(tags=["reports"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _reports_root(settings: Settings) -> Path:
    return _resolve_reports_dir(settings.WORKBENCH_REPORTS_DIR)


@router.get("/reports", response_model=ReportListResponse)
def list_reports_route(
    _user: AuthenticatedUserDep,
    settings: SettingsDep,
) -> ReportListResponse:
    return list_reports(_reports_root(settings))


@router.get("/reports/{slug}", response_model=ReportDetail)
def get_report_route(
    slug: str,
    _user: AuthenticatedUserDep,
    settings: SettingsDep,
) -> ReportDetail:
    try:
        return get_report(slug, _reports_root(settings))
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("report.not_found", detail=str(exc)),
        ) from exc


# /api/docs/{path:path} captures nested repo paths (e.g. docs/specs/B019.md).
# B022 F007 ships the sanitiser so the Strategies page's spec/code buttons
# resolve; F009 also lets the docs viewer page consume it.
@router.get("/docs/{file_path:path}", response_model=DocsResponse)
def get_docs(file_path: str, _user: AuthenticatedUserDep) -> DocsResponse:
    try:
        return load_doc(file_path)
    except InvalidDocsPathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("docs.invalid_path", detail=str(exc)),
        ) from exc
    except DocsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("docs.not_found", detail=str(exc)),
        ) from exc
