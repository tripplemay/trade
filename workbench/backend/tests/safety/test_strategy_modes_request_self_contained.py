"""B057 F001 — strategy-mode layer §12.10 self-containment.

The regime precompute job (``strategy_modes/regime_precompute.py``) imports the
``trade`` package to run the real regime-adaptive scoring — exactly like the
Master recommendations precompute. The generic target layer and the mode
registry sit on the **request path** side (the recommendations read path, the
paper service and — B057 F004 — the execution chain call ``get_target`` /
``list_modes`` on auth-gated requests) and must NEVER import ``trade``: they read
the precomputed ``recommendation_snapshot`` from the DB instead.

A regression that imports ``trade`` from ``targets.py`` / ``registry.py`` would
work locally + in CI (trade is installed) but couple the read path to the heavy
scoring stack — exactly the §12.10 class this guard prevents.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"
STRATEGY_MODES = PACKAGE_ROOT / "strategy_modes"

REQUEST_PATH_MODULES = (
    STRATEGY_MODES / "targets.py",
    STRATEGY_MODES / "registry.py",
    STRATEGY_MODES / "__init__.py",
)
PRECOMPUTE_MODULE = STRATEGY_MODES / "regime_precompute.py"


def _imports_trade(py_path: Path) -> bool:
    """True if the module imports the top-level ``trade`` package (absolute)."""

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


def test_strategy_modes_request_layer_does_not_import_trade() -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in REQUEST_PATH_MODULES
        if path.is_file() and _imports_trade(path)
    )
    assert not offenders, (
        "§12.10 violated: the strategy-mode request layer imports the trade "
        f"package {offenders}. Read the precomputed recommendation_snapshot from "
        "the DB (get_target) instead — only the regime precompute job "
        "(strategy_modes/regime_precompute.py) may import trade."
    )


def test_regime_precompute_job_does_import_trade() -> None:
    """Pin the positive side: the regime precompute job IS the allowed importer
    of trade. A regression that severs this would silently stop real scoring."""

    assert PRECOMPUTE_MODULE.is_file()
    assert _imports_trade(PRECOMPUTE_MODULE), (
        "the regime precompute job must import trade (real regime-adaptive "
        "scoring); if scoring moved, update this guard + the request-layer test"
    )
