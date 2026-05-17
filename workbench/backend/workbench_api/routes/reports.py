"""Router for ``/api/reports`` (F009 stubs) + ``/api/docs/{path}`` (F007 body)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from workbench_api.auth.dependency import require_authenticated_user
from workbench_api.auth.jwt_validator import AuthenticatedUser
from workbench_api.routes._stub import not_implemented
from workbench_api.schemas.reports import DocsResponse, ReportDetail, ReportListResponse
from workbench_api.services.docs import (
    DocsNotFoundError,
    InvalidDocsPathError,
    load_doc,
)

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
# B022 F007 ships the sanitiser so the Strategies page's spec/code buttons
# resolve; F009 reuses this endpoint for the Reports page's body rendering.
@router.get("/docs/{file_path:path}", response_model=DocsResponse)
def get_docs(file_path: str, _user: AuthenticatedUserDep) -> DocsResponse:
    try:
        return load_doc(file_path)
    except InvalidDocsPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocsNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
