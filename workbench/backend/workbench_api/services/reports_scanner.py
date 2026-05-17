"""Filesystem scanner for ``docs/test-reports/`` (and friends).

B022 F006 Dashboard surfaces the most-recent reports inline; F009 will
also need this for the Reports page. Keeping the scanner pure (no DB,
no HTTP) makes it cheap to unit-test and easy to compose with the route
handler that owns the auth / response-shaping boundary.

Production VMs may not stage the docs/ tree in the release dir; the
scanner gracefully returns an empty list when the configured directory
does not exist, so the Dashboard's "no recent reports" empty state lights
up rather than the endpoint 500'ing.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

# Test reports are named like
#   B019-retune-recommendations-signoff-2026-05-15.md
# The date suffix is the authoritative "when filed" — file mtime can lag
# (mass rename, rebase, etc.). Pulled out via regex so we still surface a
# report even if the filename doesn't follow the convention (status falls
# back to mtime in that case).
DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
BATCH_IN_NAME_RE = re.compile(r"^(B\d{3})")


def _slug_from_name(name: str) -> str:
    # Drop the trailing `.md` and the date suffix so deep-links stay
    # stable when a report is re-stamped with a new date.
    stem = name[:-3] if name.endswith(".md") else name
    return DATE_IN_NAME_RE.sub("", stem).strip("-")


def _date_from_name(name: str, fallback_mtime: float) -> str:
    match = DATE_IN_NAME_RE.search(name)
    if match:
        return match.group(1)
    dt = datetime.fromtimestamp(fallback_mtime, tz=UTC)
    return dt.strftime("%Y-%m-%d")


def _batch_from_name(name: str) -> str:
    match = BATCH_IN_NAME_RE.match(name)
    return match.group(1) if match else ""


def _kind_from_name(name: str) -> str:
    lowered = name.lower()
    if "signoff" in lowered:
        return "signoff"
    if "sweep" in lowered:
        return "sweep"
    if "review" in lowered or "audit" in lowered:
        return "review"
    if "research" in lowered:
        return "research"
    return "report"


def recent_reports(
    reports_dir: Path,
    *,
    limit: int = 10,
    glob: str = "*.md",
) -> list[dict[str, str]]:
    """Return up to ``limit`` recent reports as plain dicts.

    Each dict carries the field set the DashboardResponse / ReportListResponse
    schemas expect: ``id`` (slug), ``title``, ``date``, ``status``, ``path``.
    The caller adapts them into Pydantic models.

    ``reports_dir`` not existing is a valid empty state; nothing raises.
    """

    if not reports_dir.exists() or not reports_dir.is_dir():
        return []

    candidates: list[tuple[Path, float]] = []
    for entry in reports_dir.glob(glob):
        if not entry.is_file():
            continue
        candidates.append((entry, entry.stat().st_mtime))
    # Sort by the date in the filename when present, falling back to mtime
    # so re-stamped or freshly-touched files still float to the top.
    candidates.sort(
        key=lambda pair: (_date_from_name(pair[0].name, pair[1]), pair[1]),
        reverse=True,
    )

    out: list[dict[str, str]] = []
    for path, mtime in candidates[:limit]:
        name = path.name
        out.append(
            {
                "id": _slug_from_name(name),
                "title": _slug_from_name(name).replace("-", " ").strip(),
                "date": _date_from_name(name, mtime),
                # Status is best-effort metadata. Real status (PASS / FAIL /
                # PARTIAL) lives inside the report body; F009 will parse it.
                "status": _kind_from_name(name),
                # `path` is the relative path so the frontend can hand it to
                # /api/docs/{path} (F009) without leaking host details.
                "path": str(path.as_posix()),
            }
        )
    return out
