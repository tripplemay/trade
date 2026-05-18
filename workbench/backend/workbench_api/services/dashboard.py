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

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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

_logger = logging.getLogger("workbench.dashboard")

DEFAULT_KILL_SWITCH_THRESHOLD: float = 0.20
"""Workbench-wide manual-halt threshold (drawdown ratio).

20% mirrors the B019 retune sweep's conservative band; tuned through the
spec/ADR pipeline rather than the runtime.
"""


PROD_RELEASE_CURRENT: Path = Path("/srv/workbench/current")
"""B021 deploy.sh keeps this symlink pointing at the live release root.

Used by `_resolve_reports_dir` to fall back to the VM release tree when
the repo-root anchor (dev path) does not contain the configured docs.
"""


def _resolve_reports_dir(configured: str) -> Path:
    """Pick the directory that actually holds the reports we want to scan.

    Resolution order:

    1. ``configured`` is absolute → use as-is.
    2. ``configured`` is relative + ``<repo_root>/<configured>`` exists
       → dev / source checkout.
    3. ``configured`` is relative + ``/srv/workbench/current/<configured>``
       exists → production, where B022 F009-1 fix ships ``docs/test-reports/``
       inside the release tarball.
    4. None of the above → return the repo-root candidate so the scanner's
       ``Path.exists()`` check degrades cleanly to an empty list (the
       Dashboard's empty-state path).

    The two-stage fallback lets a single default (`docs/test-reports`)
    work in both dev (where files live at the repo root) and prod (where
    the deploy step copies them under the release directory). B022 F014
    blocker rejected the single-anchor behaviour because prod had
    ``reports_count=0``.
    """

    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    # parents arithmetic from a 5-level path
    # (services/dashboard.py → repo root). cli/bootstrap.py uses the
    # same depth + already documents the parents[4] anchor. The prior
    # parents[3] anchor resolved to `workbench/` (not the repo root)
    # and silently returned an empty list in dev because the configured
    # default `docs/test-reports` only exists at the actual repo root.
    repo_root = Path(__file__).resolve().parents[4]
    dev_path = repo_root / candidate
    prod_path = PROD_RELEASE_CURRENT / candidate
    if dev_path.is_dir():
        return dev_path
    if prod_path.is_dir():
        return prod_path
    return dev_path


def _aggregate_nav(session: Session) -> float:
    """Sum cash + equity_value across all accounts (single row in MVP).

    Returns 0.0 (and logs at WARNING) when the DB read raises so the
    Dashboard page still renders with a zeroed NAV card rather than
    blowing up the whole endpoint. B022 F014 fixing-round 2:
    Codex L2 observed /api/dashboard 500ing in production with no
    journal entry; the missing log was added at the app level, and
    this graceful-degradation lets the rest of the dashboard surface
    (kill-switch / recent reports / action items) still render.
    """

    try:
        accounts = list(session.execute(select(Account)).scalars())
    except SQLAlchemyError as exc:
        _logger.warning(
            "dashboard NAV aggregation skipped due to DB error",
            extra={"event": "dashboard_nav_db_error", "exception_message": str(exc)},
            exc_info=True,
        )
        session.rollback()
        return 0.0
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
