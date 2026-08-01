#!/usr/bin/env python3
"""State-machine JSON validator — 铁律 #11 enforcement.

Parses the three state-machine files (progress.json / features.json /
backlog.json) and exits non-zero if any is not valid JSON. Wired into a local
``.git/hooks/pre-commit`` so a concurrent-write race (two sessions editing
progress.json → git merges a torn intermediate state) can never land an
unparseable state file on main again.

Background: 2026-07-06 (B098 F002) a planner done-phase write raced with an
evaluator signoff write; commit f2bbb1c briefly carried a progress.json whose
``session_notes.evaluator`` had a torn tail = invalid JSON on main (breach of
铁律 #11). Self-healed by 4477e7d, but the class of bug is exactly what 铁律 #11
asks a pre-commit hook to prevent. Also the MVP precedent (commit b44b789):
a missing ``}`` in a session_notes block sat on main for hours, breaking every
downstream parser.

Usage:
    python3 scripts/check_state_json.py            # validate the 3 state files
    python3 scripts/check_state_json.py a.json b   # validate specific files

Exit 0 = all valid; exit 1 = at least one invalid (message on stderr).

fix_rounds 递增门禁（B109 F003）：暂存区 progress.json 相对 HEAD 的
fix_rounds 若**递增**，仅允许发生在 status fixing→reverifying 的同一 commit
内（由 Generator +1）；evaluator 在 verifying→fixing 时加 = 双重计数，拒绝
提交。开新批次的重置（done N → building 0，fix_rounds 减小）合法放行——
历史批量实例见 v0.9.56 归档。无 HEAD（fresh clone）或文件未暂存时跳过。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# The state-machine files 铁律 #11 names. Repo-root-relative.
DEFAULT_TARGETS = ("progress.json", "features.json", "backlog.json")


def validate(paths: list[str]) -> int:
    failures: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            # A named-but-absent target is not a JSON-validity failure; skip it
            # (e.g. a fresh clone before a file is created). The 3 defaults
            # always exist in this repo, so this only matters for explicit args.
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            failures.append(f"{path}: {exc}")
    if failures:
        sys.stderr.write("✗ 状态机 JSON 校验失败（铁律 #11）：\n")
        for line in failures:
            sys.stderr.write(f"  - {line}\n")
        sys.stderr.write("commit 被拒绝——修好 JSON 再提交。\n")
        return 1
    return 0


def fix_rounds_violation(old: dict, new: dict) -> str | None:
    """纯函数：old（HEAD）→ new（staged）是否非法递增 fix_rounds。

    非法 = fix_rounds 变大，但不是「status fixing→reverifying 且恰好 +1」。
    减小（开新批次重置 done N → building 0）与不变均合法，返回 None。
    """
    old_rounds = old.get("fix_rounds", 0)
    new_rounds = new.get("fix_rounds", 0)
    if not (isinstance(old_rounds, int) and isinstance(new_rounds, int)):
        return None
    if new_rounds <= old_rounds:
        return None
    if (
        old.get("status") == "fixing"
        and new.get("status") == "reverifying"
        and new_rounds == old_rounds + 1
    ):
        return None
    return (
        f"status {old.get('status')}→{new.get('status')}，"
        f"fix_rounds {old_rounds}→{new_rounds}"
    )


def check_fix_rounds_gate() -> str | None:
    """对比暂存区与 HEAD 的 progress.json，非法递增 fix_rounds 时返回错误信息。

    无 HEAD（首个 commit 前）或 progress.json 未暂存时跳过（返回 None）；
    JSON 不可解析由 validate() 拦，本门禁不重复报。
    """
    try:
        head = subprocess.run(
            ["git", "show", "HEAD:progress.json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        staged = subprocess.run(
            ["git", "show", ":progress.json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        old = json.loads(head)
        new = json.loads(staged)
    except json.JSONDecodeError:
        return None
    detail = fix_rounds_violation(old, new)
    if detail is None:
        return None
    return (
        "✗ fix_rounds 递增门禁（B109 F003）：\n"
        f"  - 暂存区 progress.json：{detail}\n"
        "  - fix_rounds 仅允许由 Generator 在 status fixing→reverifying 的同一\n"
        "    commit 内 +1；evaluator 在 verifying→fixing 时不得加（双重计数）。\n"
        "    规则见 harness-rules.md §状态流转。\n"
        "commit 被拒绝——修正 progress.json 再提交。\n"
    )


def main(argv: list[str]) -> int:
    targets = argv[1:] if len(argv) > 1 else list(DEFAULT_TARGETS)
    rc = validate(targets)
    if rc != 0:
        return rc
    msg = check_fix_rounds_gate()
    if msg is not None:
        sys.stderr.write(msg)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
