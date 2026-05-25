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

echo "✓ deploy complete: ${RELEASE_DIR}"
