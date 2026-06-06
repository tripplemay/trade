"""Reports list + detail service (B022 F009).

Lists reports by reusing the F006 ``reports_scanner`` and re-shaping
each hit into a ``ReportSummary``. Detail fetches one markdown file
by slug match, returns the raw body, plus a structured table extract
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
from pathlib import Path

from workbench_api.schemas.reports import (
    ReportDetail,
    ReportListResponse,
    ReportMetrics,
    ReportSummary,
    ReportTable,
)
from workbench_api.services.reports_scanner import (
    _batch_from_name,
    _date_from_name,
    _kind_from_name,
    _slug_from_name,
    recent_reports,
)


class ReportNotFoundError(LookupError):
    """No markdown file matched the supplied slug."""


# Match a markdown link target that points at a repo-tracked doc path.
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def list_reports(reports_dir: Path, *, limit: int = 50) -> ReportListResponse:
    """List the most recent reports under ``reports_dir`` as schema rows."""

    scanned = recent_reports(reports_dir, limit=limit)
    rows = [
        ReportSummary(
            slug=entry["id"],
            title=entry["title"],
            date=entry["date"],
            batch=_batch_from_name(Path(entry["path"]).name),
            kind=entry["status"],
            path=entry["path"],
        )
        for entry in scanned
    ]
    return ReportListResponse(reports=rows)


def get_report(slug: str, reports_dir: Path) -> ReportDetail:
    """Resolve ``slug`` to a markdown file and parse it into a ReportDetail.

    Raises ``ReportNotFoundError`` when no file matches.
    """

    if not reports_dir.is_dir():
        raise ReportNotFoundError(f"reports_dir does not exist: {reports_dir}")

    # Two acceptable match shapes:
    #   1. Exact slug match (after stripping date + .md)
    #   2. Substring match (slug embedded in filename) — handy when the
    #      caller used a partial like "B019-retune"
    candidates: list[Path] = []
    for entry in reports_dir.glob("*.md"):
        if _slug_from_name(entry.name) == slug:
            candidates = [entry]
            break
        if slug in entry.name:
            candidates.append(entry)

    if not candidates:
        raise ReportNotFoundError(f"No report file matches slug={slug!r}")
    path = candidates[0]
    body = path.read_text(encoding="utf-8", errors="replace")

    tables = _extract_tables(body)
    cross_links = _extract_cross_links(body)
    metrics = _parse_metrics(tables)

    return ReportDetail(
        slug=_slug_from_name(path.name),
        title=_slug_from_name(path.name).replace("-", " ").strip(),
        date=_date_from_name(path.name, path.stat().st_mtime),
        batch=_batch_from_name(path.name),
        kind=_kind_from_name(path.name),
        body_markdown=body,
        tables=tables,
        cross_links=cross_links,
        metrics=metrics,
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
