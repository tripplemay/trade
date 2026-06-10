"""B053 F003 — forbid ``date.today()`` anywhere in ``workbench_api``.

``date.today()`` reads the **server's local timezone**. The production VM runs
UTC, so the value happens to be correct today — but that is an implicit,
undocumented assumption that silently breaks (off-by-one day) if the server TZ
ever changes. B053 replaced every call with the explicit ``datetime.now(UTC).date()``.

This AST guard pins that decision: it fails if any production module reintroduces
a ``date.today()`` call, so the next contributor uses the explicit UTC form. It
matches only the *call* ``date.today()`` (an ``Attribute`` ``today`` on a ``Name``
``date``); docstrings / comments mentioning the API are not flagged. Tests are
out of scope — only ``workbench_api`` is scanned.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"


def _date_today_calls(py_path: Path) -> list[int]:
    """Line numbers of any ``date.today()`` call in the module."""

    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    hits: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "today"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "date"
        ):
            hits.append(node.lineno)
    return hits


def test_no_date_today_in_workbench_api() -> None:
    offenders: list[str] = []
    for py_path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for lineno in _date_today_calls(py_path):
            offenders.append(f"{py_path.relative_to(BACKEND_ROOT)}:{lineno}")
    assert not offenders, (
        "date.today() uses the server's local timezone (implicit-UTC assumption). "
        "Use datetime.now(UTC).date() instead. Offenders:\n  "
        + "\n  ".join(offenders)
    )
