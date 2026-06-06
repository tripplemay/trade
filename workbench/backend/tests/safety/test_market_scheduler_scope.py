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
ADVISOR_PKG = BACKEND_ROOT / "workbench_api" / "advisor"
PRICES_PKG = BACKEND_ROOT / "workbench_api" / "prices"
NEWS_PKG = BACKEND_ROOT / "workbench_api" / "news"
# Four scheduler packages are scanned: the market-context fetch (B035), the
# AI advisor precompute (B036), the price-snapshot fetch (B037), and the
# news ingest (B038, boundary (q)→(r)). Boundary (r) was revised in B036 — a
# scheduler may run CI-safety-gated advisor precompute (which imports the LLM
# gateway), but still never a trade-execution surface. The B037 price fetch
# and the B038 news fetch are read-only data; news ingest is also
# non-generative (B034 boundary — embed only, never advise).
SCHEDULER_PKGS = (MARKET_PKG, ADVISOR_PKG, PRICES_PKG, NEWS_PKG)
REPO_ROOT = Path(__file__).resolve().parents[4]
SYSTEMD_DIR = REPO_ROOT / "workbench" / "deploy" / "systemd"
SERVICE_UNIT = SYSTEMD_DIR / "workbench-market-context.service"
TIMER_UNIT = SYSTEMD_DIR / "workbench-market-context.timer"
ADVISOR_SERVICE_UNIT = SYSTEMD_DIR / "workbench-advisor.service"
ADVISOR_TIMER_UNIT = SYSTEMD_DIR / "workbench-advisor.timer"
PRICES_SERVICE_UNIT = SYSTEMD_DIR / "workbench-prices.service"
PRICES_TIMER_UNIT = SYSTEMD_DIR / "workbench-prices.timer"
NEWS_SERVICE_UNIT = SYSTEMD_DIR / "workbench-news.service"
NEWS_TIMER_UNIT = SYSTEMD_DIR / "workbench-news.timer"
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"

# Dotted-path fragments that mark a TRADE-EXECUTION surface a scheduler must
# never import (boundary (r), revised B036). LLM + advisor are now allowed
# (the advisor precompute is CI-safety-gated); only order/trade execution
# stays forbidden.
_FORBIDDEN_IMPORT_FRAGMENTS: tuple[str, ...] = (
    "broker",
    "order_ticket",
    "execution",
    "tickets",
    "fills",
    "reconcile",
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


def test_scheduler_packages_import_no_trade_execution_surface() -> None:
    offending: dict[str, list[str]] = {}
    for pkg in SCHEDULER_PKGS:
        for path in pkg.rglob("*.py"):
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
        "Permanent product boundary (r) violated: a scheduler package imports "
        f"a trade-execution surface {offending}. Schedulers may fetch data and "
        "run the CI-safety-gated advisor, but never broker / order-ticket / "
        "execution — remove the import or add a relaxation note in "
        "framework/proposed-learnings.md."
    )


def test_scheduler_packages_no_inprocess_scheduler_lib() -> None:
    offending: dict[str, list[str]] = {}
    for pkg in SCHEDULER_PKGS:
        for path in pkg.rglob("*.py"):
            top_level = {m.split(".", 1)[0] for m in _imported_modules(path)}
            hits = sorted(top_level & _FORBIDDEN_SCHEDULER_LIBS)
            if hits:
                offending[str(path.relative_to(BACKEND_ROOT))] = hits
    assert not offending, (
        "Schedulers use OS-level systemd timers, not an in-process scheduler: "
        f"{offending}. Do not add apscheduler / aiocron / schedule (avoids a "
        "new runtime dep + keeps the app stateless)."
    )


def test_advisor_scheduler_may_import_llm_gateway() -> None:
    """Boundary (r) revision (B036): the advisor scheduler is explicitly
    ALLOWED to import the LLM gateway (it runs the CI-safety-gated advisor).
    This pins that the revision landed — a regression that re-bans llm under
    the scheduler scope would break the advisor precompute."""

    service_src = (ADVISOR_PKG / "service.py").read_text(encoding="utf-8")
    assert "workbench_api.llm.gateway" in service_src


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


