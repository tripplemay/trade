"""B056 F002 — per-asset P&L (pure).

Computes each virtual holding's cost basis → current price → unrealized P&L
(absolute $ and %). Pure (no ORM): the MTM job records it into the nav point and
the F003 read service surfaces the live table from the same helper, so the
number the user sees matches the number stored.

Degrade-don't-crash: an unmarkable symbol (no close) reports ``close=None`` /
``market_value=None`` / ``unrealized=None`` rather than guessing a price; a
zero cost basis reports ``unrealized_pct=None`` (no division by zero).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionPnl:
    symbol: str
    shares: float
    avg_cost: float
    close: float | None
    market_value: float | None
    cost_basis: float
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None


def compute_position_pnl(
    positions: Iterable[tuple[str, float, float]],
    marks: dict[str, float],
) -> list[PositionPnl]:
    """``positions`` = ``(symbol, shares, avg_cost)``; ``marks`` = ``{SYMBOL: close}``.

    Returns one :class:`PositionPnl` per position, symbol-sorted."""

    out: list[PositionPnl] = []
    for symbol, shares, avg_cost in positions:
        sym = symbol.upper()
        close = marks.get(sym)
        cost_basis = shares * avg_cost
        if close is None:
            out.append(
                PositionPnl(sym, shares, avg_cost, None, None, cost_basis, None, None)
            )
            continue
        market_value = shares * close
        unrealized = market_value - cost_basis
        pct = (unrealized / cost_basis) if cost_basis > 0 else None
        out.append(
            PositionPnl(
                sym, shares, avg_cost, close, market_value, cost_basis, unrealized, pct
            )
        )
    return sorted(out, key=lambda p: p.symbol)
