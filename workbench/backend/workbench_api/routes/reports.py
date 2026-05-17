"""Stub router for ``/api/reports`` + ``/api/docs/{path}`` — F002 schema, F009 body."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.reports import DocsResponse, ReportDetail, ReportListResponse

router = APIRouter(tags=["reports"])

AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get("/reports", response_model=ReportListResponse)
def list_reports(_user: AuthenticatedUserDep) -> ReportListResponse:
    raise not_implemented("F009")


@router.get("/reports/{slug}", response_model=ReportDetail)
def get_report(slug: str, _user: AuthenticatedUserDep) -> ReportDetail:
    del slug
    raise not_implemented("F009")


# /api/docs/{path:path} captures nested repo paths (e.g. docs/specs/B019.md).
# Per spec the handler sanitises path traversal; the stub returns 501 so the
# attack surface is not live until F009 ships the sanitiser.
@router.get("/docs/{file_path:path}", response_model=DocsResponse)
def get_docs(file_path: str, _user: AuthenticatedUserDep) -> DocsResponse:
    del file_path
    raise not_implemented("F009")
