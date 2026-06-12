#!/usr/bin/env bash
# Workbench deploy step — runs on the VM as the `deploy` user.
#
# Argument: the absolute path to the newly-SCP'd release directory under
# /srv/workbench/releases/<sha>/. CI (B021 F004 workbench-deploy.yml) calls
# this script via SSH after the SCP step lands the artifacts.
#
# Side effects (in order):
#   1. Install backend wheel into /opt/workbench/.venv (handles first-time
#      bootstrap; subsequent runs upgrade in-place).
#   2. Run `alembic upgrade head` against WORKBENCH_DB_URL (idempotent).
#   3. Atomically flip /srv/workbench/current symlink to the new release.
#   4. systemctl restart workbench-backend.service workbench-frontend.service.
#
# Bash 3.2 compatible (no `wait -n`, no `mapfile`, no `${var^^}`).

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $(basename "$0") /srv/workbench/releases/<sha>" >&2
  exit 64
fi

RELEASE_DIR="$1"
WORKBENCH_ROOT="${WORKBENCH_ROOT:-/srv/workbench}"
CURRENT_LINK="${WORKBENCH_ROOT}/current"
VENV_PIP="/opt/workbench/.venv/bin/pip"
VENV_PYTHON="/opt/workbench/.venv/bin/python"

if [[ ! -d "${RELEASE_DIR}" ]]; then
  echo "error: release dir not found: ${RELEASE_DIR}" >&2
  exit 65
fi
if [[ ! -d "${RELEASE_DIR}/backend" ]] || [[ ! -d "${RELEASE_DIR}/frontend" ]]; then
  echo "error: release dir missing backend/ or frontend/: ${RELEASE_DIR}" >&2
  exit 65
fi

# 1. Install the backend wheel into the shared venv. We use the built
# wheel (workbench/backend/dist/workbench_api-*.whl) when present — this
# is what the CI build step ships in the release tarball. Falls back to
# `pip install -e ${RELEASE_DIR}/backend` only if no wheel is found
# (developer-driven one-shot deploys without the CI build).
echo "→ install backend into /opt/workbench/.venv"
WHEEL=$(ls "${RELEASE_DIR}"/backend/dist/workbench_api-*.whl 2>/dev/null | head -n 1 || true)
if [[ -n "${WHEEL}" ]]; then
  echo "  wheel: ${WHEEL}"
  "${VENV_PIP}" install --quiet --upgrade "${WHEEL}"
else
  echo "  no prebuilt wheel under ${RELEASE_DIR}/backend/dist/; falling back to editable install"
  "${VENV_PIP}" install --quiet --upgrade -e "${RELEASE_DIR}/backend"
fi

# B044 F001 — install the trade/ wheel into the shared venv alongside
# workbench_api. The recommendations precompute timer (B044 F002) imports
# trade.backtest.master_portfolio for real scoring; the request path must
# NEVER import trade (§12.10 AST guard, F003). This is additive — the
# workbench_api backend does not import trade, so backend startup is
# unchanged. Best-effort: a dev `deploy.sh` rehearsal without the trade wheel
# still completes the backend/frontend deploy.
echo "→ install trade package into /opt/workbench/.venv"
TRADE_WHEEL=$(ls "${RELEASE_DIR}"/trade-dist/trade-*.whl 2>/dev/null | head -n 1 || true)
if [[ -n "${TRADE_WHEEL}" ]]; then
  echo "  wheel: ${TRADE_WHEEL}"
  # B045-OPS1 F001 — reliable trade-wheel (re)install. Lessons baked in:
  #   --force-reinstall : a same-version wheel must STILL overwrite the installed
  #     files (B045 F004 #2 — --upgrade skipped same-version 0.1.0 → 0.2.0 and
  #     left trade.data.data_root absent → precompute ModuleNotFoundError).
  #   --no-deps         : reinstall ONLY trade, never its deps. pandas/numpy are
  #     already in the venv (the backend wheel installed just above pulls them in
  #     transitively via yfinance), so re-resolving them here is pointless AND is
  #     the S4 silent-failure root cause: --force-reinstall WITHOUT --no-deps
  #     re-resolves pandas/numpy against PyPI, which on the restricted VM can
  #     stall / fail and leave trade stale. --no-deps makes the reinstall a
  #     deterministic, network-independent file overwrite from the local wheel.
  #   no --quiet        : the resolved version must be visible in the deploy log.
  "${VENV_PIP}" install --force-reinstall --no-deps "${TRADE_WHEEL}"
  "${VENV_PIP}" show trade | grep -i '^Version:' || true

  # B045-OPS1 F001 — smoke import check (the durable defence; v0.9.36 铁律).
  # pip exiting 0 is NOT proof precompute can import trade: a stale wheel installs
  # "fine" yet is missing a newly-added module (e.g. trade.data.data_root), then
  # the recommendations precompute timer dies at runtime — invisible to the
  # deploy. Import the exact two modules precompute depends on; any failure is a
  # LOUD hard deploy failure (::error:: survives every quiet flag), never a
  # silent pass. This catches ALL S4 root-cause candidates (stale wheel / missing
  # module / broken deps), independent of why the install regressed.
  echo "→ smoke import check: trade precompute modules"
  if ! "${VENV_PYTHON}" -c "import trade.backtest.master_portfolio; import trade.data.data_root"; then
    echo "::error::trade smoke import failed after install (${TRADE_WHEEL}) — precompute would break at runtime; failing the deploy"
    exit 1
  fi
  echo "  trade smoke import OK"
