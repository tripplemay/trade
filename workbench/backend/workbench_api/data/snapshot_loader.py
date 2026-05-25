"""Vendor-agnostic market-data snapshot Repository.

The ``SnapshotLoader`` abstract base class is the contract every real-
market-data vendor adapter implements. Strategy and ingest code depend
on this surface, not on any specific vendor SDK or HTTP shape, so a
future vendor swap (e.g. Tiingo → Massive (ex-Polygon.io) → yfinance
cross-check) is a new ``<vendor>_loader.py`` file plus a constructor
swap, not a code rewrite.

Companion ``PriceBar`` dataclass is the normalised in-process shape every
adapter must return — vendor-specific JSON quirks (``adjClose`` vs
``adjusted_close``, ISO date strings vs epoch ms) are absorbed by the
adapter before any caller sees a bar.

PIT correctness (point-in-time) is the loader's invariant: a call with
``to_date == today`` returns at most bars whose ``bar_date <= today``,
and adjustments (splits / dividends) are applied per the vendor's
public convention as of ``to_date``. Backfill orchestration that needs
stricter PIT semantics (e.g. unadjusted bars + a separate corporate-
actions log) lands in B028+; B027 only fixes the in-process bar shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Daily OHLCV bar normalised across vendors.

    ``adj_close`` is the split/dividend-adjusted close per the source
    vendor's convention at the time of retrieval. Callers that need
    raw close values should use ``close``; backtests should typically
    use ``adj_close``. ``volume`` is the share count, never notional.
    """

    ticker: str
    bar_date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class SnapshotLoader(ABC):
    """Abstract repository for real market-data snapshots.

    Concrete implementations:

    * :class:`workbench_api.data.tiingo_loader.TiingoSnapshotLoader` —
      B027 main vendor (Tiingo Starter $10/月).
    * ``YFinanceSnapshotLoader`` — B028 free cross-check (planned).
    * ``MassiveSnapshotLoader`` — backup for B028+ if Tiingo coverage
      gaps surface (formerly Polygon.io).

    The class is intentionally narrow: ``fetch_daily_bars`` + a
    ``health_check`` probe is enough for B027 (no live order routing,
    no intraday, no fundamentals). Wider surface lands in future
    batches alongside the corresponding tests.
    """

    @abstractmethod
    def fetch_daily_bars(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[PriceBar]:
        """Return daily OHLCV bars in ``[from_date, to_date]`` inclusive.

        PIT-correct: must not return bars dated after ``to_date``. If
        ``to_date`` is in the future, implementations clamp it to
        ``date.today()`` rather than ask the vendor for nonexistent
        future data.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Probe vendor connectivity + API key validity.

        Returns ``True`` on a 200 response from a low-impact endpoint
        (typically a single-ticker single-day fetch). Returns ``False``
        on auth failure (401/403). Network / 5xx errors propagate so
        the caller can distinguish "vendor down" from "key invalid".
        """
