"""B048 F004 — wash-sale detection from the fills journal.

A wash sale (informational, for the user's tax review) is flagged when a
holding is **sold at a loss** and the **same symbol is repurchased within
30 days** of that sale. Both inputs already exist:

* the loss test uses the symbol's ``avg_cost`` from the latest
  ``AccountSnapshot`` taken on-or-before the sale date (cost basis known
  at sale time) — ``avg_cost > sell fill_price`` ⇒ a loss sale;
* the repurchase test scans the ``fill_journal_entry`` history for a
  ``buy`` of the same symbol strictly after the sale and within 30 days.

Output is one :class:`WashSaleFlag` per symbol (the most recent qualifying
repurchase), carrying the repurchase date + days since. The recommendations
service surfaces these (replacing the pre-F011 empty list) and the B023
order ticket renders them in its tax / wash-sale section automatically.

This is informational only — it never gates ticket generation (B023). It is
read-only over ``fill_journal_entry`` + ``account_snapshot`` and imports no
``trade`` package, so it is safe on the request path (§12.10.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.fill_journal_entry import FillJournalEntryRepository
from workbench_api.schemas.recommendations import WashSaleFlag
from workbench_api.symbols.names import resolve_symbol_names

# IRS-style window: a repurchase within 30 days of a loss sale taints it.
WASH_SALE_WINDOW_DAYS: int = 30


@dataclass(frozen=True, slots=True)
class _CostSnapshot:
    """A snapshot's per-symbol avg_cost, keyed for at-or-before lookup."""

    on_date: date
    avg_cost_by_symbol: dict[str, float]


def _cost_snapshots(session: Session) -> list[_CostSnapshot]:
    """Per-snapshot avg_cost maps, oldest first (for at-or-before lookup)."""

    # B053 F002 — stable tie-breaker so same-instant snapshots order
    # deterministically for the at-or-before cost lookup.
    stmt = select(AccountSnapshot).order_by(
        AccountSnapshot.snapshot_at, AccountSnapshot.created_at, AccountSnapshot.id
    )
    out: list[_CostSnapshot] = []
    for snap in session.execute(stmt).scalars().all():
        costs: dict[str, float] = {}
        for entry in snap.positions or []:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol", "")).upper()
            if not symbol:
                continue
            try:
                costs[symbol] = float(entry.get("avg_cost", 0.0))
            except (TypeError, ValueError):
                continue
        out.append(_CostSnapshot(on_date=snap.snapshot_at.date(), avg_cost_by_symbol=costs))
    return out


def _avg_cost_at(
    cost_snapshots: Sequence[_CostSnapshot], symbol: str, on_date: date
) -> float | None:
    """avg_cost of ``symbol`` from the latest snapshot on-or-before ``on_date``.

    Returns ``None`` when no snapshot at/before the date carries the symbol —
    the caller then can't establish a loss and skips (does not fabricate)."""

    result: float | None = None
    for snap in cost_snapshots:  # oldest first
        if snap.on_date > on_date:
            break
        if symbol in snap.avg_cost_by_symbol:
            result = snap.avg_cost_by_symbol[symbol]
    return result


def detect_wash_sales(
    session: Session, *, today: date | None = None
) -> list[WashSaleFlag]:
    """Return one wash-sale flag per symbol with a loss sale + 30-day
    repurchase. Sorted by symbol for a deterministic response."""

    as_of = today or datetime.now(UTC).date()
    fills = FillJournalEntryRepository(session).list_all_chronological()
    if not fills:
        return []
    cost_snapshots = _cost_snapshots(session)

    buys_by_symbol: dict[str, list[date]] = {}
    for fill in fills:
        if fill.side == "buy":
            buys_by_symbol.setdefault(fill.symbol.upper(), []).append(
                fill.filled_at.date()
            )

    flags: dict[str, WashSaleFlag] = {}
    for fill in fills:
        if fill.side != "sell":
            continue
        symbol = fill.symbol.upper()
        sell_date = fill.filled_at.date()
        avg_cost = _avg_cost_at(cost_snapshots, symbol, sell_date)
        if avg_cost is None or avg_cost <= float(fill.fill_price):
            continue  # not a determinable loss sale
        window_end = sell_date + timedelta(days=WASH_SALE_WINDOW_DAYS)
        repurchases = [
            buy_date
            for buy_date in buys_by_symbol.get(symbol, [])
            if sell_date < buy_date <= window_end
        ]
        if not repurchases:
            continue
        last_buy = max(repurchases)
        existing = flags.get(symbol)
        # Keep the most recent qualifying repurchase per symbol.
        if existing is None or last_buy.isoformat() > existing.last_buy_date:
            flags[symbol] = WashSaleFlag(
                symbol=symbol,
                last_buy_date=last_buy.isoformat(),
                days_since=max(0, (as_of - last_buy).days),
            )
    # B079 — batch-resolve display names for the flagged symbols (name-primary).
    names = resolve_symbol_names(session, list(flags))
    return [
        flags[symbol].model_copy(update={"name": names.get(symbol)})
        for symbol in sorted(flags)
    ]