else
  echo "  no trade wheel under ${RELEASE_DIR}/trade-dist/; skipping (B044 F001 — precompute will be unavailable until shipped)"
fi

# 2. Apply pending DB migrations. The workbench is single-VM single-user so
# we do not need a separate migrate worker — applying inline is the simplest
# safe ordering (migrate before symlink flip prevents the new server code
# from hitting an older schema mid-deploy).
#
# B022 F014 fixing-round 4 — load the systemd EnvironmentFile first so
# alembic sees the production WORKBENCH_DB_URL
# (sqlite:////var/lib/workbench/db/workbench.db). Without this, Settings
# falls back to DEFAULT_DEV_DB_URL = "sqlite:///./workbench-dev.db",
# which created a per-release scratch DB inside ${RELEASE_DIR}/backend/
# that was thrown away on the next deploy; the real prod DB was never
# migrated and B022 routes hit "no such table: snapshot_meta /
# backlog_entry" at runtime (Codex round-3 reverification surfaced the
# OperationalError via /api/debug/recent-errors). The systemd service
# itself does load the same file via EnvironmentFile=, so the running
# backend always saw the correct URL — the bug was purely in this
# deploy-time alembic invocation. `set -a` + source + `set +a` puts the
# variables into the environment of the alembic subprocess only.
ENV_FILE="${WORKBENCH_ENV_FILE:-/etc/workbench/workbench.env}"
if [[ -r "${ENV_FILE}" ]]; then
  echo "→ loading env from ${ENV_FILE} for alembic"
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
  # B048-OPS1 F001 — root-cause guard for Finding #1. A *readable* env file
  # is the production path; if WORKBENCH_DB_URL is still unset after sourcing
  # it, the env file is missing the key and alembic would silently migrate
  # the DEFAULT_DEV_DB_URL scratch DB instead of prod (exactly the B022 F014
  # regression — and a likely cause of prod stalling at an old revision).
  # Fail LOUDLY here rather than migrate the wrong DB + skip the schema check.
  if [[ -z "${WORKBENCH_DB_URL:-}" ]]; then
    echo "::error::${ENV_FILE} is readable but WORKBENCH_DB_URL is unset after sourcing it." >&2
    echo "  alembic would migrate the DEFAULT_DEV_DB_URL scratch DB, not prod." >&2
    echo "  Add WORKBENCH_DB_URL=sqlite:////var/lib/workbench/db/workbench.db to the" >&2
    echo "  env file (re-run the bootstrap-env workflow) and redeploy." >&2
    exit 71
  fi
else
  echo "  warning: ${ENV_FILE} not readable; alembic will use DEFAULT_DEV_DB_URL" >&2
fi

