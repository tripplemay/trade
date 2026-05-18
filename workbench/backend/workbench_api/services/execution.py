"""Execution-workflow service (B023 F002+).

F002 surfaces three primitives:

* ``get_position_diff`` — join latest ``account_snapshot`` with the
  target portfolio from the recommendations service, compute signed
  share/weight/dollar deltas per symbol.
* ``get_latest_account`` — read the most recent ``account_snapshot``.
* ``update_account`` — insert a new snapshot with ``source=ui_edit``.

This service intentionally has no broker integration and never invokes
``trade.execute``-style code paths. See ``docs/specs/B023-workbench-
phase2-manual-execution-spec.md`` §Hard boundaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.schemas.execution import (
    AccountSnapshotPayload,
    AccountUpdateRequest,
    PositionDiffEntry,
    PositionDiffResponse,
    PositionEntry,
)
from workbench_api.services.recommendations import get_current_recommendations

_logger = logging.getLogger("workbench.execution")


def _snapshot_to_payload(row: AccountSnapshot) -> AccountSnapshotPayload:
    """Convert an ORM row to the wire-shape payload, normalising types."""

    positions = [
        PositionEntry(
            symbol=str(entry.get("symbol", "")),
            shares=float(entry.get("shares", 0.0)),
            avg_cost=float(entry.get("avg_cost", 0.0)),
        )
        for entry in (row.positions or [])
    ]
    return AccountSnapshotPayload(
        id=row.id,
        snapshot_at=row.snapshot_at,
        cash=float(row.cash),
        base_currency=row.base_currency,
        positions=positions,
        source=row.source,  # type: ignore[arg-type]
    )


def get_latest_account(session: Session) -> AccountSnapshotPayload | None:
    """Return the most recent snapshot, or None if the table is empty.

    DB failure → log + None (matches the recommendations service's
    defensive-degrade contract added during B022 F014 round 2)."""

    try:
        repo = AccountSnapshotRepository(session)
        row = repo.latest()
    except SQLAlchemyError as exc:
        _logger.warning(
            "account_snapshot latest read failed; surfacing empty state",
            extra={
                "event": "execution_account_latest_db_error",
                "exception_message": str(exc),
            },
            exc_info=True,
        )
        session.rollback()
        return None
    if row is None:
        return None
    return _snapshot_to_payload(row)


def update_account(
    session: Session,
    body: AccountUpdateRequest,
    *,
    now: datetime | None = None,
) -> AccountSnapshotPayload:
    """Insert a new ``account_snapshot`` row with ``source=ui_edit``.

    Returns the persisted payload (with assigned ``id`` + ``snapshot_at``)
    so the frontend can update its cached state without a follow-up GET.
    """

    snapshot_at = now or datetime.now(UTC).replace(tzinfo=None)
    snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
    row = AccountSnapshot(
        id=snapshot_id,
        snapshot_at=snapshot_at,
        cash=Decimal(str(body.cash)),
        base_currency=body.base_currency.upper(),
        positions=[
            {"symbol": p.symbol.upper(), "shares": p.shares, "avg_cost": p.avg_cost}
            for p in body.positions
        ],
        source="ui_edit",
        created_at=snapshot_at,
    )
    repo = AccountSnapshotRepository(session)
    repo.upsert(row)
    session.commit()
    return _snapshot_to_payload(row)


def _compute_total_equity(snapshot: AccountSnapshotPayload | None) -> float:
    if snapshot is None:
        return 0.0
    total = snapshot.cash
    for p in snapshot.positions:
        total += p.shares * p.avg_cost
    return total


def get_position_diff(session: Session, as_of: str | None = None) -> PositionDiffResponse:
    """Build the position-diff response by joining snapshot + targets.

    F002 uses the per-symbol ``avg_cost`` as the price reference for
    share-count math. Target-only symbols (no prior position) get a
    placeholder ``reference_price=None`` and surface in ``unmatched``
    so the UI can flag them. This is research-only; no live market
    data is fetched.
    """

    snapshot = get_latest_account(session)
    as_of_date = as_of or date.today().isoformat()
    recommendations = get_current_recommendations(session)
    total_equity = _compute_total_equity(snapshot)

    current_by_symbol: dict[str, PositionEntry] = {}
    if snapshot is not None:
        for p in snapshot.positions:
            current_by_symbol[p.symbol.upper()] = p

    target_payload: list[PositionEntry] = []
    diff: list[PositionDiffEntry] = []
    unmatched: list[PositionDiffEntry] = []
    seen_symbols: set[str] = set()

    for target in recommendations.target_positions:
        symbol = target.symbol.upper()
        seen_symbols.add(symbol)
        current = current_by_symbol.get(symbol)
        current_shares = current.shares if current else 0.0
        reference_price: float | None = (
            current.avg_cost if current and current.avg_cost > 0 else None
        )

        target_dollar = target.target_weight * total_equity
        if reference_price is not None and reference_price > 0:
            target_shares = target_dollar / reference_price
        else:
            target_shares = current_shares  # cannot rebalance without a price

        delta_shares = target_shares - current_shares
        current_weight = (
            (current_shares * (reference_price or 0.0)) / total_equity
            if total_equity > 0 and reference_price is not None
            else 0.0
        )
        delta_weight = target.target_weight - current_weight
        delta_dollar = delta_shares * (reference_price or 0.0)

        entry = PositionDiffEntry(
            symbol=symbol,
            current_shares=current_shares,
            target_shares=target_shares,
            delta_shares=delta_shares,
            current_weight=current_weight,
            target_weight=target.target_weight,
            delta_weight=delta_weight,
            delta_dollar=delta_dollar,
            reference_price=reference_price,
            reason=target.rationale,
        )
        diff.append(entry)
        if reference_price is None:
            unmatched.append(entry)

        target_payload.append(
            PositionEntry(
                symbol=symbol,
                shares=target_shares,
                avg_cost=reference_price or 0.0,
            )
        )

    # Symbols held but no longer in target → flag as "sell to zero" so the
    # diff table tells the user to liquidate the position.
    for symbol, current in current_by_symbol.items():
        if symbol in seen_symbols:
            continue
        reference_price = current.avg_cost if current.avg_cost > 0 else None
        current_weight = (
            (current.shares * (reference_price or 0.0)) / total_equity
            if total_equity > 0 and reference_price is not None
            else 0.0
        )
        delta_shares = -current.shares
        delta_dollar = delta_shares * (reference_price or 0.0)
        diff.append(
            PositionDiffEntry(
                symbol=symbol,
                current_shares=current.shares,
                target_shares=0.0,
                delta_shares=delta_shares,
                current_weight=current_weight,
                target_weight=0.0,
                delta_weight=-current_weight,
                delta_dollar=delta_dollar,
                reference_price=reference_price,
                reason="held but no longer in target — sell to zero",
            )
        )

    return PositionDiffResponse(
        as_of_date=as_of_date,
        total_equity=total_equity,
        current=snapshot,
        target=target_payload,
        diff=diff,
        unmatched=unmatched,
    )