def test_deploy_installs_and_enables_timers_via_dry_loop() -> None:
    """B037-OPS1: the per-timer install/enable blocks were collapsed into a
    single loop over ${SYSTEMD_SRC}/workbench-*.timer. The market-context,
    advisor and prices timers are now wired by that glob, not named literally.
    Detailed coverage lives in test_deploy_timer_wiring.py; this pins the
    boundary-(r) scheduler-scope view of the same wiring."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "daemon-reload" in text
    # deploy.sh must reference the units at the actual release layout
    # (${RELEASE_DIR}/systemd) — the release ships scripts/ + systemd/ at
    # the top level, NOT a deploy/ dir (regression found 2026-06-05).
    assert 'SYSTEMD_SRC="${RELEASE_DIR}/systemd"' in text
    # The DRY glob loop replaces the per-timer hardcoded blocks.
    assert 'for timer_path in "${SYSTEMD_SRC}"/workbench-*.timer' in text
    assert 'enable --now "${timer_unit}"' in text
    # Each read-only timer ships so the glob picks it up.
    for unit in (
        "workbench-market-context.timer",
        "workbench-advisor.timer",
        "workbench-prices.timer",
    ):
        assert (SYSTEMD_DIR / unit).is_file(), f"missing shipped unit {unit}"


def test_deploy_workflow_ships_systemd_units() -> None:
    """The deploy workflow must rsync workbench/deploy/systemd into the
    release, else deploy.sh's timer install finds nothing (2026-06-05:
    units were never shipped — release had scripts/ but no systemd/)."""

    workflow = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "rsync -a workbench/deploy/systemd" in text


# --- B036 advisor timer (boundary (r) revision) --------------------------


def test_advisor_service_execstart_runs_advisor_cli() -> None:
    assert ADVISOR_SERVICE_UNIT.is_file(), f"missing {ADVISOR_SERVICE_UNIT}"
    text = ADVISOR_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.advisor.cli" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_advisor_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in ADVISOR_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "execution", "ticket", "fills"):
        assert frag not in directives, (
            f"advisor .service directive references trade-execution {frag!r} "
            "(boundary (r))"
        )


def test_advisor_timer_runs_daily_after_market() -> None:
    assert ADVISOR_TIMER_UNIT.is_file(), f"missing {ADVISOR_TIMER_UNIT}"
    text = ADVISOR_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-advisor.service" in text
    assert "WantedBy=timers.target" in text


def test_advisor_timer_wired_by_dry_loop() -> None:
    """B037-OPS1: advisor timer is installed by the workbench-*.timer loop
    (no hardcoded literal). It must ship so the glob covers it."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-advisor.timer" not in text, (
        "advisor timer must be wired by the DRY loop, not a hardcoded enable"
    )
    assert (SYSTEMD_DIR / "workbench-advisor.timer").is_file()


# --- B037 price-snapshot timer (boundary (r): read-only price fetch) ------


def test_prices_service_execstart_runs_prices_cli() -> None:
    assert PRICES_SERVICE_UNIT.is_file(), f"missing {PRICES_SERVICE_UNIT}"
    text = PRICES_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.prices.cli fetch" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_prices_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in PRICES_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "execution", "ticket", "fills"):
        assert frag not in directives, (
            f"prices .service directive references trade-execution {frag!r} "
            "(boundary (r))"
        )


def test_prices_timer_runs_daily_and_pulls_service() -> None:
    assert PRICES_TIMER_UNIT.is_file(), f"missing {PRICES_TIMER_UNIT}"
    text = PRICES_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-prices.service" in text
    assert "WantedBy=timers.target" in text


def test_prices_timer_wired_by_dry_loop() -> None:
    """B037-OPS1: prices timer is installed by the workbench-*.timer loop
    (no hardcoded literal). It must ship so the glob covers it."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-prices.timer" not in text, (
        "prices timer must be wired by the DRY loop, not a hardcoded enable"
    )
    assert (SYSTEMD_DIR / "workbench-prices.timer").is_file()


# --- B038 news ingest timer (boundary (q)→(r): read-only news fetch) -------


def test_news_service_execstart_runs_news_cli() -> None:
    assert NEWS_SERVICE_UNIT.is_file(), f"missing {NEWS_SERVICE_UNIT}"
    text = NEWS_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.news.cli fetch" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_news_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in NEWS_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "execution", "ticket", "fills"):
        assert frag not in directives, (
            f"news .service directive references trade-execution {frag!r} "
            "(boundary (r))"
        )


def test_news_timer_runs_daily_and_pulls_service() -> None:
    assert NEWS_TIMER_UNIT.is_file(), f"missing {NEWS_TIMER_UNIT}"
    text = NEWS_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-news.service" in text
    assert "WantedBy=timers.target" in text


def test_news_timer_wired_by_dry_loop() -> None:
    """B038 first exercises B037-OPS1's durable wiring: the news timer is
    installed by the workbench-*.timer loop with ZERO deploy.sh / sudoers
    changes. It must ship so the glob covers it; no hardcoded literal."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-news.timer" not in text, (
        "news timer must be wired by the DRY loop, not a hardcoded enable "
        "(B037-OPS1 durable auto-wiring — zero deploy.sh change)"
    )
    assert NEWS_TIMER_UNIT.is_file()
