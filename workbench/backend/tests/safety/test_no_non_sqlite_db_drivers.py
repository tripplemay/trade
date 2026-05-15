"""Workbench is SQLite-only by design (B021 spec §Out of Scope).

A drive-by `import psycopg2` would expand the operations surface from a
single SQLite file to a network-attached database without anyone noticing
in code review. This regression scans every backend Python file for an
import of the forbidden DB driver modules.

The file is structured exactly like ``test_no_broker_sdk_imports.py`` so
the two safety guards rot in lockstep when the surface evolves.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_DB_MODULES: tuple[str, ...] = (
    "psycopg2",
    "psycopg",  # the v3 rewrite — same network-DB problem
    "mysqlclient",
    "MySQLdb",
    "pymysql",
    "pymongo",
    "motor",  # async mongo client
    "cx_Oracle",
    "snowflake.connector",
    "google.cloud.sql",
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "node_modules",
    }
)

IMPORT_RE = re.compile(
    rf"^\s*(?:from|import)\s+({'|'.join(re.escape(m) for m in FORBIDDEN_DB_MODULES)})\b",
    re.MULTILINE,
)


def _iter_python_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def test_no_non_sqlite_db_drivers_imported() -> None:
    offenders: list[tuple[str, str, int]] = []
    for source in _iter_python_sources(BACKEND_ROOT):
        text = source.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            offenders.append((str(source.relative_to(BACKEND_ROOT)), match.group(1), line_number))

    assert offenders == [], (
        "Forbidden DB driver import detected — workbench backend must remain "
        f"SQLite-only (B021 spec §Out of Scope). Hits: {offenders}"
    )
