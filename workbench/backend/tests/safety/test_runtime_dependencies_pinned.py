"""Runtime-import safety guard.

B027 F003 fix-round 1 root cause: ``workbench_api/data/tiingo_loader.py``
landed a top-level ``import httpx`` in F001, but ``httpx`` was only
declared under ``[project.optional-dependencies].dev`` at the time.
Local dev / CI installed with the ``dev`` extra and all 273 backend
tests passed; the production wheel install (which resolves only
``[project].dependencies``) blew up on the first real ``health_check``
with ``ModuleNotFoundError: No module named 'httpx'``.

This guard greps every ``workbench_api/`` source file for top-level
``import X`` / ``from X import ...`` statements that hit a third-party
package, then asserts each one is declared in the runtime dependency
set of ``pyproject.toml``. That keeps a future ``import requests``
(or any other dev-only library) from sneaking into the runtime path
without showing up here first.

The check operates on the file text rather than ``ast``-level imports
because lazy imports inside functions are allowed (production runtime
may not need them at module load), and the simpler regex over the
top-of-file lines catches the regression class we actually care about.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = BACKEND_ROOT / "pyproject.toml"
SOURCE_ROOT = BACKEND_ROOT / "workbench_api"


# Stdlib + first-party + bundled extras that never need a runtime
# dependency entry. Keep the set small and explicit — a missing entry
# here should fail the test loudly so the author has to declare the
# package they imported.
_STDLIB_MODULE_NAMES: frozenset[str] = frozenset(sys.stdlib_module_names)
_FIRST_PARTY: frozenset[str] = frozenset({"workbench_api"})
_EXEMPT: frozenset[str] = frozenset(
    {
        # Transitive deps that fastapi / starlette / uvicorn / sqlalchemy
        # pin themselves; flagging them here would force redundant
        # entries in pyproject.toml. The runtime contract is satisfied
        # because the corresponding direct dep declares them.
        "starlette",  # fastapi
        "anyio",  # starlette / fastapi
        "jose",  # python-jose
        # ``typing_extensions`` is pinned by pydantic on every supported
        # python version we run (it stays bundled even on 3.11+ where
        # ``typing.TypedDict`` etc. are available, because pydantic v2
        # uses backports of newer features).
        "typing_extensions",
    }
)


def _runtime_packages(pyproject_text: str) -> set[str]:
    """Extract the ``[project].dependencies`` package names.

    The values look like ``fastapi>=0.115,<0.116`` /
    ``python-jose[cryptography]>=3.3,<4`` — strip the version and
    extras suffixes so the bare package name remains.
    """

    data = tomllib.loads(pyproject_text)
    raw = data.get("project", {}).get("dependencies", [])
    names: set[str] = set()
    for entry in raw:
        # Drop bracket extras + version operators.
        name = entry.split("[", 1)[0]
        for token in (">=", "<=", "==", "<", ">", "~=", "!="):
            name = name.split(token, 1)[0]
        names.add(name.strip().lower().replace("_", "-"))
    return names


def _top_level_imports(py_path: Path) -> set[str]:
    """Return the set of top-level module names imported at module load."""

    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".", 1)[0])
    return out


def test_runtime_imports_are_declared_dependencies() -> None:
    runtime = _runtime_packages(PYPROJECT.read_text(encoding="utf-8"))
    # Normalise the same way as _runtime_packages did.
    runtime_normalised = {name.replace("-", "_") for name in runtime} | runtime

    offending: dict[str, set[str]] = {}
    for path in SOURCE_ROOT.rglob("*.py"):
        for module in _top_level_imports(path):
            module_lower = module.lower()
            if module_lower in _STDLIB_MODULE_NAMES:
                continue
            if module_lower in _FIRST_PARTY:
                continue
            if module_lower in _EXEMPT:
                continue
            if (
                module_lower in runtime_normalised
                or module_lower.replace("_", "-") in runtime
            ):
                continue
            offending.setdefault(module, set()).add(
                str(path.relative_to(BACKEND_ROOT))
            )

    if offending:
        msg = "Top-level imports not declared in [project].dependencies:\n" + "\n".join(
            f"  {mod} (used in {sorted(paths)})"
            for mod, paths in sorted(offending.items())
        )
        raise AssertionError(msg)


def test_httpx_is_runtime_not_dev_extra() -> None:
    """Pin the specific regression that motivated this guard.

    Even if a contributor restructures pyproject.toml in a future
    refactor, ``httpx`` must stay in the runtime dependency set —
    otherwise the Tiingo loader cannot import on the production VM
    (B027 F003 fix-round 1 root cause).
    """

    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    runtime_entries = data.get("project", {}).get("dependencies", [])
    has_httpx = any(entry.split("[", 1)[0].split(">", 1)[0].strip() == "httpx"
                    for entry in runtime_entries)
    assert has_httpx, (
        "httpx must be a runtime dependency (not just a dev extra); "
        "workbench_api/data/tiingo_loader.py imports it at module "
        "load and the production wheel install resolves only "
        "[project].dependencies."
    )
