"""B037 F001 — Day P&L price provider.

``build_home`` marks the latest account positions to market to compute a
read-only Day P&L. It depends on this thin :class:`PriceProvider`
protocol — "give me the latest close and the prior trading day's close
for these symbols" — rather than on the storage details. That seam is
what lets the F001 tests inject a fake provider returning known closes
(so the mark-to-market arithmetic asserts an exact, deterministic P&L)
while production reads the ``price_snapshot`` table the daily
``workbench-prices`` timer fills.

A symbol is only marked when **two** stored closes exist (latest + prior
trading day). Symbols with fewer than two observations are simply absent
from the returned dict, and ``build_home`` treats a position with no mark
as contributing nothing to Day P&L (degrading to ``null`` when no
position can be marked) — the spec's empty-state path.

B111 F004 fix-round: :class:`PriceMark` additionally carries
``latest_date`` (the ``obs_date`` of the latest close) so the paper
engine can enforce the unified execution caliber — fills strictly AFTER
the target's signal session (no same-session fills). It defaults to
``None`` so existing Day-P&L callers and test fakes are unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session

from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository


@dataclass(frozen=True, slots=True)
class PriceMark:
    """Latest close + prior trading-day close for one symbol."""

    latest_close: float
    prior_close: float
    # obs_date of ``latest_close`` (B111 F004 fix-round); ``None`` when the
    # caller does not need date-aware fill timing (Day P&L path / test fakes).
    latest_date: date | None = None


class PriceProvider(Protocol):
    """Resolve per-symbol marks for the Home Day P&L computation."""

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        """Return ``{SYMBOL: PriceMark}`` for symbols that have both a
        latest and a prior close. Symbols without two closes are omitted.
        Keys are upper-cased."""
        ...


class DbPriceProvider:
    """Production :class:`PriceProvider` reading the ``price_snapshot`` table.

    Self-contained per v0.9.32 §12.10: the only data source is the DB
    table the daily timer populated — no repo-root fixture / file read.
    """

    def __init__(self, session: Session) -> None:
        self._repo = PriceSnapshotRepository(session)

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        marks: dict[str, PriceMark] = {}
        for symbol in {s.upper() for s in symbols if s}:
            rows = self._repo.latest_two_by_symbol(symbol)
            if len(rows) == 2:
                marks[symbol] = PriceMark(
                    latest_close=float(rows[0].close),
                    prior_close=float(rows[1].close),
                    latest_date=rows[0].obs_date,
                )
        return marks
