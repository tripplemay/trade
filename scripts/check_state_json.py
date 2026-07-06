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
"""

from __future__ import annotations

import json
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


def main(argv: list[str]) -> int:
    targets = argv[1:] if len(argv) > 1 else list(DEFAULT_TARGETS)
    return validate(targets)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