# B027 F001 — Tiingo Starter API key pre-flight. The TiingoSnapshotLoader
# constructor raises a RuntimeError at first call when the key is missing,
# which would only surface long after the service is back up. Failing the
# deploy here makes the misconfiguration visible immediately instead of
# at strategy run-time. The key lives in the GitHub repo secret
# TIINGO_API_KEY → systemd EnvironmentFile path; tolerate empty during the
# dev `deploy.sh` rehearsal (WORKBENCH_ENV_FILE unset) so a contributor
# without a Tiingo account can still smoke this script locally.
if [[ -r "${ENV_FILE}" ]] && [[ -z "${TIINGO_API_KEY:-}" ]]; then
  echo "✗ TIINGO_API_KEY is missing from ${ENV_FILE}. The Tiingo adapter " >&2
  echo "  (workbench_api/data/tiingo_loader.py) cannot start without it. " >&2
  echo "  Configure the TIINGO_API_KEY repo secret (Settings → Secrets and " >&2
  echo "  variables → Actions) and re-run the deploy workflow so the env " >&2
  echo "  file is rewritten." >&2
  exit 66
fi

# B029 F001 — SEC EDGAR contact email pre-flight (永久边界 (h);
# https://www.sec.gov/os/accessing-edgar-data). The SEC enforces a
# fair-access policy that bans IPs lacking a valid User-Agent header
# with a contact email for 30 days. The SECEDGARFundamentalsLoader
# constructor raises a RuntimeError at first call when the env var is
# missing — failing the deploy here makes the misconfiguration visible
# immediately instead of at the next fundamentals fetch. Tolerate empty
# during the dev `deploy.sh` rehearsal (WORKBENCH_ENV_FILE unset) so a
# contributor without an SEC EDGAR config can still smoke this locally.
if [[ -r "${ENV_FILE}" ]] && [[ -z "${SEC_EDGAR_CONTACT_EMAIL:-}" ]]; then
  echo "✗ SEC_EDGAR_CONTACT_EMAIL is missing from ${ENV_FILE}. The SEC " >&2
  echo "  EDGAR adapter (workbench_api/data/sec_edgar_loader.py) cannot " >&2
  echo "  start without a valid contact email in the User-Agent header — " >&2
  echo "  SEC bans non-conforming IPs for 30 days. Configure the " >&2
  echo "  SEC_EDGAR_CONTACT_EMAIL repo secret (Settings → Secrets and " >&2
  echo "  variables → Actions) with a research-only mailbox and re-run " >&2
  echo "  the deploy workflow so the env file is rewritten." >&2
  exit 67
fi

# B031 F001 — aigc-gateway API key pre-flight (Stream 3.A / Phase 2
# starting infra). The LLMGateway constructor
# (workbench_api/llm/gateway.py) raises a RuntimeError at first call
# when the key is missing — failing the deploy here makes the
# misconfiguration visible immediately instead of at the first LLM
# call inside an AI advisor endpoint (B036+). Same shape as TIINGO_
# API_KEY (B027) and SEC_EDGAR_CONTACT_EMAIL (B029): tolerate empty
# during the dev `deploy.sh` rehearsal (WORKBENCH_ENV_FILE unset) so
# a contributor without aigc-gateway access can still smoke this
# script locally. Permanent boundary (l) routing + (m) cost cap are
# enforced inside the gateway code regardless of this check.
if [[ -r "${ENV_FILE}" ]] && [[ -z "${AIGC_GATEWAY_API_KEY:-}" ]]; then
  echo "✗ AIGC_GATEWAY_API_KEY is missing from ${ENV_FILE}. The LLM " >&2
  echo "  gateway (workbench_api/llm/gateway.py) cannot start without " >&2
  echo "  a backend-scoped key. Configure the AIGC_GATEWAY_API_KEY " >&2
  echo "  repo secret (Settings → Secrets and variables → Actions); " >&2
  echo "  generate one via mcp__aigc-gateway__create_api_key or the " >&2
  echo "  aigc-gateway dashboard, then re-run the bootstrap-env " >&2
  echo "  workflow so the env file is rewritten." >&2
  exit 68
fi

