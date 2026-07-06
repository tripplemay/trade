#!/bin/sh
# 铁律 #11 — state-machine JSON validation before every commit.
# Installed 2026-07-06 (B098 F002 concurrent-write race lesson). Local-only
# (.git/hooks not tracked); re-install after fresh clone:
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
"$PY" scripts/check_state_json.py || exit 1
