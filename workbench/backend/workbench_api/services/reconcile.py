"""Reconciliation + journal-history + slippage analytics (B023 F005).

Reconcile is the user-driven act of saying "I've recorded the fills,
update the account snapshot to reflect them". The workbench:

1. Looks up the ticket's source snapshot (``ticket.snapshot_id``) and
   captures reference prices from its ``positions`` for slippage math.
2. Iterates fills, computing signed slippage in basis points (positive
   = unfavorable for the user, see ``_compute_slippage_bps``).
3. Builds a post-fill position map from the previous snapshot + the
   fills (buys add shares + subtract cash; sells subtract shares + add
   cash; commissions + fees always subtract cash).
4. Inserts a new ``account_snapshot`` row (source=fill_reconcile) only
   if the ticket is not yet ``executed`` (idempotent re-runs return the
   existing snapshot).
5. Flips the ticket status to ``executed`` and stamps ``executed_at``.

Journal history aggregates past tickets + their fills + slippage
summary; slippage analytics rolls those summaries into a 3-month /
6-month / 1-year window with simple per-month trend + outliers.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.fill_journal_entry import FillJournalEntryRepository
from workbench_api.db.repositories.order_ticket import OrderTicketRepository
from workbench_api.i18n import t
from workbench_api.schemas.reconcile import (
    FillSlippage,
    JournalHistoryItem,
    JournalHistoryResponse,
    ReconcileResponse,
    SlippageAnalyticsResponse,
    SlippageOutlier,
    SlippageSummary,
    SlippageTrendPoint,
)
from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID
from workbench_api.symbols.names import resolve_symbol_names

_logger = logging.getLogger("workbench.reconcile")

# B053 F001: tolerances for "impossible state" detection. A sell that lands
# within ``_SHARE_EPSILON`` of zero held shares (e.g. selling 50.0 of 50.0
# where float math leaves a sub-micro-share residual) is benign float noise
# and floored to 0; anything beyond it is a real oversell → reject. Cash uses
# the same idea at dollar precision.
_SHARE_EPSILON: float = 1e-6
_CASH_EPSILON: float = 1e-6


def _fmt_shares(value: float) -> str:
    """Trim trailing zeros so ``10.0`` renders as ``10`` and ``109.27`` stays
    exact — used only for human-facing rejection detail."""

    return f"{value:.4f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Reconcile
# ---------------------------------------------------------------------------


def _compute_slippage_bps(*, side: str, fill_price: float, reference_price: float) -> float:
    """Signed bps slippage vs reference price.

    Positive = unfavorable for the user (overpaid on a buy, undersold on
    a sell). Negative = favorable (got a better fill than the reference).
    """

    if reference_price <= 0:
        return 0.0
    raw = (fill_price - reference_price) / reference_price * 10_000.0
    return raw if side == "buy" else -raw


def _reference_prices_from_snapshot(
    snapshot: AccountSnapshot | None,
) -> dict[str, float]:
    """Build {symbol: avg_cost} from a snapshot's positions JSON. Missing
    or non-positive entries are dropped so callers see them as missing
    references (``None`` slippage)."""

    if snapshot is None:
        return {}
    refs: dict[str, float] = {}
    for entry in snapshot.positions or []:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).upper()
        avg_cost = entry.get("avg_cost")
        if not symbol or avg_cost in (None, ""):
            continue
        try:
            value = float(cast(Any, avg_cost))
        except (TypeError, ValueError):
            continue
        if value > 0:
            refs[symbol] = value
    return refs


def _apply_fills_to_positions(
    positions: list[dict[str, Any]],
    fills: list[Any],
) -> tuple[list[dict[str, Any]], float, list[dict[str, Any]]]:
    """Return (new_positions, cash_delta, oversell_violations).

    ``cash_delta`` is the net cash change to apply on top of the prior
    snapshot's cash: buys + commissions/fees subtract cash, sells add.

    ``oversell_violations`` (B053 F001) lists every sell whose share count
    exceeds the running held shares — an impossible state under the MVP (no
    short positions). Each entry is ``{symbol, sell_shares, held_shares,
    line}``. The caller turns a non-empty list into a 409 rather than
    silently flooring the position to 0 (the old behaviour hid user input
    errors: a mistyped fill quantity would just zero the holding with no
    trace). Selling *exactly* down to 0 is legal and produces no violation.
    """

    # B048 F002: remember each prior holding's sleeve tag so the rebuilt
    # snapshot keeps it (per-sleeve grouping stays reliable across a
    # reconcile). A symbol introduced by a fill has no prior tag → left
    # untagged (reader → unclassified).
    sleeve_by_symbol: dict[str, str] = {}
    pos_by_symbol: dict[str, dict[str, Any]] = {}
    for entry in positions:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).upper()
        if not symbol:
            continue
        if entry.get("sleeve"):
            sleeve_by_symbol[symbol] = str(entry["sleeve"])
        pos_by_symbol[symbol] = {
            "symbol": symbol,
            "shares": float(entry.get("shares", 0.0)),
            "avg_cost": float(entry.get("avg_cost", 0.0)),
        }

    cash_delta = 0.0
    oversell_violations: list[dict[str, Any]] = []
    for index, fill in enumerate(fills):
        symbol = fill.symbol.upper()
        shares = float(fill.shares)
        price = float(fill.fill_price)
        commission = float(fill.commission)
        fees = float(fill.fees)
        prev = pos_by_symbol.get(
            symbol, {"symbol": symbol, "shares": 0.0, "avg_cost": 0.0}
        )
        if fill.side == "buy":
            # Weighted average cost basis on accumulation.
            new_shares = prev["shares"] + shares
            if new_shares > 0:
                new_avg = (
                    prev["shares"] * prev["avg_cost"] + shares * price
                ) / new_shares
            else:
                new_avg = 0.0
            pos_by_symbol[symbol] = {
                "symbol": symbol,
                "shares": new_shares,
                "avg_cost": new_avg,
            }
            cash_delta -= shares * price + commission + fees
        else:
            new_shares = prev["shares"] - shares
            if new_shares < -_SHARE_EPSILON:
                # Sold more than held — impossible state (no short positions
                # in the MVP). Record it so the caller can reject the whole
                # reconcile with a 409 instead of silently flooring to 0.
                seq = getattr(fill, "order_seq", None)
                oversell_violations.append(
                    {
                        "symbol": symbol,
                        "sell_shares": shares,
                        "held_shares": prev["shares"],
                        "line": seq if seq is not None else index + 1,
                    }
                )
                new_shares = 0.0
            elif new_shares < 0:
                # Within epsilon: benign float noise from selling exactly to
                # zero (e.g. 109.27 of 109.27). Floor without flagging.
                new_shares = 0.0
            # Selling does not change cost basis; we just deplete shares.
            pos_by_symbol[symbol] = {
                "symbol": symbol,
                "shares": new_shares,
                "avg_cost": prev["avg_cost"] if new_shares > 0 else 0.0,
            }
            cash_delta += shares * price - commission - fees
    # Stable ordering so the JSON round-trip is deterministic for tests.
    # B048 F002: re-attach the preserved sleeve tag (only when known, so a
    # tagless holding stays byte-identical to a pre-B048 row).
    out: list[dict[str, Any]] = []
    for symbol in sorted(pos_by_symbol):
        entry = pos_by_symbol[symbol]
        sleeve = sleeve_by_symbol.get(symbol)
        if sleeve:
            entry["sleeve"] = sleeve
        out.append(entry)
    return out, cash_delta, oversell_violations


def _ticket_diff_symbols(ticket: OrderTicket, session: Session) -> set[str]:
    """Best-effort: derive symbols the ticket intended to trade from the
    referenced snapshot's positions. We do not store the rendered diff
    rows per ticket, so the set is approximate — used only to flag
    unmatched lines on reconcile."""

    repo = AccountSnapshotRepository(session)
    snapshot = repo.get_by_id(ticket.snapshot_id) if ticket.snapshot_id else None
    if snapshot is None:
        return set()
    return {
        str(entry.get("symbol", "")).upper()
        for entry in (snapshot.positions or [])
        if isinstance(entry, dict) and entry.get("symbol")
    }


def reconcile_ticket(
    session: Session, ticket_id: str, *, now: datetime | None = None
) -> ReconcileResponse:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    ticket_repo = OrderTicketRepository(session)
    ticket = ticket_repo.get_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=404, detail=t("ticket.not_found", ticket_id=ticket_id)
        )
    if ticket.status == "voided":
        raise HTTPException(
            status_code=409,
            detail=t("ticket.is_voided", ticket_id=ticket_id),
        )

    fills_repo = FillJournalEntryRepository(session)
    fills = fills_repo.list_by_ticket(ticket_id)
    if not fills:
        raise HTTPException(
            status_code=409,
            detail=t("ticket.no_fills_to_reconcile", ticket_id=ticket_id),
        )

    snapshot_repo = AccountSnapshotRepository(session)
    prior_snapshot = (
        snapshot_repo.get_by_id(ticket.snapshot_id) if ticket.snapshot_id else None
    )
    reference_prices = _reference_prices_from_snapshot(prior_snapshot)

    # B079 — batch-resolve display names for the reconciled symbols (name-primary).
    names = resolve_symbol_names(session, [str(f.symbol) for f in fills])
    fill_slippages: list[FillSlippage] = []
    valid_bps: list[float] = []
    total_dollar = 0.0
    for fill in fills:
        ref = reference_prices.get(fill.symbol.upper())
        bps: float | None
        if ref is None:
            bps = None
        else:
            bps = _compute_slippage_bps(
                side=fill.side, fill_price=float(fill.fill_price), reference_price=ref
            )
            valid_bps.append(bps)
            total_dollar += (bps / 10_000.0) * float(fill.shares) * float(fill.fill_price)
        fill_slippages.append(
            FillSlippage(
                fill_id=fill.id,
                symbol=fill.symbol,
                name=names.get(str(fill.symbol).upper()),
                side=fill.side,  # type: ignore[arg-type]
                shares=float(fill.shares),
                fill_price=float(fill.fill_price),
                reference_price=ref,
                slippage_bps=bps,
            )
        )
    avg_bps = sum(valid_bps) / len(valid_bps) if valid_bps else None
    summary = SlippageSummary(
        ticket_id=ticket_id,
        fill_count=len(fills),
        avg_bps=avg_bps,
        total_dollar=total_dollar,
    )

    ticket_symbols = _ticket_diff_symbols(ticket, session)
    filled_symbols = {fill.symbol.upper() for fill in fills}
    unmatched_lines = sorted(ticket_symbols - filled_symbols)

    # Idempotency: if the ticket is already executed, find the post-
    # reconcile snapshot it produced and return that without inserting
    # a duplicate. We identify the canonical snapshot as the most
    # recent ``source=fill_reconcile`` row whose ``snapshot_at <= now``
    # AND whose snapshot_at is >= the ticket's executed_at (when set);
    # in practice the simplest deterministic key is "the latest
    # fill_reconcile snapshot strictly after the ticket's prior
    # snapshot," and we fall back to the absolute latest if that lookup
    # is ambiguous.
    if ticket.status == "executed":
        stmt = (
            select(AccountSnapshot)
            .where(
                AccountSnapshot.source == "fill_reconcile",
                # B057 F004 — scope by the ticket's mode so an already-executed
                # ticket resolves to ITS OWN mode's post-reconcile snapshot, never
                # another mode's (which would corrupt the idempotent re-run).
                AccountSnapshot.strategy_id == ticket.strategy_id,
            )
            # B053 F002 — deterministic tie-breaker (created_at, then unique id)
            # so the idempotent re-run resolves to the same snapshot every time
            # even when two fill_reconcile rows share ``snapshot_at``.
            .order_by(
                AccountSnapshot.snapshot_at.desc(),
                AccountSnapshot.created_at.desc(),
                AccountSnapshot.id.desc(),
            )
            .limit(1)
        )
        existing = session.execute(stmt).scalar_one_or_none()
        existing_id = existing.id if existing else ""
        return ReconcileResponse(
            snapshot_id=existing_id,
            ticket_id=ticket_id,
            slippage_summary=summary,
            fill_slippages=fill_slippages,
            unmatched_lines=unmatched_lines,
            already_reconciled=True,
        )

    # Build the post-fill snapshot.
    prior_positions = (
        list(prior_snapshot.positions or []) if prior_snapshot is not None else []
    )
    prior_cash = float(prior_snapshot.cash) if prior_snapshot is not None else 0.0
    base_currency = (
        prior_snapshot.base_currency if prior_snapshot is not None else "USD"
    )
    new_positions, cash_delta, oversell_violations = _apply_fills_to_positions(
        prior_positions, fills
    )

    # B053 F001: impossible-state guards — reject (409) instead of silently
    # "correcting" the books. No snapshot is inserted and the ticket is NOT
    # flipped to executed, so the user can fix the fill and re-run.
    if oversell_violations:
        first = oversell_violations[0]
        raise HTTPException(
            status_code=409,
            detail=t(
                "reconcile.oversell",
                line=first["line"],
                symbol=first["symbol"],
                sell_shares=_fmt_shares(float(first["sell_shares"])),
                held_shares=_fmt_shares(float(first["held_shares"])),
            ),
        )

    projected_cash = prior_cash + cash_delta
    if projected_cash < -_CASH_EPSILON:
        raise HTTPException(
            status_code=409,
            detail=t(
                "reconcile.cash_would_go_negative",
                shortfall=f"{abs(projected_cash):.2f}",
                prior_cash=f"{prior_cash:.2f}",
                cash_delta=f"{cash_delta:.2f}",
            ),
        )
    new_cash = max(0.0, projected_cash)

    snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
    new_snapshot = AccountSnapshot(
        id=snapshot_id,
        snapshot_at=now,
        # B057 F004 — the reconciled snapshot belongs to the ticket's mode, so it
        # becomes that mode's new latest() account (Master stays Master).
        strategy_id=ticket.strategy_id,
        cash=Decimal(str(new_cash)),
        base_currency=base_currency,
        positions=new_positions,
        source="fill_reconcile",
        created_at=now,
    )
    snapshot_repo.upsert(new_snapshot)

    # Flip the ticket to executed.
    ticket_repo.reconcile(ticket_id, now)
    session.commit()

    return ReconcileResponse(
        snapshot_id=snapshot_id,
        ticket_id=ticket_id,
        slippage_summary=summary,
        fill_slippages=fill_slippages,
        unmatched_lines=unmatched_lines,
        already_reconciled=False,
    )


# ---------------------------------------------------------------------------
# Journal history
# ---------------------------------------------------------------------------


def get_journal_history(
    session: Session,
    *,
    since: str | None = None,
    strategy_id: str = MASTER_STRATEGY_ID,
) -> JournalHistoryResponse:
    """Past tickets + per-ticket fill counts + slippage summary.

    B057 F004 — filtered by ``strategy_id`` (default Master, backward compatible)
    so each mode's journal shows only its own reconciled tickets."""

    stmt = (
        select(OrderTicket)
        .where(OrderTicket.strategy_id == strategy_id)
        .order_by(OrderTicket.created_at.desc())
    )
    if since:
        try:
            since_date = date.fromisoformat(since)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=t("reconcile.invalid_since", since=since),
            ) from exc
        stmt = stmt.where(OrderTicket.ticket_date >= since_date)
    tickets = list(session.execute(stmt).scalars().all())

    fills_repo = FillJournalEntryRepository(session)
    snapshot_repo = AccountSnapshotRepository(session)
    items: list[JournalHistoryItem] = []
    for ticket in tickets:
        fills = fills_repo.list_by_ticket(ticket.id)
        ref_snapshot = (
            snapshot_repo.get_by_id(ticket.snapshot_id) if ticket.snapshot_id else None
        )
        refs = _reference_prices_from_snapshot(ref_snapshot)
        bps_values: list[float] = []
        total_dollar = 0.0
        for fill in fills:
            ref = refs.get(fill.symbol.upper())
            if ref is None:
                continue
            bps = _compute_slippage_bps(
                side=fill.side, fill_price=float(fill.fill_price), reference_price=ref
            )
            bps_values.append(bps)
            total_dollar += (bps / 10_000.0) * float(fill.shares) * float(fill.fill_price)
        items.append(
            JournalHistoryItem(
                ticket_id=ticket.id,
                ticket_date=ticket.ticket_date,
                status=ticket.status,  # type: ignore[arg-type]
                snapshot_id=ticket.snapshot_id,
                markdown_path=ticket.markdown_path,
                created_at=ticket.created_at,
                executed_at=ticket.executed_at,
                fill_count=len(fills),
                avg_bps=(sum(bps_values) / len(bps_values)) if bps_values else None,
                total_dollar=total_dollar,
            )
        )
    return JournalHistoryResponse(since=since, items=items)


