#!/usr/bin/env bash
# Workbench rollback step — runs on the VM as the `deploy` user.
#
# Walks /srv/workbench/releases/ by mtime (newest first), skips the one
# currently pointed at by /srv/workbench/current, and flips the symlink to
# the next-newest. The two workbench services are then restarted so the
# OS sees the prior release's binaries.
#
# Called by B021 F004 workbench-deploy.yml whenever healthcheck.sh fails
# after a fresh deploy.
#
# Bash 3.2 compatible.

set -euo pipefail

WORKBENCH_ROOT="${WORKBENCH_ROOT:-/srv/workbench}"
RELEASES_DIR="${WORKBENCH_ROOT}/releases"
CURRENT_LINK="${WORKBENCH_ROOT}/current"

if [[ ! -d "${RELEASES_DIR}" ]]; then
  echo "error: ${RELEASES_DIR} does not exist; nothing to roll back to." >&2
  exit 65
fi

CURRENT_TARGET=""
if [[ -L "${CURRENT_LINK}" ]]; then
  CURRENT_TARGET="$(readlink -f "${CURRENT_LINK}")"
fi

# List release directories newest-first. `ls -1t` is portable to macOS bash 3.2
# (mapfile / readarray are 4+).
PREV_RELEASE=""
for entry in $(ls -1t "${RELEASES_DIR}" 2>/dev/null); do
  candidate="${RELEASES_DIR}/${entry}"
  if [[ ! -d "${candidate}" ]]; then
    continue
  fi
  if [[ "${candidate}" == "${CURRENT_TARGET}" ]]; then
    continue
  fi
  PREV_RELEASE="${candidate}"
  break
done

if [[ -z "${PREV_RELEASE}" ]]; then
  echo "error: no previous release found to roll back to." >&2
  exit 66
fi

echo "→ rollback: ${CURRENT_LINK} → ${PREV_RELEASE}"
ln -sfn "${PREV_RELEASE}" "${CURRENT_LINK}"

echo "→ systemctl restart workbench-{backend,frontend}.service"
sudo /bin/systemctl restart workbench-backend.service workbench-frontend.service

echo "✓ rolled back to ${PREV_RELEASE}"
