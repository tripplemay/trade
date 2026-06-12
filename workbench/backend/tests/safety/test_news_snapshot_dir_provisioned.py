"""B033 F004 fixing-round — deploy.sh must provision the persistent news
snapshot directory, empty, without enabling ingest.

Regression guard for the F004 Codex L2 blocker (2026-06-01): production
VM was missing ``data/snapshots/news/``. Acceptance §8 requires the
directory to exist and be empty after deploy; permanent boundary (q)
requires news ingest to stay manual-trigger only (no cron / scheduler /
``cli fetch`` wired into the deploy path).

This is a static guard on ``workbench/deploy/scripts/deploy.sh`` — the
same shape as ``tests/safety/test_news_no_scheduler.py``. It cannot
exercise the real VM, but it locks the deploy script's contract so a
future edit that drops the mkdir, moves it off the persistent data root,
or wires an ingest call fails loudly in CI.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"


def _deploy_script_text() -> str:
    assert DEPLOY_SH.is_file(), f"deploy.sh not found at {DEPLOY_SH}"
    return DEPLOY_SH.read_text(encoding="utf-8")


def test_deploy_creates_persistent_news_snapshot_dir() -> None:
    """deploy.sh mkdir -p's the news snapshot dir under the persistent
    data root (/var/lib/workbench), not only the ephemeral release tree."""

    text = _deploy_script_text()
    assert "data/snapshots/news" in text, (
        "deploy.sh no longer references data/snapshots/news — F004 L2 "
        "acceptance §8 requires the production directory to be provisioned "
        "at deploy time (spec risk-table mitigation, 2026-06-01 blocker)."
    )
    assert "/var/lib/workbench/data/snapshots/news" in text, (
        "News snapshot dir must default to the persistent data root next to "
        "the SQLite DB so raw bodies survive release swaps + GC, not the "
        "release tree which is discarded each deploy."
    )
    assert "mkdir -p" in text


def test_deploy_does_not_run_news_ingest() -> None:
    """Permanent boundary (q): the deploy must NOT trigger a news fetch —
    B033 ships manual-trigger ingest only (no cron / scheduler / CLI run
    wired into deploy)."""

    text = _deploy_script_text()
    lowered = text.lower()
    assert "news.cli" not in lowered, (
        "deploy.sh must not invoke the news CLI — boundary (q) keeps ingest "
        "manual-trigger only; the deploy provisions an empty dir, nothing more."
    )
    # Boundary (q) forbids the NEWS ingest specifically — not every data fetch.
    # B058 F002 legitimately runs a read-only `prices.cli fetch` at deploy
    # (boundary (r): priming price_snapshot), so assert no NEWS fetch is wired
    # rather than the over-broad "no `cli fetch` at all".
    assert "news.cli fetch" not in lowered
    # No news-ingest scheduler library wired into the deploy path. (The
    # script legitimately uses systemctl to restart the workbench services;
    # we only forbid scheduler libs that would imply automated news fetch.)
    for scheduler_lib in ("apscheduler", "aiocron"):
        assert scheduler_lib not in lowered, (
            f"deploy.sh references {scheduler_lib!r} — boundary (q) forbids "
            "wiring a news-ingest scheduler at deploy time."
        )
