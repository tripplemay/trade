"""Schemas for the reports / docs endpoints (F009)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSummary(BaseModel):
    """Row in the report-list view."""

    slug: str = Field(description="Stable identifier; deep-linked at /reports/<slug>.")
    title: str
    date: str = Field(description="ISO-8601 date the report was filed.")
    batch: str = Field(description="Batch label, e.g. 'B019'.")
    kind: str = Field(description="'signoff' / 'sweep' / 'research' / 'adr'.")
    path: str = Field(description="Repo-relative path under docs/test-reports/ or docs/research/.")


class ReportTable(BaseModel):
    """Markdown table extracted for AG Grid re-rendering (>= 10 rows)."""

    caption: str | None = None
    columns: list[str]
    rows: list[list[str]]


class ReportDetail(BaseModel):
    """GET /api/reports/{slug} payload."""

    slug: str
    title: str
    date: str
    batch: str
    kind: str
    body_markdown: str = Field(description="Original markdown source for react-markdown.")
    tables: list[ReportTable] = Field(
        default_factory=list,
        description="Tables >= 10 rows pre-extracted so the page can swap them for AG Grid.",
    )
    cross_links: list[str] = Field(
        default_factory=list,
        description="Internal repo paths the report references (resolved to /reports/* / /docs/*).",
    )


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]


class DocsResponse(BaseModel):
    """GET /api/docs/{path} — shared resolver for spec/code/report deep links."""

    path: str
    content_type: str = Field(description="'markdown' / 'python' / 'json' / 'text'.")
    body: str = Field(description="Raw file contents (markdown rendered client-side).")
