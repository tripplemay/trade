"""B033 permanent product boundary **(q)** — news ingest stays
production-disabled by default (no cron / no APScheduler / no
scheduled FastAPI job).

The B033 batch only ships a manual-trigger CLI
(``python -m workbench_api.news.cli fetch``). A future batch that
wants to add scheduling must first add a permanent-boundary
relaxation note in ``framework/proposed-learnings.md`` and an
explicit edit to this guard.

The guard makes two checks:

1. ``workbench_api/news/scheduler.py`` does not exist. A file with
   this name would be the obvious place to wire APScheduler /
   ``schedule`` / ``aiocron`` callbacks, so we block it outright.

2. No module under ``workbench_api/news/`` imports ``apscheduler``,
   ``aiocron``, ``schedule``, or any submodule of those packages.
   Top-level imports are walked via ``ast`` for deterministic
   inspection — same shape as
   :func:`tests.safety.test_runtime_dependencies_pinned._top_level_imports`.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
NEWS_PACKAGE = BACKEND_ROOT / "workbench_api" / "news"

_FORBIDDEN_SCHEDULER_MODULES: frozenset[str] = frozenset({
    "apscheduler",
    "aiocron",
    "schedule",
})


def _top_level_imports(py_path: Path) -> set[str]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".", 1)[0])
    return out


def test_no_scheduler_module_exists() -> None:
    """No ``workbench_api/news/scheduler.py`` — permanent product boundary (q)."""

    scheduler_path = NEWS_PACKAGE / "scheduler.py"
    assert not scheduler_path.exists(), (
        f"Permanent product boundary (q) violated: {scheduler_path.relative_to(BACKEND_ROOT)} "
        "exists. The B033 batch ships only a manual-trigger CLI; a scheduler "
        "module requires a permanent-boundary relaxation note in "
        "framework/proposed-learnings.md before merge. See spec §3 boundary (q)."
    )


def test_no_scheduler_imports_under_workbench_news() -> None:
    """No file under ``workbench_api/news/`` imports a scheduler library."""

    offending: dict[str, list[str]] = {}
    for path in NEWS_PACKAGE.rglob("*.py"):
        imports = _top_level_imports(path)
        hits = sorted(imports & _FORBIDDEN_SCHEDULER_MODULES)
        if hits:
            offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "Permanent product boundary (q) violated: scheduler libraries imported "
        f"under workbench_api/news/: {offending}. Remove the import or add a "
        "permanent-boundary relaxation note in framework/proposed-learnings.md "
        "before merge. See spec §3 boundary (q)."
    )