# B035 F001 — FRED API key pre-flight (Stream 2.C / market context). The
# FREDMarketLoader constructor raises when the key is missing; failing the
# deploy here surfaces the misconfiguration immediately instead of at the
# first market-context timer fetch. Same shape as TIINGO/SEC/AIGC: tolerate
# empty during the dev `deploy.sh` rehearsal (env file unset) so a
# contributor without a FRED key can still smoke this script locally.
if [[ -r "${ENV_FILE}" ]] && [[ -z "${FRED_API_KEY:-}" ]]; then
  echo "✗ FRED_API_KEY is missing from ${ENV_FILE}. The market-context " >&2
  echo "  FRED loader (workbench_api/data/fred_loader.py) cannot fetch " >&2
  echo "  macro series without a key. Configure the FRED_API_KEY repo " >&2
  echo "  secret (Settings → Secrets and variables → Actions); get a free " >&2
  echo "  key at https://fred.stlouisfed.org/docs/api/api_key.html, then " >&2
  echo "  re-run the bootstrap-env workflow so the env file is rewritten." >&2
  exit 69
fi

# B035 F001 — Alpha Vantage API key pre-flight (Stream 2.C / market
# context). The AlphaVantageLoader constructor raises when the key is
# missing. Same tolerate-empty-in-dev shape as above.
if [[ -r "${ENV_FILE}" ]] && [[ -z "${ALPHAVANTAGE_API_KEY:-}" ]]; then
  echo "✗ ALPHAVANTAGE_API_KEY is missing from ${ENV_FILE}. The market- " >&2
  echo "  context Alpha Vantage loader (workbench_api/data/alpha_vantage_" >&2
  echo "  loader.py) cannot fetch index quotes without a key. Configure " >&2
  echo "  the ALPHAVANTAGE_API_KEY repo secret (Settings → Secrets and " >&2
  echo "  variables → Actions); get a free key at " >&2
  echo "  https://www.alphavantage.co/support/#api-key, then re-run the " >&2
  echo "  bootstrap-env workflow so the env file is rewritten." >&2
  exit 70
fi

echo "→ alembic upgrade head"
(
  cd "${RELEASE_DIR}/backend"
  "${VENV_PYTHON}" -m alembic upgrade head
)

# 2a. B048-OPS1 F001 — assert alembic actually reached head on the DB it
# migrated (core durable defense). This turns the Finding #1 silent failure
# (prod stalled at 0006, missing 0007-0011) into a LOUD deploy failure: if
# the DB's current revision != the migration tree's head, emit `::error::`
# and exit 1. Reads the URL from the same Settings model alembic's env.py
# uses, so it checks exactly the DB that was just migrated. Idempotent +
# read-only (no migration side effects).
echo "→ asserting alembic at head (B048-OPS1)"
(
  cd "${RELEASE_DIR}/backend"
  "${VENV_PYTHON}" - <<'PY'
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from workbench_api.settings import get_settings

url = get_settings().WORKBENCH_DB_URL
cfg = Config("alembic.ini")
cfg.set_main_option("script_location", "workbench_api/db/migrations")
heads = set(ScriptDirectory.from_config(cfg).get_heads())
engine = create_engine(url)
with engine.connect() as conn:
    current = set(MigrationContext.configure(conn).get_current_heads())
if current != heads:
    print(
        f"::error::alembic NOT at head after upgrade: current={sorted(current)} "
        f"heads={sorted(heads)} db={url}. Migrations did not apply to this DB.",
        file=sys.stderr,
    )
    sys.exit(1)
print(f"  ✓ alembic at head {sorted(heads)} (db={url})")
PY
)

# 2b. Post-alembic safety check — assert the workbench tables exist in
# the DB alembic just migrated. Catches future regressions where the
# env file silently changes path or WORKBENCH_DB_URL drifts to a wrong
# location. Reads WORKBENCH_DB_URL from the env we just sourced.
#
# B023 F001 (v0.9.25 #1b enforcement): the `required` set now lists
# 6 tables — the 3 B021/B022 tables plus the 3 B023 execution-workflow
# tables (order_ticket / fill_journal_entry / account_snapshot). Any
# migration drift that leaves the schema short of these 6 tables fails
# the deploy here, before the symlink flip + service restart.
if [[ -n "${WORKBENCH_DB_URL:-}" ]]; then
  echo "→ verifying schema (B021/B022/B023 + B034-B048 incl. price_history + B047 backtest_run/investment_report + B047-OPS2 backtest_data_window)"
  "${VENV_PYTHON}" - <<'PY'
import os
import sys

from sqlalchemy import create_engine, inspect

