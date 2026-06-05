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
  exec "${VENV_PYTHON}" -m alembic upgrade head
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
  echo "→ verifying schema (account / backlog_entry / snapshot_meta / order_ticket / fill_journal_entry / account_snapshot / tiingo_budget_log)"
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
}
missing = required - present
if missing:
    print(f"  ✗ schema check FAILED: missing tables {sorted(missing)} in {url}", file=sys.stderr)
    sys.exit(1)
print(f"  ✓ schema check passed: {sorted(required)} present in {url}")
PY
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

# B035 F002 — install + enable the market-context daily timer (boundary (r):
# read-only market-data fetch only; systemd timer, NOT an in-process
# scheduler). The unit files ship in the release under deploy/systemd/.
# Best-effort: tolerate a dev `deploy.sh` rehearsal (no sudo / units absent)
# and a not-yet-granted sudoers entry so an existing backend/frontend deploy
# still completes. Codex F004 L2 verifies `systemctl status` shows the timer
# enabled; if this block warned, add the sudoers grant + re-deploy.
SYSTEMD_SRC="${RELEASE_DIR}/systemd"
if [[ -f "${SYSTEMD_SRC}/workbench-market-context.timer" ]]; then
  echo "→ install + enable workbench-market-context.timer (boundary (r) read-only fetch)"
  if sudo /usr/bin/install -m 644 "${SYSTEMD_SRC}/workbench-market-context.service" /etc/systemd/system/workbench-market-context.service \
    && sudo /usr/bin/install -m 644 "${SYSTEMD_SRC}/workbench-market-context.timer" /etc/systemd/system/workbench-market-context.timer \
    && sudo /bin/systemctl daemon-reload \
    && sudo /bin/systemctl enable --now workbench-market-context.timer; then
    echo "✓ workbench-market-context.timer enabled"
  else
    echo "::warning::Could not install/enable workbench-market-context.timer. Grant the deploy user sudoers access to '/usr/bin/install -m 644 * /etc/systemd/system/workbench-market-context.*' and '/bin/systemctl enable --now workbench-market-context.timer', then re-deploy (B035 F002). Deploy continues; the daily market-context fetch will not run until granted." >&2
  fi
fi

# B036 F002 — install + enable the AI advisor daily timer (boundary (r) as
# revised: CI-safety-gated advisor precompute, never trade execution). Same
# best-effort shape as the market timer.
if [[ -f "${SYSTEMD_SRC}/workbench-advisor.timer" ]]; then
  echo "→ install + enable workbench-advisor.timer (boundary (r) advisor precompute)"
  if sudo /usr/bin/install -m 644 "${SYSTEMD_SRC}/workbench-advisor.service" /etc/systemd/system/workbench-advisor.service \
    && sudo /usr/bin/install -m 644 "${SYSTEMD_SRC}/workbench-advisor.timer" /etc/systemd/system/workbench-advisor.timer \
    && sudo /bin/systemctl daemon-reload \
    && sudo /bin/systemctl enable --now workbench-advisor.timer; then
    echo "✓ workbench-advisor.timer enabled"
  else
    echo "::warning::Could not install/enable workbench-advisor.timer. Grant the deploy user sudoers access to '/usr/bin/install -m 644 * /etc/systemd/system/workbench-advisor.*' and '/bin/systemctl enable --now workbench-advisor.timer', then re-deploy (B036 F002). Deploy continues; the daily advisor precompute will not run until granted." >&2
  fi
fi

echo "✓ deploy complete: ${RELEASE_DIR}"
