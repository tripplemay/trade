"""B047 F002 — backtest worker boundary (r) scope guard.

The backtest worker daemon runs the DETERMINISTIC Master Portfolio backtest
engine over read-only price data. Like the read-only schedulers it may import
``trade`` (the real engine) but must NEVER reach a trade-EXECUTION surface
(broker / order-ticket / fills / reconcile). These guards enforce that on the
package AND on the systemd unit, and pin that the daemon is wired by deploy.sh.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKTESTS_PKG = BACKEND_ROOT / "workbench_api" / "backtests"
REPO_ROOT = Path(__file__).resolve().parents[4]
WORKER_SERVICE = (
    REPO_ROOT / "workbench" / "deploy" / "systemd" / "workbench-backtest-worker.service"
)
CANONICAL_SERVICE = (
    REPO_ROOT / "workbench" / "deploy" / "systemd" / "workbench-canonical-backtest.service"
)
CANONICAL_TIMER = (
    REPO_ROOT / "workbench" / "deploy" / "systemd" / "workbench-canonical-backtest.timer"
)
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"

_FORBIDDEN_IMPORT_FRAGMENTS: tuple[str, ...] = (
    "broker",
    "order_ticket",
    "execution",
    "tickets",
    "fills",
    "reconcile",
)


def _imported_modules(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_backtests_package_imports_no_trade_execution_surface() -> None:
    offending: dict[str, list[str]] = {}
    for path in BACKTESTS_PKG.rglob("*.py"):
        modules = _imported_modules(path)
        hits = sorted(
            m for m in modules for frag in _FORBIDDEN_IMPORT_FRAGMENTS if frag in m
        )
        if hits:
            offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "Boundary (r) violated: the backtest worker package imports a "
        f"trade-execution surface {offending}. The worker runs the deterministic "
        "backtest engine only — remove the import."
    )


def test_worker_service_execstart_runs_worker_module() -> None:
    assert WORKER_SERVICE.is_file(), f"missing {WORKER_SERVICE}"
    text = WORKER_SERVICE.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1, "service must have exactly one ExecStart"
    assert "workbench_api.backtests.worker" in execstart[0]
    # Long-running daemon, not a oneshot.
    assert "Type=simple" in text
    assert "Restart=always" in text
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_worker_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in WORKER_SERVICE.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives, (
            f"backtest-worker .service directive references trade-execution {frag!r}"
        )


def test_canonical_service_execstart_runs_canonical_cli() -> None:
    assert CANONICAL_SERVICE.is_file(), f"missing {CANONICAL_SERVICE}"
    text = CANONICAL_SERVICE.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.backtests.canonical" in execstart[0]
    assert "Type=oneshot" in text  # timer-pulled, not a daemon
    # Auto-wired by the deploy timer-glob loop (sibling of its .timer).
    assert CANONICAL_TIMER.is_file()
    directives = "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives


def test_deploy_installs_backtest_worker_daemon() -> None:
    """deploy.sh must install + enable the worker daemon (it has no sibling
    timer, so the timer-glob loop won't cover it)."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert '"${SYSTEMD_SRC}"/workbench-*-worker.service' in text
    assert 'enable --now "${worker_unit}"' in text
