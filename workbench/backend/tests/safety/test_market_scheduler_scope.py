"""B035 F002 — permanent product boundary **(r)** scope guard.

The project's first scheduler (the market-context systemd timer) is
allowed to do **read-only market-data fetching only**. It must never
reach into trading surfaces — broker / order-ticket / execution /
recommendation / LLM code (B035 spec §3). These guards enforce that at
three levels:

1. No module under ``workbench_api/market/`` imports a trading /
   recommendation / LLM module (AST walk).
2. No in-process scheduler library (apscheduler / aiocron / schedule) is
   imported under ``workbench_api/market/`` — the schedule is an OS-level
   systemd timer, not an app-process loop (avoids a new runtime dep).
3. The systemd ``.service`` ``ExecStart`` invokes only the market CLI,
   and neither unit references a trading surface; the ``.timer`` runs
   daily; ``deploy.sh`` installs + enables the timer.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MARKET_PKG = BACKEND_ROOT / "workbench_api" / "market"
REPO_ROOT = Path(__file__).resolve().parents[4]
SYSTEMD_DIR = REPO_ROOT / "workbench" / "deploy" / "systemd"
SERVICE_UNIT = SYSTEMD_DIR / "workbench-market-context.service"
TIMER_UNIT = SYSTEMD_DIR / "workbench-market-context.timer"
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"

# Dotted-path fragments that mark a trading / recommendation / LLM surface
# the read-only market scheduler must never import (boundary (r)).
_FORBIDDEN_IMPORT_FRAGMENTS: tuple[str, ...] = (
    "broker",
    "order_ticket",
    "execution",
    "recommendation",
    "tickets",
    "fills",
    "reconcile",
    "workbench_api.llm",
)

_FORBIDDEN_SCHEDULER_LIBS: frozenset[str] = frozenset(
    {"apscheduler", "aiocron", "schedule"}
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


def test_market_package_imports_no_trading_surface() -> None:
    offending: dict[str, list[str]] = {}
    for path in MARKET_PKG.rglob("*.py"):
        modules = _imported_modules(path)
        hits = sorted(
            m
            for m in modules
            for frag in _FORBIDDEN_IMPORT_FRAGMENTS
            if frag in m
        )
        if hits:
            offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "Permanent product boundary (r) violated: the market scheduler "
        f"package imports a trading/recommendation/LLM surface {offending}. "
        "The timer does read-only market-data fetch only — remove the import "
        "or add a boundary relaxation note in framework/proposed-learnings.md."
    )


def test_market_package_no_inprocess_scheduler_lib() -> None:
    offending: dict[str, list[str]] = {}
    for path in MARKET_PKG.rglob("*.py"):
        top_level = {m.split(".", 1)[0] for m in _imported_modules(path)}
        hits = sorted(top_level & _FORBIDDEN_SCHEDULER_LIBS)
        if hits:
            offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "B035 uses an OS-level systemd timer, not an in-process scheduler: "
        f"{offending}. Do not add apscheduler / aiocron / schedule (avoids a "
        "new runtime dep + keeps the app stateless)."
    )


def test_service_execstart_only_market_cli() -> None:
    assert SERVICE_UNIT.is_file(), f"missing {SERVICE_UNIT}"
    text = SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1, "service must have exactly one ExecStart"
    assert "workbench_api.market.cli fetch" in execstart[0], (
        "ExecStart must invoke the market CLI fetch command only"
    )


def test_service_references_no_trading_surface() -> None:
    # Scan only systemd directive lines, not comments — the boundary
    # comment legitimately *names* the forbidden surfaces to document (r).
    directives = "\n".join(
        ln
        for ln in SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "execution", "recommendation", "ticket"):
        assert frag not in directives, (
            f"market-context .service directive references trading surface "
            f"{frag!r} (boundary (r))"
        )


def test_service_loads_env_file_for_keys() -> None:
    text = SERVICE_UNIT.read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_timer_runs_daily_and_pulls_service() -> None:
    assert TIMER_UNIT.is_file(), f"missing {TIMER_UNIT}"
    text = TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=daily" in text
    assert "Unit=workbench-market-context.service" in text
    assert "WantedBy=timers.target" in text


def test_deploy_installs_and_enables_timer() -> None:
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "workbench-market-context.timer" in text
    assert "enable --now workbench-market-context.timer" in text
    assert "daemon-reload" in text
    # deploy.sh must reference the units at the actual release layout
    # (${RELEASE_DIR}/systemd) — the release ships scripts/ + systemd/ at
    # the top level, NOT a deploy/ dir (regression found 2026-06-05).
    assert 'SYSTEMD_SRC="${RELEASE_DIR}/systemd"' in text


def test_deploy_workflow_ships_systemd_units() -> None:
    """The deploy workflow must rsync workbench/deploy/systemd into the
    release, else deploy.sh's timer install finds nothing (2026-06-05:
    units were never shipped — release had scripts/ but no systemd/)."""

    workflow = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "rsync -a workbench/deploy/systemd" in text
