"""B044 F003 — recommendations request-path §12.10 self-containment.

B044 F001 ships the ``trade`` package into the VM venv so the precompute timer
can import it for real Master Portfolio scoring. That means the §12.10
"request path must not depend on trade" boundary can no longer rely on
``trade`` being physically absent — it is now enforced HERE, by AST.

Contract:
- The request path — ``routes/recommendations.py`` + ``services/recommendations.py``
  — must NEVER import ``trade`` (it reads the precomputed recommendation_snapshot
  from the DB instead).
- Only the precompute JOB (``workbench_api/recommendations/precompute.py``) may
  import ``trade``.

A regression that imports ``trade`` on the request path would work locally + in
CI (trade is installed) but couples the auth-gated read path to the heavy
scoring stack — exactly the §12.10 class this guard prevents.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"

REQUEST_PATH_MODULES = (
    PACKAGE_ROOT / "routes" / "recommendations.py",
    PACKAGE_ROOT / "services" / "recommendations.py",
    # B051: account state now flows through nav.py (account_snapshot
    # mark-to-market) — these joined the request path's import closure.
    PACKAGE_ROOT / "services" / "nav.py",
    PACKAGE_ROOT / "services" / "mark_to_market.py",
    PACKAGE_ROOT / "services" / "prices_provider.py",
)
PRECOMPUTE_MODULE = PACKAGE_ROOT / "recommendations" / "precompute.py"


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


def test_recommendations_request_path_does_not_import_trade() -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in REQUEST_PATH_MODULES
        if path.is_file() and _imports_trade(path)
    )
    assert not offenders, (
        "§12.10 violated: the recommendations request path imports the trade "
        f"package {offenders}. Read the precomputed recommendation_snapshot from "
        "the DB instead — only workbench_api/recommendations/precompute.py (the "
        "job) may import trade."
    )


def test_precompute_job_does_import_trade() -> None:
    """Pin the positive side: the precompute job IS the allowed importer of
    trade. A regression that severs this would silently stop real scoring."""

    assert PRECOMPUTE_MODULE.is_file()
    assert _imports_trade(PRECOMPUTE_MODULE), (
        "the recommendations precompute job must import trade (real Master "
        "scoring); if scoring moved, update this guard + the request-path test"
    )
