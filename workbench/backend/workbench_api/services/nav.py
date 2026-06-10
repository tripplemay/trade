"""NAV aggregation helper — unified onto ``account_snapshot`` (B051 F001).

``aggregate_nav`` values the **latest** ``account_snapshot`` at market:
``cash + Σ shares × latest_close`` via the shared mark-to-market helper —
the SAME source + basis the execution position-diff, current_weight and
Home Day P&L already use. B051 removed the old ``select(Account)`` read:
the ``account`` table is only ever written by the ``accounts/me.json``
bootstrap mirror, so reading it here meant a UI-saved account (which
writes ``account_snapshot``) was invisible to NAV — Home showed 0.0 and
Recommendations claimed no account was configured.

History: relocated from the removed dashboard service in B049 F003 (it
then summed ``account.cash + equity_value``).

Read-only; degrades to ``(False, 0.0)`` on DB error so the Home page
renders a zeroed NAV card rather than 500ing (B022 F014 fixing-round 2
contract). A position whose symbol has no mark (fewer than two stored
closes) contributes nothing to NAV — the mark_to_market degrade contract.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.services.mark_to_market import compute_mark_to_market, marks_for
from workbench_api.services.prices_provider import DbPriceProvider, PriceProvider

_logger = logging.getLogger("workbench.nav")


def snapshot_positions_and_cash(
    snapshot: AccountSnapshot | None,
) -> tuple[list[tuple[str, float]], float]:
    """Trust-nothing parse of a snapshot's positions JSON → ``([(SYMBOL, shares)], cash)``.

    Malformed entries (non-dict, missing/garbage symbol or shares) are
    dropped — the same posture home / reconcile take on this JSON.
    ``None`` snapshot → ``([], 0.0)``.
    """

    if snapshot is None:
        return [], 0.0
    positions: list[tuple[str, float]] = []
    raw = snapshot.positions if isinstance(snapshot.positions, list) else []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        try:
            shares = float(entry.get("shares", 0.0))
        except (TypeError, ValueError):
            continue
        positions.append((symbol, shares))
    return positions, float(snapshot.cash or 0.0)


def aggregate_account_state(
    session: Session, provider: PriceProvider | None = None
) -> tuple[bool, float]:
    """Return ``(account_present, nav)`` from the latest ``account_snapshot``.

    ``account_present`` is True iff a snapshot row exists — a pure-cash
    snapshot with zero positions (the new-user path: UI Account form saved
    with just a cash balance) still counts as a configured account.

    ``nav = cash + mark-to-market(positions)``; with zero positions it is
    exactly ``cash``. No snapshot → ``(False, 0.0)``; DB error → logged,
    rolled back, ``(False, 0.0)`` (degrade contract unchanged).
    """

    try:
        snapshot = AccountSnapshotRepository(session).latest()
        if snapshot is None:
            return False, 0.0
        positions, cash = snapshot_positions_and_cash(snapshot)
        if provider is None:
            provider = DbPriceProvider(session)
        marks = marks_for(provider, (symbol for symbol, _ in positions))
        mtm = compute_mark_to_market(positions, cash, marks)
        return True, round(mtm.nav, 2)
    except SQLAlchemyError as exc:
        _logger.warning(
            "NAV aggregation skipped due to DB error",
            extra={"event": "nav_db_error", "exception_message": str(exc)},
            exc_info=True,
        )
        session.rollback()
        return False, 0.0


def aggregate_nav(session: Session, provider: PriceProvider | None = None) -> float:
    """Market-value NAV of the latest ``account_snapshot`` (0.0 when none).

    Returns 0.0 (and logs at WARNING) when the DB read raises so callers can
    still render with a zeroed NAV rather than blowing up the endpoint.
    """

    return aggregate_account_state(session, provider)[1]
