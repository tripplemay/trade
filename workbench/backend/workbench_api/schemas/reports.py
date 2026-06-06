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


class ReportMetrics(BaseModel):
    """B040 F001 — headline backtest metrics parsed from a report's metrics
    table, for the Robinhood-style big-number card.

    Every field is optional: a report may omit a metric, the table may be
    absent entirely (then ``ReportDetail.metrics`` is ``None``), or a cell
    may be unparseable. ``calmar`` is derived (CAGR / |max_drawdown|) when not
    present as its own column. These are **historical backtest statistics**,
    never a forward return prediction (positioning §1.1)."""

    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    cagr: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    turnover: float | None = None


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
    metrics: ReportMetrics | None = Field(
        default=None,
        description=(
            "Headline backtest metrics parsed from the report's metrics table "
            "(Robinhood-style big-number card). None when no metrics table is "
            "recognised — the page then renders the markdown only."
        ),
    )


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]


class DocsResponse(BaseModel):
    """GET /api/docs/{path} — shared resolver for spec/code/report deep links."""

    path: str
    content_type: str = Field(description="'markdown' / 'python' / 'json' / 'text'.")
    body: str = Field(description="Raw file contents (markdown rendered client-side).")
