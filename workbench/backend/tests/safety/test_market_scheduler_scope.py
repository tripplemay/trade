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
RECOMMENDATIONS_PKG = BACKEND_ROOT / "workbench_api" / "recommendations"
DATA_REFRESH_PKG = BACKEND_ROOT / "workbench_api" / "data_refresh"
PRICE_HISTORY_PKG = BACKEND_ROOT / "workbench_api" / "price_history"
NEWS_TRANSLATE_PKG = BACKEND_ROOT / "workbench_api" / "news_translation"
PAPER_PKG = BACKEND_ROOT / "workbench_api" / "paper"
STRATEGY_MODES_PKG = BACKEND_ROOT / "workbench_api" / "strategy_modes"
# Seven scheduler packages are scanned: the market-context fetch (B035), the
# AI advisor precompute (B036), the price-snapshot fetch (B037), the news
# ingest (B038, boundary (q)→(r)), the recommendations precompute (B044,
# boundary (r-c) deterministic quant scoring), the data-refresh job (B045),
# and the price-history backfill (B048, reads the B045 unified CSV → DB).
# Boundary (r) was revised in B036 — a scheduler may run CI-safety-gated
# advisor precompute (which imports the LLM gateway); B044 adds quant scoring
# that imports the ``trade`` package; B054 adds news-headline translation
# (generative, no-AI rule (e): translate only, off the request path) — but
# NONE may ever reach a trade-EXECUTION surface (broker/order/fills/...).
SCHEDULER_PKGS = (
    MARKET_PKG,
    ADVISOR_PKG,
    PRICES_PKG,
    NEWS_PKG,
    RECOMMENDATIONS_PKG,
    DATA_REFRESH_PKG,
    PRICE_HISTORY_PKG,
    NEWS_TRANSLATE_PKG,
    PAPER_PKG,
    # B057 F001 — the strategy-mode platform layer: the regime precompute job
    # imports trade (deterministic quant scoring, boundary (r-c)), the generic
    # target layer + registry are read models. None may reach a trade-EXECUTION
    # surface (broker/order/fills/...).
    STRATEGY_MODES_PKG,
)
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
RECO_SERVICE_UNIT = SYSTEMD_DIR / "workbench-recommendations.service"
RECO_TIMER_UNIT = SYSTEMD_DIR / "workbench-recommendations.timer"
REFRESH_SERVICE_UNIT = SYSTEMD_DIR / "workbench-data-refresh.service"
REFRESH_TIMER_UNIT = SYSTEMD_DIR / "workbench-data-refresh.timer"
RISK_EXPL_SERVICE_UNIT = SYSTEMD_DIR / "workbench-risk-explanation.service"
RISK_EXPL_TIMER_UNIT = SYSTEMD_DIR / "workbench-risk-explanation.timer"
NEWS_TRANSLATE_SERVICE_UNIT = SYSTEMD_DIR / "workbench-news-translate.service"
NEWS_TRANSLATE_TIMER_UNIT = SYSTEMD_DIR / "workbench-news-translate.timer"
PAPER_MTM_SERVICE_UNIT = SYSTEMD_DIR / "workbench-paper-mtm.service"
PAPER_MTM_TIMER_UNIT = SYSTEMD_DIR / "workbench-paper-mtm.timer"
REGIME_SERVICE_UNIT = SYSTEMD_DIR / "workbench-regime-precompute.service"
REGIME_TIMER_UNIT = SYSTEMD_DIR / "workbench-regime-precompute.timer"
RISK_EXPL_MODULE = (
    BACKEND_ROOT / "workbench_api" / "services" / "risk_explanation.py"
)
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


def test_price_history_backfill_in_scheduler_scope() -> None:
    """B048 F001: the price-history backfill job is a read-only data job
    (reads the B045 unified CSV, writes price_history). Pin that its
    package is covered by the boundary-(r) scope guard so a future import
    of a trade-execution surface there is caught."""

    assert PRICE_HISTORY_PKG in SCHEDULER_PKGS
    assert PRICE_HISTORY_PKG.is_dir()


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


# --- B044 recommendations precompute (boundary (r-c): read-only quant scoring) ---


def test_recommendations_service_execstart_runs_reco_cli() -> None:
    assert RECO_SERVICE_UNIT.is_file(), f"missing {RECO_SERVICE_UNIT}"
    text = RECO_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.recommendations.cli" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_recommendations_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in RECO_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile"):
        assert frag not in directives, (
            f"recommendations .service directive references trade-execution {frag!r} "
            "(boundary (r-c))"
        )


def test_recommendations_timer_runs_daily_and_pulls_service() -> None:
    assert RECO_TIMER_UNIT.is_file(), f"missing {RECO_TIMER_UNIT}"
    text = RECO_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-recommendations.service" in text
    assert "WantedBy=timers.target" in text


