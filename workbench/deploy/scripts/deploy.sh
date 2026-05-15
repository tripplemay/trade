#!/usr/bin/env bash
# Workbench deploy step — runs on the VM as the `deploy` user.
#
# Argument: the absolute path to the newly-SCP'd release directory under
# /srv/workbench/releases/<sha>/. CI (B021 F004 workbench-deploy.yml) calls
# this script via SSH after the SCP step lands the artifacts.
#
# Side effects (in order):
#   1. Run `alembic upgrade head` against WORKBENCH_DB_URL (idempotent).
#   2. Atomically flip /srv/workbench/current symlink to the new release.
#   3. systemctl restart workbench-backend.service workbench-frontend.service.
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

if [[ ! -d "${RELEASE_DIR}" ]]; then
  echo "error: release dir not found: ${RELEASE_DIR}" >&2
  exit 65
fi
if [[ ! -d "${RELEASE_DIR}/backend" ]] || [[ ! -d "${RELEASE_DIR}/frontend" ]]; then
  echo "error: release dir missing backend/ or frontend/: ${RELEASE_DIR}" >&2
  exit 65
fi

# 1. Apply pending DB migrations. The workbench is single-VM single-user so
# we do not need a separate migrate worker — applying inline is the simplest
# safe ordering (migrate before symlink flip prevents the new server code
# from hitting an older schema mid-deploy).
echo "→ alembic upgrade head"
(
  cd "${RELEASE_DIR}/backend"
  exec /opt/workbench/.venv/bin/python -m alembic upgrade head
)

# 2. Flip the active release symlink atomically. `ln -sfn` is one syscall
# and survives the brief window where both services are reading from the
# directory.
echo "→ symlink ${CURRENT_LINK} → ${RELEASE_DIR}"
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

# 3. Restart both workbench services. The deploy user's sudoers grant
# (B021 prep #3) is locked to these two unit names + daemon-reload.
echo "→ systemctl daemon-reload + restart workbench-{backend,frontend}.service"
sudo /bin/systemctl daemon-reload
sudo /bin/systemctl restart workbench-backend.service workbench-frontend.service

echo "✓ deploy complete: ${RELEASE_DIR}"
