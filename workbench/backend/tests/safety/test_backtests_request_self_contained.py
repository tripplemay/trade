"""B047 F001 — backtests request-path §12.10.2 self-containment.

The Option A async architecture keeps the request path off the heavy ``trade``
stack: ``POST /api/backtests/run`` only enqueues a ``backtest_run`` row and
returns a ``run_id``; ``GET /api/backtests/{run_id}`` only reads that table.
Only the async **worker** (``workbench_api/backtests/worker.py``, B047 F002)
and the **canonical** report job (``…/backtests/canonical.py``, B047 F004) may
import ``trade`` — they run the real Master Portfolio backtest off the request
path.

Contract:
- ``routes/backtests.py`` + ``services/backtests.py`` must NEVER import
  ``trade`` (a regression would couple the auth-gated read path to the scoring
  stack — exactly the §12.10.2 class this guard prevents; it would pass locally
  + in CI where trade is installed).
- The worker / canonical modules (when present) ARE the allowed importers.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"

REQUEST_PATH_MODULES = (
    PACKAGE_ROOT / "routes" / "backtests.py",
    PACKAGE_ROOT / "services" / "backtests.py",
)
# Allowlisted off-request-path importers (created in F002 / F004).
WORKER_MODULE = PACKAGE_ROOT / "backtests" / "worker.py"
CANONICAL_MODULE = PACKAGE_ROOT / "backtests" / "canonical.py"


def _imports_trade(py_path: Path) -> bool:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "trade" or alias.name.startswith("trade."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "trade" or module.startswith("trade.")):
                return True
    return False


def test_backtests_request_path_does_not_import_trade() -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in REQUEST_PATH_MODULES
        if path.is_file() and _imports_trade(path)
    )
    assert not offenders, (
        "§12.10.2 violated: the backtests request path imports the trade "
        f"package {offenders}. Enqueue a backtest_run row + read it from the DB "
        "instead — only workbench_api/backtests/{worker,canonical}.py may "
        "import trade."
    )


def _imports_worker(py_path: Path) -> bool:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "workbench_api.backtests.worker"
        ):
            return True
    return False


def test_worker_imports_trade_when_present() -> None:
    """The worker IS the allowed trade importer (the real engine). Pin it once
    it exists so a refactor that severs the real-engine import is caught."""

    if WORKER_MODULE.is_file():
        assert _imports_trade(WORKER_MODULE), (
            "workbench_api/backtests/worker.py drives the real engine and must "
            "import trade; if the engine moved, update this allowlist + guard"
        )


def test_canonical_drives_the_real_engine_when_present() -> None:
    """The canonical job runs the real engine — directly importing trade or via
    the worker (which does). Pin the positive contract once it exists."""

    if CANONICAL_MODULE.is_file():
        assert _imports_trade(CANONICAL_MODULE) or _imports_worker(CANONICAL_MODULE), (
            "workbench_api/backtests/canonical.py must drive the real engine "
            "(import trade, or the worker that does)"
        )
