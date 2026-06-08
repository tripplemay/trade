"""B047-OPS1 F001 — deploy.sh backtest wiring guards.

Root cause this batch hardens: B047's deploy chain enables the backtest worker
daemon + the canonical-report timer, but a command returning 0 does NOT prove
the unit ended up active/enabled (§12.11). And the post-alembic schema check
did not list the two B047 tables, so a deploy that never ran B047's migrations
would pass the gate while prod silently lacked them.

We grep the deploy.sh artifact (it expects a release-dir arg + runs on the VM)
the same way ``test_deploy_timer_wiring.py`` does.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"

WORKER_UNIT = "workbench-backtest-worker.service"
CANONICAL_TIMER = "workbench-canonical-backtest.timer"


def _deploy_text() -> str:
    return DEPLOY_SH.read_text(encoding="utf-8")


# --- post-step end-state assertions (§12.11) ------------------------------


def test_deploy_asserts_worker_is_active() -> None:
    """deploy.sh must verify the backtest worker is ACTIVE after enabling it,
    not just that the enable command returned 0."""
    text = _deploy_text()
    assert f'WORKER_UNIT="{WORKER_UNIT}"' in text, (
        "deploy.sh must pin the backtest worker unit name for the post-step assert"
    )
    assert 'systemctl is-active --quiet "${WORKER_UNIT}"' in text, (
        "deploy.sh must assert `systemctl is-active` on the backtest worker "
        "(post-step end-state check, §12.11)"
    )


def test_deploy_asserts_canonical_timer_enabled() -> None:
    """deploy.sh must verify the canonical-report timer is ENABLED after deploy."""
    text = _deploy_text()
    assert f'CANONICAL_TIMER="{CANONICAL_TIMER}"' in text, (
        "deploy.sh must pin the canonical timer unit name for the post-step assert"
    )
    assert 'systemctl is-enabled --quiet "${CANONICAL_TIMER}"' in text, (
        "deploy.sh must assert `systemctl is-enabled` on the canonical-backtest "
        "timer (post-step end-state check, §12.11)"
    )


def test_worker_assert_warns_not_hard_fails() -> None:
    """The worker is-active assert must WARN (sudoers may still be pending on a
    fresh VM), not hard-exit the deploy — mirrors the timer-enable best-effort
    path. We assert a `::warning::` is emitted for the not-active branch and the
    script does not `exit` inside that branch."""
    text = _deploy_text()
    assert "is NOT active after deploy" in text and "::warning::" in text, (
        "the worker not-active branch must emit a loud ::warning:: (not silent)"
    )
    # The whole backtest post-step block must not introduce a hard `exit`.
    block = text.split('WORKER_UNIT="')[1]
    assert "exit 1" not in block, (
        "the post-step worker/timer asserts must warn, never hard-fail the deploy"
    )


# --- required-tables backstop (Finding C) ---------------------------------


def test_schema_check_requires_backtest_tables() -> None:
    """The post-alembic schema check must list the two B047 tables so a deploy
    that never ran B047's migrations fails concretely."""
    text = _deploy_text()
    assert '"backtest_run"' in text, (
        "deploy.sh schema check must require the backtest_run table (B047 0012)"
    )
    assert '"investment_report"' in text, (
        "deploy.sh schema check must require the investment_report table (B047 0013)"
    )
