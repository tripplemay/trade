"""Builds the ``/api/dashboard`` response (B022 F006).

The 4 top cards on the home page need:

* ``nav`` — net asset value (cash + equity from the single research
  account row); 0.0 when no account exists yet, so the page shows a
  zeroed-out card instead of a Pydantic validation 500.
* ``master_drawdown`` — current drawdown vs equity peak. No data source
  exists in SQLite yet; we surface 0.0 as a placeholder until a Phase 2
  drawdown tracker (post-B022) lands. Documented in the field comment
  so the next batch's spec doesn't repeat the discovery.
* ``kill_switch_threshold`` — the workbench-wide drawdown ceiling that
  arms the manual halt switch. Constant for now (matches B019 retune
  sweep configuration); becomes a settings field if the threshold ever
  varies per strategy or per account.
* ``days_to_next_rebalance`` — also 0 until a scheduler / cron source
  lands. Acceptable empty state per F006 spec.

Recent reports come from the filesystem scanner; action items are an
empty list (no source yet — F010 wash-sale flags + B023 alerts populate).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.account import Account
from workbench_api.db.repositories.account import AccountRepository
from workbench_api.schemas.dashboard import (
    ActionItem,
    DashboardResponse,
    LastRebalance,
    RecentReport,
)
from workbench_api.services.reports_scanner import recent_reports
from workbench_api.settings import Settings

DEFAULT_KILL_SWITCH_THRESHOLD: float = 0.20
"""Workbench-wide manual-halt threshold (drawdown ratio).

20% mirrors the B019 retune sweep's conservative band; tuned through the
spec/ADR pipeline rather than the runtime.
"""


def _resolve_reports_dir(configured: str) -> Path:
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    # When the path is relative, anchor it at the repo root so the
    # default ``docs/test-reports`` resolves regardless of where uvicorn
    # was invoked from. The backend package lives at
    # ``workbench/backend/workbench_api/services/dashboard.py``; walking
    # up 4 ``parents`` lands at the repo root.
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / candidate


def _aggregate_nav(session: Session) -> float:
    """Sum cash + equity_value across all accounts (single row in MVP)."""

    accounts = list(session.execute(select(Account)).scalars())
    if not accounts:
        return 0.0
    total = 0.0
    for account in accounts:
        total += float(account.cash) + float(account.equity_value)
    return round(total, 2)


def build_dashboard(session: Session, settings: Settings) -> DashboardResponse:
    """Assemble the DashboardResponse the home page consumes.

    The session enters with the same transactional contract as every
    other workbench route (commit on clean exit, rollback on raise);
    this function does not write — it only reads via the repository
    layer + filesystem scanner.
    """

    # Repository plumbing lives here so a future caller (CLI tool, test
    # fixture) can swap in a fake without re-implementing the dashboard
    # aggregation. ``AccountRepository`` is bound but not iterated yet
    # because ``_aggregate_nav`` uses a single SELECT for clarity; the
    # repo instance is kept around so subsequent fields (e.g. base
    # currency display in B023) plug in without re-threading.
    _accounts_repo = AccountRepository(session)
    del _accounts_repo  # placeholder for the cross-feature wiring

    nav = _aggregate_nav(session)
    reports_dir = _resolve_reports_dir(settings.WORKBENCH_REPORTS_DIR)
    raw_reports = recent_reports(reports_dir, limit=10)

    return DashboardResponse(
        nav=nav,
        # The two placeholder fields below are deliberately zeroed; the
        # Dashboard renders the cards regardless of whether a real data
        # source exists yet (per F006 spec: "empty states" required).
        master_drawdown=0.0,
        kill_switch_threshold=DEFAULT_KILL_SWITCH_THRESHOLD,
        days_to_next_rebalance=0,
        last_rebalance=_resolve_last_rebalance(session),
        recent_reports=[RecentReport(**entry) for entry in raw_reports],
        action_items=_resolve_action_items(),
    )


def _resolve_last_rebalance(session: Session) -> LastRebalance | None:
    """No rebalance journal in SQLite yet — return None.

    The field is wired so F008 (Backtest viewer) can land a journal table
    later and surface the most recent entry without touching the route
    handler. Until then the page renders the "no last rebalance" empty
    state.
    """

    del session
    return None


def _resolve_action_items() -> list[ActionItem]:
    """No alert source in MVP — empty list lights the page's empty state.

    F010 wash-sale heuristics + B023 alert engine populate this. Keeping
    the empty implementation here (vs inlining ``[]`` at the call site)
    means future wiring lands in one place.
    """

    return []
