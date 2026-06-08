"""Reports list + detail service (B022 F009; B047 F004 — DB-backed).

Lists the canonical INVESTMENT reports from the ``investment_report`` table
(B047 F004 cut over from the F006 filesystem ``reports_scanner``, now removed),
re-shaping each row into a ``ReportSummary``. Detail fetches one report by slug,
returns the raw body, plus a structured table extract
and cross-link list so the frontend can re-render heavy tables in
AG Grid and rewrite ``docs/specs/...`` / ``docs/test-reports/...``
cross-links into in-app routes.

Markdown table extraction is GFM-style regex: a header row (``|...|``),
a separator (``|---|...``), and N body rows until the first non-``|``
line. We snapshot all tables (not just the ``>= 10 row`` ones) so the
frontend can pick which to swap into AG Grid; backend stays simple.

Cross-link extraction pulls every ``[text](docs/...)`` link target so
the frontend can rewrite them on render without re-parsing markdown.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.repositories.investment_report import InvestmentReportRepository
from workbench_api.schemas.reports import (
    ReportDetail,
    ReportListResponse,
    ReportMetrics,
    ReportSummary,
    ReportTable,
)


class ReportNotFoundError(LookupError):
    """No markdown file matched the supplied slug."""


# Match a markdown link target that points at a repo-tracked doc path.
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def list_reports(session: Session) -> ReportListResponse:
    """List the canonical INVESTMENT reports (B047 F004).

    The user Reports page now surfaces real Master/sleeve backtest reports
    written by the canonical job (``kind='investment'``), NOT the development
    sign-offs under ``docs/test-reports/`` (those stay reachable via the
    /api/docs deep links, but are filtered out of the user Reports list)."""

    reports = InvestmentReportRepository(session).list_reports()
    rows = [
        ReportSummary(
            slug=report.slug,
            title=report.title,
            date=report.as_of_date.isoformat(),
            batch=report.strategy_id,
            kind=report.kind,
            path="",
        )
        for report in reports
    ]
    return ReportListResponse(reports=rows)


def get_report(session: str | Session, slug: str | None = None) -> ReportDetail:
    """Resolve ``slug`` to an investment report and shape it into a ReportDetail.

    Raises ``ReportNotFoundError`` when no report matches."""

    # Backwards-tolerant arg order during the F004 cut-over: callers pass
    # (session, slug). The legacy (slug, reports_dir) path is gone.
    if slug is None:
        raise ReportNotFoundError("slug is required")
    if not isinstance(session, Session):
        raise ReportNotFoundError("a DB session is required")

    report = InvestmentReportRepository(session).get_by_slug(slug)
    if report is None:
        raise ReportNotFoundError(f"No investment report matches slug={slug!r}")

    tables = _extract_tables(report.markdown)
    cross_links = _extract_cross_links(report.markdown)
    return ReportDetail(
        slug=report.slug,
        title=report.title,
        date=report.as_of_date.isoformat(),
        batch=report.strategy_id,
        kind=report.kind,
        body_markdown=report.markdown,
        tables=tables,
        cross_links=cross_links,
        metrics=_metrics_from_json(report.metrics_json),
    )


def _metrics_from_json(metrics_json: dict[str, Any] | None) -> ReportMetrics | None:
    """Map the worker's stored metrics dict to the ReportMetrics card shape.

    The engine emits cagr / sharpe / sortino / max_drawdown / turnover; calmar
    is derived (CAGR / |max_drawdown|), volatility is not computed → None."""

    if not metrics_json:
        return None
    cagr = metrics_json.get("cagr")
    max_dd = metrics_json.get("max_drawdown")
    calmar = (
        cagr / abs(max_dd)
        if isinstance(cagr, (int, float)) and isinstance(max_dd, (int, float)) and max_dd
        else None
    )
    return ReportMetrics(
        sharpe=metrics_json.get("sharpe"),
        sortino=metrics_json.get("sortino"),
        calmar=calmar,
        cagr=cagr,
        max_drawdown=max_dd,
        volatility=None,
        turnover=metrics_json.get("turnover"),
    )


# B040 F001 — column-name → ReportMetrics field, with synonyms. Column names
# are normalised (lower / spaces+dashes → underscore / trailing units stripped)
# before lookup. Many report tables use B016/B015-style headers
# (annualized_return / annualized_volatility / mdd …); map those to the
# canonical metric set.
_METRIC_COLUMN_SYNONYMS: dict[str, str] = {
    "sharpe": "sharpe",
    "sharpe_ratio": "sharpe",
    "sortino": "sortino",
    "sortino_ratio": "sortino",
    "calmar": "calmar",
    "calmar_ratio": "calmar",
    "cagr": "cagr",
    "annualized_return": "cagr",
    "annual_return": "cagr",
    "annualised_return": "cagr",
    "max_drawdown": "max_drawdown",
    "maximum_drawdown": "max_drawdown",
    "mdd": "max_drawdown",
    "volatility": "volatility",
    "annualized_volatility": "volatility",
    "annual_volatility": "volatility",
    "annualised_volatility": "volatility",
    "vol": "volatility",
    "turnover": "turnover",
}

# A table is treated as a metrics table only when it carries at least one of
# these "core" metric columns — guards against matching an unrelated table that
# merely happens to share a generic column like ``turnover``.
_CORE_METRIC_FIELDS: frozenset[str] = frozenset(
    {"sharpe", "sortino", "calmar", "cagr", "max_drawdown"}
)


def _normalise_column(name: str) -> str:
    """Lower-case, collapse separators to ``_``, drop a trailing ``(%)`` unit."""

    out = name.strip().lower()
    out = re.sub(r"\([^)]*\)", "", out)  # drop "(%)" / "(annualized)" units
    out = re.sub(r"[\s\-/]+", "_", out.strip())
    return out.strip("_")


def _parse_metric_float(cell: str) -> float | None:
    """Parse a metric cell to float; tolerate ``%``, thousands commas, and
    non-numeric placeholders (``N/A`` / ``—``) → ``None``."""

    text = cell.strip().replace(",", "")
    if not text:
        return None
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value / 100.0 if percent else value


def _column_field_map(columns: list[str]) -> dict[int, str]:
    """Return ``{column_index: metric_field}`` for recognised metric columns."""

    mapping: dict[int, str] = {}
    for idx, col in enumerate(columns):
        field = _METRIC_COLUMN_SYNONYMS.get(_normalise_column(col))
        # First win per field — if both ``cagr`` and ``annualized_return``
        # appear, keep the earliest column.
        if field is not None and field not in mapping.values():
            mapping[idx] = field
    return mapping


def _parse_metrics(tables: list[ReportTable]) -> ReportMetrics | None:
    """Parse headline metrics from the first recognised wide metrics table.

    Recognition (header-signature): the table's columns map to ≥2 known metric
    fields AND include at least one core field (sharpe / sortino / calmar /
    cagr / max_drawdown). Values come from the first data row. Calmar is
    derived from CAGR / |max_drawdown| when not present as its own column.
    Returns ``None`` when no table qualifies — the report renders markdown
    only (graceful; never raises). Real-corpus shape: B016/B015 wide tables
    (``| method | annualized_return | … | sharpe | max_drawdown | …|``)."""

    for table in tables:
        field_map = _column_field_map(table.columns)
        if len(field_map) < 2 or not (_CORE_METRIC_FIELDS & set(field_map.values())):
            continue
        if not table.rows:
            continue
        row = table.rows[0]
        values: dict[str, float | None] = {}
        for idx, field in field_map.items():
            values[field] = _parse_metric_float(row[idx]) if idx < len(row) else None

        # Derive Calmar when the table didn't carry it directly.
        if values.get("calmar") is None:
            cagr = values.get("cagr")
            mdd = values.get("max_drawdown")
            if cagr is not None and mdd is not None and mdd != 0:
                values["calmar"] = cagr / abs(mdd)

        return ReportMetrics(
            sharpe=values.get("sharpe"),
            sortino=values.get("sortino"),
            calmar=values.get("calmar"),
            cagr=values.get("cagr"),
            max_drawdown=values.get("max_drawdown"),
            volatility=values.get("volatility"),
            turnover=values.get("turnover"),
        )
    return None


def _extract_tables(body: str) -> list[ReportTable]:
    """Parse all GFM tables in ``body`` and return them as ReportTable.

    Caption support is minimal — if the line immediately above the
    table header begins with ``**`` or is a heading (``#``), use it as
    the caption. Otherwise caption is None.
    """

    lines = body.splitlines()
    tables: list[ReportTable] = []
    i = 0
    while i < len(lines):
        if not _TABLE_LINE_RE.match(lines[i]):
            i += 1
            continue
        if i + 1 >= len(lines) or not _SEPARATOR_RE.match(lines[i + 1]):
            i += 1
            continue
        header = _split_table_row(lines[i])
        rows: list[list[str]] = []
        j = i + 2
        while j < len(lines) and _TABLE_LINE_RE.match(lines[j]):
            rows.append(_split_table_row(lines[j]))
            j += 1
        caption = _caption_above(lines, i)
        tables.append(ReportTable(caption=caption, columns=header, rows=rows))
        i = j
    return tables


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _caption_above(lines: list[str], header_index: int) -> str | None:
    if header_index == 0:
        return None
    prev = lines[header_index - 1].strip()
    if not prev:
        return None
    if prev.startswith("**") and prev.endswith("**"):
        return prev.strip("*").strip()
    if prev.startswith("#"):
        return prev.lstrip("#").strip()
    return None


def _extract_cross_links(body: str) -> list[str]:
    """Return unique repo-relative paths referenced by markdown links."""

    seen: dict[str, None] = {}
    for match in _LINK_RE.finditer(body):
        target = match.group(1)
        if target.startswith("docs/") or target.startswith("trade/"):
            seen.setdefault(target, None)
    return list(seen.keys())