url = os.environ["WORKBENCH_DB_URL"]
engine = create_engine(url)
present = set(inspect(engine).get_table_names())
required = {
    "account",
    "backlog_entry",
    "snapshot_meta",
    "order_ticket",
    "fill_journal_entry",
    "account_snapshot",
    "tiingo_budget_log",
    # B048-OPS1 F001 — the 0007-0011 era tables prod was missing in
    # Finding #1 (alembic stalled at 0006). Listing them here makes a short
    # schema fail the deploy concretely (belt-and-suspenders to the
    # alembic==head assert above).
    "market_context_observation",
    "advisor_recommendation",
    "price_snapshot",
    "recommendation_snapshot",
    "price_history",
    # B047-OPS1 F001 — Finding C backstop. The B047 backtest infra added
    # 0012 backtest_run (on-demand queue) + 0013 investment_report (the
    # canonical Reports page source). If the deploy chain never ran B047's
    # migrations, prod is missing these two tables and the canonical report
    # generator / Reports page silently surface nothing — fail the deploy
    # concretely here (belt-and-suspenders to the alembic==head assert above).
    "backtest_run",
    "investment_report",
    # B047-OPS2 F001 — 0014 backtest_data_window (the data-coverage window the
    # request-path GET /api/backtests/data-range reads so the frontend picks a
    # valid default range). A short schema here means the backtest page falls
    # back to the empty state — fail the deploy concretely.
    "backtest_data_window",
}
missing = required - present
if missing:
    print(f"  ✗ schema check FAILED: missing tables {sorted(missing)} in {url}", file=sys.stderr)
    sys.exit(1)
print(f"  ✓ schema check passed: {sorted(required)} present in {url}")
PY
fi

# B058 F002 — prime price_snapshot with the current strategy target universe
# right after deploy, so the paper mark source is fresh IMMEDIATELY instead of
# waiting for the next daily workbench-prices timer fire. Without this, the
# window between a deploy (especially one that changes the priced universe, like
# B058 adding the regime ETFs + equities) and the next timer run leaves the
# manual "align to current target" + regime forward-validation flows skipping
# every not-yet-priced target (the user sees "X 个目标缺市价未建仓"). The env
# file sourced above provides WORKBENCH_DB_URL + TIINGO_API_KEY. Best-effort and
# NON-FATAL: a Tiingo blip / missing key / dev rehearsal must NEVER fail the
# deploy — the daily timer still backfills, and the paper engine self-heals
# (build_complete stays False → the daily MTM job retries once priced).
if [[ -n "${WORKBENCH_DB_URL:-}" ]]; then
  echo "→ priming price_snapshot (prices.cli fetch — held ∪ target universe; best-effort)"
  # Run from the new release's backend dir so workbench_api resolves from the
  # release SOURCE tree — the SAME context the alembic step above uses (the venv
  # provides dependencies, not the app package). Without the cd, `python -m
  # workbench_api.prices.cli` fails with ModuleNotFoundError before the symlink
  # flip. The subshell keeps the main shell's cwd unchanged.
  if ( cd "${RELEASE_DIR}/backend" && "${VENV_PYTHON}" -m workbench_api.prices.cli fetch ); then
    echo "  ✓ price_snapshot primed"
  else
    echo "::warning::price_snapshot prime failed (Tiingo / key / network). The daily workbench-prices timer will populate it on its next run; paper align skips unpriced targets and the MTM job retries once priced." >&2
  fi
else
  echo "→ skip price_snapshot prime (WORKBENCH_DB_URL unset — dev rehearsal)"
fi

# B033 F004 — provision the news snapshot directory (永久边界 (p) + (q)).
# News raw filing / article bodies land here (boundary (p): the `news`
# table stores only metadata + snapshot_path + content_sha256; the bodies
# live on disk). Those bodies must survive release swaps + the 30-day
# release GC, so the canonical location is the persistent data root next
# to the SQLite DB (/var/lib/workbench/), NOT the ephemeral release tree.
# We create the directory EMPTY and never invoke the news ingest
# entrypoint here — B033 keeps news ingest manual-trigger only
# (boundary (q): no cron / scheduler / systemd unit). F004 L2 acceptance
# §8 asserts the directory exists and is empty.
#
# A symlink exposes the same persistent directory at the release-relative
# `data/snapshots/news` path so any repo-root-relative resolution (e.g.
# the CLI's DEFAULT_SNAPSHOT_ROOT) lands on the persistent store rather
# than writing into the release tree that the next deploy discards.
NEWS_SNAPSHOT_DIR="${WORKBENCH_NEWS_SNAPSHOT_DIR:-/var/lib/workbench/data/snapshots/news}"
echo "→ ensure news snapshot dir ${NEWS_SNAPSHOT_DIR} (empty; no ingest)"
mkdir -p "${NEWS_SNAPSHOT_DIR}"
mkdir -p "${RELEASE_DIR}/data/snapshots"
ln -sfn "${NEWS_SNAPSHOT_DIR}" "${RELEASE_DIR}/data/snapshots/news"

