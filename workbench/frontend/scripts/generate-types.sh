#!/usr/bin/env bash
# Regenerate workbench/frontend/src/types/api.ts from the live backend
# OpenAPI schema. Idempotent: running twice on the same backend produces
# byte-identical output. CI uses `git diff --exit-code` on the produced
# file to detect drift between the backend schema and the committed types.
#
# Usage:
#   bash workbench/frontend/scripts/generate-types.sh
#
# Environment overrides (all optional):
#   PYTHON_BIN              path to a Python 3.11 interpreter (default: repo .venv/bin/python)
#   WORKBENCH_BACKEND_HOST  host backend binds to (default 127.0.0.1)
#   WORKBENCH_BACKEND_PORT  port backend binds to (default 8724 — different from
#                           the dev server's 8723 to allow concurrent local runs)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKBENCH_DIR="$(cd "${FRONTEND_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${WORKBENCH_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
BACKEND_HOST="${WORKBENCH_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${WORKBENCH_BACKEND_PORT:-8724}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
OUTPUT_FILE="${FRONTEND_DIR}/src/types/api.ts"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "error: PYTHON_BIN=${PYTHON_BIN} not executable. Install workbench/backend[dev] into a Python 3.11 venv." >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "error: npx not found on PATH. Install Node.js 20+ and run 'npm --prefix workbench/frontend install' first." >&2
  exit 1
fi

OPENAPI_JSON="$(mktemp -t workbench-openapi.XXXXXX.json)"
UVICORN_LOG="$(mktemp -t workbench-uvicorn.XXXXXX.log)"

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "${UVICORN_PID}" 2>/dev/null; then
    kill "${UVICORN_PID}" 2>/dev/null || true
    wait "${UVICORN_PID}" 2>/dev/null || true
  fi
  rm -f "${OPENAPI_JSON}" "${UVICORN_LOG}"
}
trap cleanup EXIT INT TERM

echo "→ starting backend (uvicorn workbench_api.app:app @ ${BACKEND_URL})"
(
  cd "${WORKBENCH_DIR}/backend"
  exec "${PYTHON_BIN}" -m uvicorn workbench_api.app:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --log-level warning
) >"${UVICORN_LOG}" 2>&1 &
UVICORN_PID=$!

echo "→ waiting for ${BACKEND_URL}/health (pid ${UVICORN_PID})"
ATTEMPTS=0
MAX_ATTEMPTS=60
until curl -fsS "${BACKEND_URL}/health" -o /dev/null 2>/dev/null; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if (( ATTEMPTS >= MAX_ATTEMPTS )); then
    echo "error: backend not responsive after ${MAX_ATTEMPTS} probes. Last log:" >&2
    tail -n 50 "${UVICORN_LOG}" >&2 || true
    exit 1
  fi
  if ! kill -0 "${UVICORN_PID}" 2>/dev/null; then
    echo "error: backend process died before responding. Log:" >&2
    cat "${UVICORN_LOG}" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "→ fetching ${BACKEND_URL}/openapi.json"
curl -fsS "${BACKEND_URL}/openapi.json" -o "${OPENAPI_JSON}"

echo "→ regenerating ${OUTPUT_FILE}"
(
  cd "${FRONTEND_DIR}"
  npx --no-install openapi-typescript "${OPENAPI_JSON}" -o "${OUTPUT_FILE}"
)

echo "✓ wrote $(wc -l < "${OUTPUT_FILE}" | tr -d ' ') lines to ${OUTPUT_FILE#${REPO_ROOT}/}"
