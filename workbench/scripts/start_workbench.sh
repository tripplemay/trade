#!/usr/bin/env bash
# Boot the workbench backend (FastAPI on 127.0.0.1:8723) and frontend
# (Next.js dev server on 127.0.0.1:3000) concurrently, streaming both logs to
# stdout. Ctrl-C terminates both children.
#
# Prereqs (see workbench/README.md for the full list):
#   - .venv with `workbench/backend[dev]` installed (project-root .venv).
#   - `npm install` already run inside `workbench/frontend/`.
#
# B020 binds backend to 127.0.0.1 only by design. Cloud binding (0.0.0.0
# behind nginx + OAuth) is B021's concern.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKBENCH_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${WORKBENCH_DIR}/.." && pwd)"

BACKEND_HOST="${WORKBENCH_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${WORKBENCH_BACKEND_PORT:-8723}"
FRONTEND_PORT="${WORKBENCH_FRONTEND_PORT:-3000}"

VENV_PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${VENV_PY}" ]]; then
  echo "error: ${VENV_PY} not found. Create a Python 3.11 venv and install workbench backend:" >&2
  echo "  python3.11 -m venv .venv" >&2
  echo "  .venv/bin/pip install -e workbench/backend[dev]" >&2
  exit 1
fi

if [[ ! -d "${WORKBENCH_DIR}/frontend/node_modules" ]]; then
  echo "error: workbench/frontend/node_modules missing. Run 'npm install --prefix workbench/frontend' first." >&2
  exit 1
fi

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "${WORKBENCH_DIR}/backend"
  exec "${VENV_PY}" -m uvicorn workbench_api.app:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --reload
) &
pids+=("$!")

(
  cd "${WORKBENCH_DIR}/frontend"
  exec npm run dev -- --port "${FRONTEND_PORT}"
) &
pids+=("$!")

echo "workbench backend  → http://${BACKEND_HOST}:${BACKEND_PORT}/api/health"
echo "workbench frontend → http://127.0.0.1:${FRONTEND_PORT}/"
echo "Ctrl-C to stop both."

# Wait until either child exits, then let the EXIT trap tear down the survivor.
# We poll instead of using `wait -n`, which is Bash 4.3+ only — macOS ships
# GNU bash 3.2.57 as /bin/bash, and `wait -n` aborts with "invalid option"
# there. The 1-second cadence is fine for a dev-time boot script.
while :; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      exit 0
    fi
  done
  sleep 1
done
