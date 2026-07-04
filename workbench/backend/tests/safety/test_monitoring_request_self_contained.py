"""B080 F003 — monitoring request-path §12.10.2 self-containment.

The frozen re-validation follows the Option-A async shape: ``POST
/api/monitoring/reverify`` only enqueues a ``reverify_job`` row; ``GET
/api/monitoring/reverify/{job_id}`` only reads it. The heavy data-append + frozen
backtest + landings run on the backtest-worker daemon (the allowed ``trade``
importer). So the request path — the route + the enqueue service — must NEVER
import ``trade``, nor the reverify compute modules that pull ``trade`` / baostock
(kernel / runner / worker / data-append). A regression would couple the auth-gated
enqueue to the scoring stack and pass locally + in CI where trade is installed.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"

REQUEST_PATH_MODULES = (
    PACKAGE_ROOT / "routes" / "monitoring.py",
    PACKAGE_ROOT / "monitoring" / "reverify_service.py",
    PACKAGE_ROOT / "schemas" / "monitoring.py",
)

# The compute modules that DO pull trade / baostock — the request path must not
# import them (only the worker may). Names are matched against import module paths.
_FORBIDDEN_MODULE_FRAGMENTS = (
    "monitoring.reverify_kernel",
    "monitoring.reverify_runner",
    "monitoring.reverify_worker",
    "monitoring.reverify_data_append",
    "monitoring.metrics_job",
)

# The worker IS the allowed off-request-path trade importer.
WORKER_MODULE = PACKAGE_ROOT / "monitoring" / "reverify_worker.py"


def _imported_modules(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
    return out


def test_monitoring_request_path_is_self_contained() -> None:
    for path in REQUEST_PATH_MODULES:
        assert path.is_file(), f"request-path module missing: {path}"
        modules = _imported_modules(path)
        trade_hits = sorted(
            m for m in modules if m == "trade" or m.startswith("trade.")
        )
        assert not trade_hits, (
            f"§12.10.2: {path.name} imports trade {trade_hits} — the monitoring "
            "request path must stay off the scoring stack."
        )
        compute_hits = sorted(
            m
            for m in modules
            for frag in _FORBIDDEN_MODULE_FRAGMENTS
            if frag in m
        )
        assert not compute_hits, (
            f"§12.10.2: {path.name} imports a trade/baostock compute module "
            f"{compute_hits} — enqueue only; let the worker run it."
        )


def test_reverify_worker_is_the_allowed_importer() -> None:
    """Pin the worker as the off-path runner (imports the runner → kernel that
    lazily imports trade). A refactor severing this is caught here."""

    assert WORKER_MODULE.is_file()
    modules = _imported_modules(WORKER_MODULE)
    assert any("reverify_runner" in m for m in modules), (
        "reverify_worker must drive the runner (the frozen-backtest orchestration)"
    )
