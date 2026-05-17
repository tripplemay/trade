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

    return ReportDetail(
        slug=_slug_from_name(path.name),
        title=_slug_from_name(path.name).replace("-", " ").strip(),
        date=_date_from_name(path.name, path.stat().st_mtime),
        batch=_batch_from_name(path.name),
        kind=_kind_from_name(path.name),
        body_markdown=body,
        tables=tables,
        cross_links=cross_links,
    )


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
