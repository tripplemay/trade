"""Regression guard: ``workbench/scripts/start_workbench.sh`` must boot on
GNU Bash 3.2 (the system ``/bin/bash`` shipped with macOS).

Bash 4+ idioms are forbidden because they crash silently on macOS users with
``wait: -n: invalid option`` and similar errors. The original B020 F005
review (2026-05-15) caught a ``wait -n`` call; this test stops the same
class of regression from re-landing.

The check is static — it grep-scans the script for forbidden patterns
rather than spinning up a Bash 3.2 interpreter (which is not available in
all CI environments). Patterns are anchored so they only fire on the
genuine misuse, not on appearances inside comments-of-comments.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "workbench" / "scripts" / "start_workbench.sh"

# Each entry: (human label, compiled regex). The regex matches the bad usage
# only when it appears in executable position — so a comment like
# ``# we avoid using "wait -n" here because ...`` is allowed.
FORBIDDEN_BASH4_IDIOMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # `wait -n` was added in Bash 4.3 — the original B020 F005 regression.
    ("wait -n", re.compile(r"^(?!\s*#).*\bwait\s+-n\b", re.MULTILINE)),
    # `mapfile` / `readarray` (Bash 4.0+).
    ("mapfile", re.compile(r"^(?!\s*#).*\bmapfile\b", re.MULTILINE)),
    ("readarray", re.compile(r"^(?!\s*#).*\breadarray\b", re.MULTILINE)),
    # Case-modifying parameter expansion (Bash 4.0+): ${var^^}, ${var,,},
    # ${var^}, ${var,}.
    (
        "case-modifying parameter expansion (Bash 4+)",
        re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*[\^,]{1,2}\}"),
    ),
    # Associative arrays — `declare -A` (Bash 4.0+).
    (
        "declare -A (associative array, Bash 4+)",
        re.compile(r"^(?!\s*#).*\bdeclare\s+-A\b", re.MULTILINE),
    ),
)


def test_start_workbench_script_present() -> None:
    assert SCRIPT_PATH.is_file(), (
        f"start_workbench.sh missing at {SCRIPT_PATH}; B020 spec requires the "
        "one-command boot helper."
    )


def test_start_workbench_avoids_bash_4_only_idioms() -> None:
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    offenders: list[tuple[str, int, str]] = []
    for label, pattern in FORBIDDEN_BASH4_IDIOMS:
        for match in pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[line_number - 1]
            offenders.append((label, line_number, line.strip()))

    assert offenders == [], (
        "start_workbench.sh contains Bash 4+ idiom(s) that break macOS's "
        f"default /bin/bash 3.2.57. Offenders: {offenders}"
    )


def test_pattern_catches_original_b020_f005_regression() -> None:
    """Self-check: the `wait -n` regex *would* have flagged the original bug.

    Without this, a future "fix" that loosens the regex could go undetected.
    The literal samples below are what Codex L1 review caught on 2026-05-15.
    """

    pattern = next(regex for label, regex in FORBIDDEN_BASH4_IDIOMS if label == "wait -n")
    assert pattern.search("wait -n\n"), "wait -n at start of line should match"
    assert pattern.search("  wait -n\n"), "indented wait -n should match"
    assert pattern.search("foo\nwait -n\nbar\n"), "wait -n on middle line should match"
    assert not pattern.search(
        "# we deliberately avoid `wait -n` because Bash 3.2 lacks it\n"
    ), "wait -n inside a comment should not match"
    assert not pattern.search("wait\n"), "plain `wait` (no -n) should not match"
