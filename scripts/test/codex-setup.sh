#!/usr/bin/env bash
# Codex test environment setup — workbench backend + frontend in foreground PTY.
#
# Codex 沙箱不支持 `&` / `nohup` / `disown` 后台启动。本脚本必须在持久 PTY
# 会话中前台运行（一个 shell 跑这个，另一个 shell 跑 codex-wait.sh 等就绪）。
#
# Codex 启动顺序：
#   终端 1：bash scripts/test/codex-setup.sh
#   终端 2：bash scripts/test/codex-wait.sh
#
# 行为：
#   1. 检查 venv + frontend deps 已安装（不自动 install — Codex 不应改依赖）
#   2. 并发启动 workbench backend (uvicorn 127.0.0.1:8723) + frontend (next dev 3000)
#   3. 两个 child 日志合并 stdout
#   4. Ctrl-C / SIGTERM → trap cleanup → 同时 kill 两个 child + 等待退出
#
# 与 workbench/scripts/start_workbench.sh 的差异：本脚本明确为 Codex 沙箱设计，
# 假设调用者从 repo 根运行（不是 workbench/ 内部）。失败 fail-loud：缺 venv 或
# 缺 frontend deps 不自动修复。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKBENCH_DIR="${REPO_ROOT}/workbench"

VENV_PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${VENV_PY}" ]]; then
  echo "error: ${VENV_PY} not found." >&2
  echo "Run from repo root: python3.11 -m venv .venv && .venv/bin/pip install -e workbench/backend[dev]" >&2
  exit 1
fi

# Fail-fast: the .venv must satisfy every runtime dependency declared
# in workbench/backend/pyproject.toml. A stale .venv that was last
# populated before a new dep landed (e.g. B023 F008 blocker: missing
# python-multipart after the F004 multipart upload route shipped)
# silently lets the venv check above pass but crashes uvicorn at
# import time. Importing the FastAPI app surfaces any such gap in a
# single subprocess; non-zero → bail with the precise remediation
# instead of the cryptic stacktrace 2 seconds into uvicorn startup.
echo "[codex-setup] verifying backend imports under .venv…"
if ! (cd "${WORKBENCH_DIR}/backend" && "${VENV_PY}" -c "import workbench_api.app  # noqa: F401" 2>&1); then
  echo "error: backend import probe failed — the .venv is missing a declared dependency." >&2
  echo "Re-sync the venv to match workbench/backend/pyproject.toml:" >&2
  echo "  ${REPO_ROOT}/.venv/bin/pip install -e workbench/backend[dev]" >&2
  exit 1
fi

if [[ ! -d "${WORKBENCH_DIR}/frontend/node_modules" ]]; then
  echo "error: ${WORKBENCH_DIR}/frontend/node_modules not found." >&2
  echo "Run: (cd workbench/frontend && npm ci)" >&2
  exit 1
fi

BACKEND_PORT="${WORKBENCH_BACKEND_PORT:-8723}"
FRONTEND_PORT="${WORKBENCH_FRONTEND_PORT:-3000}"

# Pre-flight: refuse to overlap if port already bound (another instance running)
for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  if (echo > "/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1; then
    echo "error: 127.0.0.1:${port} already bound. Stop the existing process first." >&2
    exit 1
  fi
done

cleanup() {
  echo "[codex-setup] received signal — terminating children"
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "${BACKEND_PID}" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "${FRONTEND_PID}" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  echo "[codex-setup] cleanup complete"
}
trap cleanup EXIT INT TERM

echo "[codex-setup] starting backend on 127.0.0.1:${BACKEND_PORT}..."
(
  cd "${WORKBENCH_DIR}/backend"
  exec "${VENV_PY}" -m uvicorn workbench_api.app:app \
    --host 127.0.0.1 --port "${BACKEND_PORT}" 2>&1 | sed -u 's/^/[backend] /'
) &
BACKEND_PID=$!

echo "[codex-setup] starting frontend on 127.0.0.1:${FRONTEND_PORT}..."
(
  cd "${WORKBENCH_DIR}/frontend"
  exec env PORT="${FRONTEND_PORT}" HOSTNAME=127.0.0.1 npx next dev 2>&1 | sed -u 's/^/[frontend] /'
) &
FRONTEND_PID=$!

echo "[codex-setup] backend pid=${BACKEND_PID} + frontend pid=${FRONTEND_PID}"
echo "[codex-setup] in a second shell: bash scripts/test/codex-wait.sh"
echo "[codex-setup] Ctrl-C to stop both"

# Wait loop (Bash 3.2 compatible — no wait -n)
while kill -0 "${BACKEND_PID}" 2>/dev/null && kill -0 "${FRONTEND_PID}" 2>/dev/null; do
  sleep 2
done

echo "[codex-setup] one child exited; stopping the other"
exit 1