# ---------------------------------------------------------------------------
# Slippage analytics
# ---------------------------------------------------------------------------


_WINDOW_DAYS: dict[str, int] = {"3m": 92, "6m": 183, "1y": 366}


def get_slippage_analytics(
    session: Session,
    *,
    window: str = "3m",
    strategy_id: str = MASTER_STRATEGY_ID,
    now: datetime | None = None,
) -> SlippageAnalyticsResponse:
    if window not in _WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=t("reconcile.invalid_window", window=repr(window)),
        )
    cutoff = (now or datetime.now(UTC).replace(tzinfo=None)) - timedelta(
        days=_WINDOW_DAYS[window]
    )

    history = get_journal_history(session, strategy_id=strategy_id)
    in_window = [
        item
        for item in history.items
        if item.executed_at is not None
        and item.executed_at >= cutoff
        and item.avg_bps is not None
    ]
    if not in_window:
        return SlippageAnalyticsResponse(
            window=window,  # type: ignore[arg-type]
            rolling_avg_bps=None,
            outliers=[],
            trend=[],
        )

    rolling_avg = sum(item.avg_bps or 0.0 for item in in_window) / len(in_window)

    # Per-month trend.
    by_month: dict[str, list[float]] = defaultdict(list)
    for item in in_window:
        if item.executed_at is None or item.avg_bps is None:
            continue
        month_key = item.executed_at.strftime("%Y-%m")
        by_month[month_key].append(item.avg_bps)
    trend = [
        SlippageTrendPoint(
            month=month,
            avg_bps=sum(values) / len(values),
            fill_count=sum(
                item.fill_count
                for item in in_window
                if item.executed_at is not None
                and item.executed_at.strftime("%Y-%m") == month
            ),
        )
        for month, values in sorted(by_month.items())
    ]

    # Outliers: any ticket whose avg_bps is > 2× the window mean (and the
    # mean itself is positive) OR > 30 bps in absolute value.
    abs_threshold = max(30.0, 2.0 * abs(rolling_avg))
    outliers = [
        SlippageOutlier(
            ticket_id=item.ticket_id,
            ticket_date=item.ticket_date,
            avg_bps=item.avg_bps or 0.0,
        )
        for item in in_window
        if item.avg_bps is not None and abs(item.avg_bps) >= abs_threshold
    ]

    return SlippageAnalyticsResponse(
        window=window,  # type: ignore[arg-type]
        rolling_avg_bps=rolling_avg,
        outliers=outliers,
        trend=trend,
    )
