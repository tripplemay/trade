#!/usr/bin/env bash
# Codex test environment wait — block until backend + frontend health endpoints
# are reachable, then exit 0. Use in second shell after codex-setup.sh.
#
# 用法：
#   终端 1：bash scripts/test/codex-setup.sh   # 前台跑两个 service
#   终端 2：bash scripts/test/codex-wait.sh    # 这里 — wait until ready，然后开始测试

set -euo pipefail

BACKEND_URL="http://127.0.0.1:${WORKBENCH_BACKEND_PORT:-8723}/api/health"
FRONTEND_URL="http://127.0.0.1:${WORKBENCH_FRONTEND_PORT:-3000}/"
MAX_WAIT_SECONDS="${CODEX_WAIT_TIMEOUT:-120}"
POLL_INTERVAL=2

echo "[codex-wait] backend ${BACKEND_URL}"
echo "[codex-wait] frontend ${FRONTEND_URL}"
echo "[codex-wait] timeout ${MAX_WAIT_SECONDS}s"

start=$(date +%s)
backend_ready=0
frontend_ready=0
while true; do
  now=$(date +%s)
  elapsed=$((now - start))

  if [[ "${elapsed}" -ge "${MAX_WAIT_SECONDS}" ]]; then
    echo "[codex-wait] TIMEOUT after ${elapsed}s — backend_ready=${backend_ready} frontend_ready=${frontend_ready}"
    exit 1
  fi

  if [[ "${backend_ready}" -eq 0 ]]; then
    if curl -sS --max-time 3 -o /dev/null -w "%{http_code}" "${BACKEND_URL}" 2>/dev/null | grep -q "^200$"; then
      backend_ready=1
      echo "[codex-wait] backend READY at +${elapsed}s"
    fi
  fi

  if [[ "${frontend_ready}" -eq 0 ]]; then
    HTTP_CODE=$(curl -sS --max-time 3 -o /dev/null -w "%{http_code}" "${FRONTEND_URL}" 2>/dev/null || echo "000")
    # Frontend can return 200 (home) or 307/302 (redirect to /login) — both = ready
    case "${HTTP_CODE}" in
      200|301|302|307) frontend_ready=1; echo "[codex-wait] frontend READY (HTTP ${HTTP_CODE}) at +${elapsed}s" ;;
    esac
  fi

  if [[ "${backend_ready}" -eq 1 && "${frontend_ready}" -eq 1 ]]; then
    echo "[codex-wait] both services ready at +${elapsed}s — proceed with tests"
    exit 0
  fi

  sleep "${POLL_INTERVAL}"
done
