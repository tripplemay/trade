"""B046 F001 — shared mark-to-market current-weight helper.

The tradeable position diff (execution ``get_position_diff`` → the order ticket)
and the recommendations ``current_weight`` display must value held positions at
**market** (latest close), not at cost basis (``avg_cost``). Valuing at cost
understates an appreciated holding's weight, so the ticket over-buys it.

This helper centralises the mark-to-market arithmetic both call sites reuse —
the same seam ``build_home`` (B037) uses: a :class:`PriceProvider` resolves the
latest close per symbol from the ``price_snapshot`` table (injected so tests
assert exact weights against known closes).

Valuation is internally consistent — numerator AND denominator are market value:

    NAV            = cash + Σ (shares × latest_close)   over marked positions
    current_weight = (shares × latest_close) / NAV      per symbol

``avg_cost`` is deliberately untouched: cost-basis / wash-sale accounting still
reads it from the stored ``AccountSnapshot`` — this batch changes only the
weight/diff valuation basis, never the books.

Degrade-don't-crash (mirrors ``build_home`` semantics):

* No positions / no snapshot → ``nav == cash`` (often ``0.0``) → every weight ``0.0``.
* A symbol with no mark (fewer than two stored closes) → ``market_value=None``,
  listed in :attr:`MarkToMarket.unmarked`, ``current_weight`` ``0.0`` — the
  caller surfaces it instead of silently treating it as a zero-weight holding.
* ``NAV <= 0`` → every weight ``0.0`` (no division by zero).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from workbench_api.services.prices_provider import PriceMark, PriceProvider


@dataclass(frozen=True, slots=True)
class MarkedPosition:
    """One held position valued at the latest close (or unmarked)."""

    symbol: str
    shares: float
    latest_close: float | None
    market_value: float | None


@dataclass(frozen=True, slots=True)
class MarkToMarket:
    """Mark-to-market valuation of an account: market-value NAV + per-symbol weights."""

    nav: float
    cash: float
    by_symbol: dict[str, MarkedPosition]
    unmarked: tuple[str, ...]

    def current_weight(self, symbol: str) -> float:
        """Market-value weight of ``symbol`` (``0.0`` if unheld / unmarked / NAV<=0)."""

        marked = self.by_symbol.get(symbol.upper())
        if marked is None or marked.market_value is None or self.nav <= 0:
            return 0.0
        return marked.market_value / self.nav


def compute_mark_to_market(
    positions: Iterable[tuple[str, float]],
    cash: float,
    marks: dict[str, PriceMark],
) -> MarkToMarket:
    """Value ``positions`` (``(symbol, shares)``) at the latest close in ``marks``.

    ``marks`` is pre-resolved by the caller (via ``PriceProvider.get_marks`` over
    the union of held + target symbols) so a single fetch serves both the NAV and
    any target-only reference prices the caller needs.
    """

    by_symbol: dict[str, MarkedPosition] = {}
    unmarked: list[str] = []
    nav = cash
    for raw_symbol, shares in positions:
        symbol = raw_symbol.upper()
        mark = marks.get(symbol)
        if mark is None:
            by_symbol[symbol] = MarkedPosition(symbol, shares, None, None)
            unmarked.append(symbol)
            continue
        market_value = shares * mark.latest_close
        nav += market_value
        by_symbol[symbol] = MarkedPosition(symbol, shares, mark.latest_close, market_value)
    return MarkToMarket(nav=nav, cash=cash, by_symbol=by_symbol, unmarked=tuple(unmarked))


def latest_close(marks: dict[str, PriceMark], symbol: str) -> float | None:
    """Latest close for ``symbol`` from ``marks`` (None when unmarked).

    Convenience for target-only symbols (not in the held set) whose share count
    the caller still needs to price."""

    mark = marks.get(symbol.upper())
    return mark.latest_close if mark is not None else None


def marks_for(provider: PriceProvider, symbols: Iterable[str]) -> dict[str, PriceMark]:
    """Resolve marks for the de-duplicated, upper-cased, non-empty ``symbols``."""

    wanted = {s.upper() for s in symbols if s}
    return provider.get_marks(wanted) if wanted else {}