# B035 F002 — provision the market-context snapshot directory (boundary (r):
# read-only market-data fetch). Raw FRED / Alpha Vantage responses land here
# (same snapshot foundation as news); they must survive release swaps + GC,
# so the canonical location is the persistent data root next to the SQLite
# DB. The market-context systemd timer writes here via
# WORKBENCH_MARKET_SNAPSHOT_DIR; a symlink also exposes it at the
# release-relative path for the CLI's repo-relative default.
MARKET_SNAPSHOT_DIR="${WORKBENCH_MARKET_SNAPSHOT_DIR:-/var/lib/workbench/data/snapshots/market-context}"
echo "→ ensure market-context snapshot dir ${MARKET_SNAPSHOT_DIR}"
mkdir -p "${MARKET_SNAPSHOT_DIR}"
ln -sfn "${MARKET_SNAPSHOT_DIR}" "${RELEASE_DIR}/data/snapshots/market-context"

# 2. Flip the active release symlink atomically. `ln -sfn` is one syscall
# and survives the brief window where both services are reading from the
# directory.
echo "→ symlink ${CURRENT_LINK} → ${RELEASE_DIR}"
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

# 3. Restart both workbench services. The deploy user's sudoers grant
# (B021 prep #3) whitelists each service name individually, so we MUST
# call systemctl restart once per service. A single combined call
# (`systemctl restart backend frontend`) doesn't match any sudoers rule
# and falls through to "password required".
echo "→ systemctl daemon-reload + restart workbench-{backend,frontend}.service"
sudo /bin/systemctl daemon-reload
sudo /bin/systemctl restart workbench-backend.service
sudo /bin/systemctl restart workbench-frontend.service