def test_recommendations_timer_wired_by_dry_loop() -> None:
    """B044 timer installs via the B037-OPS1 workbench-*.timer loop — no
    hardcoded enable literal in deploy.sh."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-recommendations.timer" not in text
    assert RECO_TIMER_UNIT.is_file()


def test_recommendations_precompute_may_import_trade() -> None:
    """Boundary (r-c, B044): the recommendations precompute is explicitly
    ALLOWED to import the ``trade`` package (real Master Portfolio scoring) —
    pin that it does, so a regression that severs the scoring import is caught.
    The request path must NOT import trade (separate §12.10 AST guard)."""

    precompute_src = (RECOMMENDATIONS_PKG / "precompute.py").read_text(encoding="utf-8")
    assert "trade.backtest.master_portfolio" in precompute_src


# --- B045 data-refresh job (boundary (r): read-only prices + fundamentals) ---


def test_data_refresh_service_execstart_runs_refresh_cli() -> None:
    assert REFRESH_SERVICE_UNIT.is_file(), f"missing {REFRESH_SERVICE_UNIT}"
    text = REFRESH_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.data_refresh.cli" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_data_refresh_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in REFRESH_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile"):
        assert frag not in directives, (
            f"data-refresh .service directive references trade-execution {frag!r} "
            "(boundary (r))"
        )


def test_data_refresh_timer_runs_daily_and_pulls_service() -> None:
    assert REFRESH_TIMER_UNIT.is_file(), f"missing {REFRESH_TIMER_UNIT}"
    text = REFRESH_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-data-refresh.service" in text
    assert "WantedBy=timers.target" in text


def test_data_refresh_timer_wired_by_dry_loop() -> None:
    """B045 timer installs via the B037-OPS1 workbench-*.timer loop — no
    hardcoded enable literal in deploy.sh."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-data-refresh.timer" not in text
    assert REFRESH_TIMER_UNIT.is_file()


# --- B043 F003 risk-explanation timer (boundary (r) + §12.10.2: read-only
# risk grounding + off-request-path LLM; no execution) ---


def test_risk_explanation_service_execstart_runs_risk_module() -> None:
    assert RISK_EXPL_SERVICE_UNIT.is_file(), f"missing {RISK_EXPL_SERVICE_UNIT}"
    text = RISK_EXPL_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.services.risk_explanation" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_risk_explanation_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in RISK_EXPL_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives, (
            f"risk-explanation .service directive references trade-execution "
            f"{frag!r} (boundary (r))"
        )


def test_risk_explanation_timer_runs_daily_and_pulls_service() -> None:
    assert RISK_EXPL_TIMER_UNIT.is_file(), f"missing {RISK_EXPL_TIMER_UNIT}"
    text = RISK_EXPL_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-risk-explanation.service" in text
    assert "WantedBy=timers.target" in text


def test_risk_explanation_timer_wired_by_dry_loop() -> None:
    """B043 F003 timer installs via the B037-OPS1 workbench-*.timer loop — zero
    deploy.sh change, no hardcoded enable literal."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-risk-explanation.timer" not in text
    assert RISK_EXPL_TIMER_UNIT.is_file()


def test_risk_explanation_module_imports_no_trade_execution_surface() -> None:
    """The risk-explanation scheduler entry module must not DIRECTLY import a
    trade-execution surface (it reuses the read-only risk-panel computation + the
    LLM gateway only). Mirrors the SCHEDULER_PKGS boundary for a job that lives
    under services/ (which legitimately also contains execution code, so the
    whole package can't be in SCHEDULER_PKGS)."""

    hits = sorted(
        m
        for m in _imported_modules(RISK_EXPL_MODULE)
        for frag in _FORBIDDEN_IMPORT_FRAGMENTS
        if frag in m
    )
    assert not hits, (
        f"risk_explanation scheduler entry imports a trade-execution surface {hits} "
        "(boundary (r))"
    )


# --- B054 F-news translation timer (boundary (r) + no-AI rule (e):
# generative translate, off request path; never execution) ---


def test_news_translate_service_execstart_runs_translate_cli() -> None:
    assert NEWS_TRANSLATE_SERVICE_UNIT.is_file(), f"missing {NEWS_TRANSLATE_SERVICE_UNIT}"
    text = NEWS_TRANSLATE_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.news_translation.cli" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_news_translate_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in NEWS_TRANSLATE_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives, (
            f"news-translate .service directive references trade-execution "
            f"{frag!r} (boundary (r))"
        )


def test_news_translate_timer_runs_daily_and_pulls_service() -> None:
    assert NEWS_TRANSLATE_TIMER_UNIT.is_file(), f"missing {NEWS_TRANSLATE_TIMER_UNIT}"
    text = NEWS_TRANSLATE_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-news-translate.service" in text
    assert "WantedBy=timers.target" in text


