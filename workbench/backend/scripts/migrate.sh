#!/usr/bin/env bash
# Run Alembic against the workbench DB.
#
# Usage:
#   bash workbench/backend/scripts/migrate.sh           # upgrade head (default)
#   bash workbench/backend/scripts/migrate.sh downgrade -1
#
# Environment overrides (all optional):
#   PYTHON_BIN         path to a Python 3.11 interpreter (default: repo .venv/bin/python)
#   WORKBENCH_DB_URL   SQLAlchemy URL — defaults to ./workbench-dev.db in this script's CWD
#
# Bash 3.2 compatible (no `wait -n`, no `mapfile`, no `${var^^}`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/../.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "error: PYTHON_BIN=${PYTHON_BIN} not executable." >&2
  echo "  Install workbench backend into a Python 3.11 venv:" >&2
  echo "    python3.11 -m venv .venv && .venv/bin/pip install -e workbench/backend[dev]" >&2
  exit 1
fi

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}:${PYTHONPATH:-}"

if [[ $# -eq 0 ]]; then
  exec "${PYTHON_BIN}" -m alembic upgrade head
fi

exec "${PYTHON_BIN}" -m alembic "$@"