# B037-OPS1 — install + enable EVERY shipped workbench-*.timer (boundary (r):
# read-only data fetch — market-context / prices — plus the CI-safety-gated
# advisor precompute; NEVER trade execution / broker / order). The unit files
# ship in the release at ${SYSTEMD_SRC} (workbench/deploy/systemd/ → top-level
# systemd/). This single DRY loop replaces the per-timer hardcoded blocks that
# B035/B036/B037 each appended — a new timer (B038+) is now picked up
# automatically with zero deploy.sh changes.
#
# The sudo grant that makes this succeed lives in the versioned artifact
# workbench/deploy/sudoers/deploy-workbench. Installs go through the root-owned
# wrapper /usr/local/bin/workbench-install-unit (security-reviewer tightening,
# B037-OPS1 §5.1: the wrapper rejects path-separators in the unit name so the
# sudoers fnmatch `*`-matches-`/` traversal class is impossible). Apply the
# sudoers drop-in + install the wrapper once on the VM so this loop stops
# warning (see docs/dev/B021-vm-setup-runbook.md).
#
# Best-effort: a dev `deploy.sh` rehearsal (no sudo / units absent) or a
# not-yet-granted sudoers entry still lets the backend/frontend deploy
# complete. Codex F002 L2 verifies `systemctl is-enabled` for each timer; if
# this loop warned, apply the sudoers artifact + re-deploy. Bash 3.2: a glob
# with no match stays literal, so we guard each path with `[[ -e ... ]]`.
INSTALL_UNIT=/usr/local/bin/workbench-install-unit
SYSTEMD_SRC="${RELEASE_DIR}/systemd"
if [[ -d "${SYSTEMD_SRC}" ]]; then
  for timer_path in "${SYSTEMD_SRC}"/workbench-*.timer; do
    [[ -e "${timer_path}" ]] || continue
    timer_unit=$(basename "${timer_path}")
    service_unit="${timer_unit%.timer}.service"
    service_path="${SYSTEMD_SRC}/${service_unit}"
    if [[ ! -f "${service_path}" ]]; then
      echo "::warning::${timer_unit} has no sibling ${service_unit} in the release; skipping (a timer needs its oneshot service)." >&2
      continue
    fi
    echo "→ install + enable ${timer_unit} (boundary (r) read-only / advisor precompute)"
    if sudo "${INSTALL_UNIT}" "${service_path}" "${service_unit}" \
      && sudo "${INSTALL_UNIT}" "${timer_path}" "${timer_unit}" \
      && sudo /bin/systemctl daemon-reload \
      && sudo /bin/systemctl enable --now "${timer_unit}"; then
      echo "✓ ${timer_unit} enabled"
    else
      echo "::warning::Could not install/enable ${timer_unit}. Apply the versioned sudoers artifact workbench/deploy/sudoers/deploy-workbench to /etc/sudoers.d/deploy-workbench AND install workbench/deploy/sudoers/workbench-install-unit to /usr/local/bin/workbench-install-unit (root:root 0755), then re-deploy (B037-OPS1). Deploy continues; this timer will not run until granted." >&2
    fi
  done

  # B047 F002 — long-running DAEMON worker services (workbench-*-worker.service):
  # unlike the timer oneshots above these have no sibling .timer, so they are
  # install + enable --now + restart directly. The deploy-workbench sudoers
  # grants `enable --now` / `restart` for workbench-*-worker.service.
  for worker_path in "${SYSTEMD_SRC}"/workbench-*-worker.service; do
    [[ -e "${worker_path}" ]] || continue
    worker_unit=$(basename "${worker_path}")
    echo "→ install + enable + restart ${worker_unit} (boundary (r) read-only backtest daemon)"
    if sudo "${INSTALL_UNIT}" "${worker_path}" "${worker_unit}" \
      && sudo /bin/systemctl daemon-reload \
      && sudo /bin/systemctl enable --now "${worker_unit}" \
      && sudo /bin/systemctl restart "${worker_unit}"; then
      echo "✓ ${worker_unit} enabled + restarted"
    else
      echo "::warning::Could not install/enable ${worker_unit}. Apply the versioned sudoers artifact workbench/deploy/sudoers/deploy-workbench (now includes enable/restart for workbench-*-worker.service) to /etc/sudoers.d/deploy-workbench, then re-deploy. Deploy continues; the backtest worker will not run until granted." >&2
    fi
  done

  # B047-OPS1 F001 — post-step assert the intended end-state (§12.11): an
  # install/enable command returning 0 does NOT prove the unit ended up
  # active/enabled. The on-demand backtest worker must be ACTIVE and the
  # canonical-report timer ENABLED after deploy. We WARN (not hard-fail) because
  # the one-time sudoers application may still be pending on a fresh VM — F002
  # L2 confirms the end-state on the real machine. `is-active` / `is-enabled`
  # are read-only and need no sudo.
  WORKER_UNIT="workbench-backtest-worker.service"
  if [[ -e "${SYSTEMD_SRC}/${WORKER_UNIT}" ]]; then
    if systemctl is-active --quiet "${WORKER_UNIT}"; then
      echo "✓ ${WORKER_UNIT} is active"
    else
      echo "::warning::${WORKER_UNIT} is NOT active after deploy (state: $(systemctl is-active "${WORKER_UNIT}" 2>/dev/null || echo unknown)). Apply the deploy-workbench sudoers artifact + re-deploy; the on-demand backtest queue will not drain until it runs (B047-OPS1)." >&2
    fi
  fi
  CANONICAL_TIMER="workbench-canonical-backtest.timer"
  if [[ -e "${SYSTEMD_SRC}/${CANONICAL_TIMER}" ]]; then
    if systemctl is-enabled --quiet "${CANONICAL_TIMER}"; then
      echo "✓ ${CANONICAL_TIMER} is enabled"
    else
      echo "::warning::${CANONICAL_TIMER} is NOT enabled after deploy (state: $(systemctl is-enabled "${CANONICAL_TIMER}" 2>/dev/null || echo unknown)). Apply the deploy-workbench sudoers artifact + re-deploy; canonical investment reports will not regenerate on schedule (B047-OPS1)." >&2
    fi
  fi
fi

echo "✓ deploy complete: ${RELEASE_DIR}"