def test_news_translate_timer_wired_by_dry_loop() -> None:
    """B054 timer installs via the B037-OPS1 workbench-*.timer loop — zero
    deploy.sh change, no hardcoded enable literal."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-news-translate.timer" not in text
    assert NEWS_TRANSLATE_TIMER_UNIT.is_file()


def test_news_translate_scheduler_may_import_llm_gateway() -> None:
    """Boundary (r) + no-AI rule (e): the news-translate scheduler is ALLOWED
    to import the LLM gateway (it runs the generative translate precompute,
    off the request path). Pin that it does, so a regression that severs the
    gateway import is caught."""

    service_src = (NEWS_TRANSLATE_PKG / "service.py").read_text(encoding="utf-8")
    assert "workbench_api.llm.gateway" in service_src


# --- B056 F002 paper-trading MTM timer (boundary (r): read-only prices +
# stored targets; the engine is VIRTUAL — no real orders) ---


def test_paper_mtm_service_execstart_runs_paper_mtm() -> None:
    assert PAPER_MTM_SERVICE_UNIT.is_file(), f"missing {PAPER_MTM_SERVICE_UNIT}"
    text = PAPER_MTM_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.paper.mtm" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_paper_mtm_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in PAPER_MTM_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives, (
            f"paper-mtm .service directive references trade-execution {frag!r} "
            "(boundary (r))"
        )


def test_paper_mtm_timer_runs_daily_and_pulls_service() -> None:
    assert PAPER_MTM_TIMER_UNIT.is_file(), f"missing {PAPER_MTM_TIMER_UNIT}"
    text = PAPER_MTM_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-paper-mtm.service" in text
    assert "WantedBy=timers.target" in text


def test_paper_mtm_timer_wired_by_dry_loop() -> None:
    """B056 timer installs via the B037-OPS1 workbench-*.timer loop — zero
    deploy.sh change, no hardcoded enable literal."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-paper-mtm.timer" not in text
    assert PAPER_MTM_TIMER_UNIT.is_file()


def test_paper_package_may_import_recommendation_target_not_trade() -> None:
    """The paper engine follows the strategy's STORED target — it resolves the
    target through the generic target layer (which reads recommendation_snapshot),
    never imports ``trade`` (the request/job stays self-contained). Pin both
    halves.

    B057 F001: the read was delegated to ``strategy_modes.targets`` (single
    source), so the paper targets module now references the generic layer and the
    generic layer reads the snapshot table."""

    targets_src = (PAPER_PKG / "targets.py").read_text(encoding="utf-8")
    assert "strategy_modes.targets" in targets_src
    generic_src = (STRATEGY_MODES_PKG / "targets.py").read_text(encoding="utf-8")
    assert "recommendation_snapshot" in generic_src
    for path in PAPER_PKG.rglob("*.py"):
        imported = _imported_modules(path)
        assert not any(
            m == "trade" or m.startswith("trade.") for m in imported
        ), f"{path.name} imports the trade package on the paper (job) path"


# --- B057 F001 regime-adaptive precompute (boundary (r-c): read-only quant
# scoring of the regime mode's target; research-state, no prediction) ---


def test_regime_service_execstart_runs_regime_cli() -> None:
    assert REGIME_SERVICE_UNIT.is_file(), f"missing {REGIME_SERVICE_UNIT}"
    text = REGIME_SERVICE_UNIT.read_text(encoding="utf-8")
    execstart = [ln for ln in text.splitlines() if ln.strip().startswith("ExecStart=")]
    assert len(execstart) == 1
    assert "workbench_api.strategy_modes.cli" in execstart[0]
    assert "EnvironmentFile=/etc/workbench/workbench.env" in text


def test_regime_service_references_no_trade_execution() -> None:
    directives = "\n".join(
        ln
        for ln in REGIME_SERVICE_UNIT.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#")
    ).lower()
    for frag in ("broker", "order_ticket", "fills", "reconcile", "ticket"):
        assert frag not in directives, (
            f"regime .service directive references trade-execution {frag!r} "
            "(boundary (r-c))"
        )


def test_regime_timer_runs_and_pulls_service() -> None:
    assert REGIME_TIMER_UNIT.is_file(), f"missing {REGIME_TIMER_UNIT}"
    text = REGIME_TIMER_UNIT.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Unit=workbench-regime-precompute.service" in text
    assert "WantedBy=timers.target" in text


def test_regime_timer_wired_by_dry_loop() -> None:
    """B057 timer installs via the B037-OPS1 workbench-*.timer loop — zero
    deploy.sh change, no hardcoded enable literal."""
    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "enable --now workbench-regime-precompute.timer" not in text
    assert REGIME_TIMER_UNIT.is_file()


def test_regime_precompute_may_import_trade() -> None:
    """Boundary (r-c, B057): the regime precompute is explicitly ALLOWED to
    import the ``trade`` package (real regime-adaptive scoring) — pin that it
    does, so a regression that severs the scoring import is caught. The generic
    target layer + registry must NOT import trade (separate §12.10 AST guard)."""

    precompute_src = (STRATEGY_MODES_PKG / "regime_precompute.py").read_text(
        encoding="utf-8"
    )
    assert "trade.strategies.regime_adaptive" in precompute_src
