"""B059 F001 — symbol-data provider abstraction.

``SymbolDataProvider`` is the swappable seam for the "look up any ticker"
surface. yfinance is the first (free, arbitrary-ticker) implementation; the
abstraction exists so a future swap to Finnhub / FMP / etc. — should
yfinance become unreliable — is a new ``*_provider.py`` file plus a
constructor swap, **not** a rewrite, and so we never pre-pay for a paid feed
(B059 §6 risk mitigation).

This module is **request-path safe**: it imports neither ``trade`` nor any
broker SDK (§12.10.2 / no-broker guards). The concrete yfinance
implementation lives in :mod:`yfinance_provider` so the abstract surface
stays vendor-free.

Method ownership across the B059 batch:

* :meth:`SymbolDataProvider.get_price_history` — F001 price detail
  (history + the derived 52-week range / window returns).
* :meth:`SymbolDataProvider.get_quote` — F002 search-result quick quote.
* :meth:`SymbolDataProvider.get_stats` — F003 fundamentals / instrument
  metadata (``currency`` drives the US-only honest degradation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from workbench_api.data.snapshot_loader import PriceBar


class InvalidSymbolError(ValueError):
    """The requested symbol failed input validation (malformed ticker → 400).

    Distinct from :class:`SymbolNotFoundError`: this fires *before* any
    external call (bad characters / length), so we never hit the provider
    for obviously invalid input.
    """


class SymbolNotFoundError(LookupError):
    """The provider has no EOD data for a syntactically valid symbol —
    unknown / delisted / non-covered ticker (→ 404, actionable copy)."""

    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.symbol = symbol


class SymbolRateLimitedError(RuntimeError):
    """The per-request rate-limit guard halted an external fetch before it
    reached the provider (→ 429). The default guard is a no-op; this exists
    so an injected enforcing guard can short-circuit a lookup storm."""


@dataclass(frozen=True, slots=True)
class ProviderQuote:
    """The latest EOD close for a symbol (close-of-day, never intraday)."""

    symbol: str
    as_of: date
    close: float
    source: str


@dataclass(frozen=True, slots=True)
class ProviderStats:
    """Instrument identity + fundamentals metadata the source knows about a symbol.

    Identity (name / currency / exchange / quote_type / country / sector /
    industry) plus best-effort fundamental ratios. All fields beyond
    ``symbol`` / ``source`` are optional — yfinance's ``.info`` is best-effort
    and may be partial or unavailable; consumers degrade honestly rather than
    fabricate. Consumed by B059 F003 (fundamentals surface) + the detail page
    header.
    """

    symbol: str
    source: str
    # Identity
    long_name: str | None = None
    currency: str | None = None
    exchange: str | None = None
    quote_type: str | None = None
    country: str | None = None
    sector: str | None = None
    industry: str | None = None
    # Fundamentals (best-effort; see B059 F003 US-equity gating in the service)
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    dividend_yield: float | None = None
    profit_margins: float | None = None
    gross_margins: float | None = None
    revenue: float | None = None
    shares_outstanding: float | None = None
    return_on_equity: float | None = None
    debt_to_equity: float | None = None


class SymbolDataProvider(ABC):
    """Abstract EOD data source for arbitrary tickers."""

    name: str

    @abstractmethod
    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        """Return daily OHLCV bars in ``[from_date, to_date]`` inclusive,
        oldest first. Raise :class:`SymbolNotFoundError` when the source has
        no data for ``symbol``."""

    @abstractmethod
    def get_quote(self, symbol: str) -> ProviderQuote:
        """Return the latest EOD close. Raise :class:`SymbolNotFoundError`
        when the source has no data for ``symbol``."""

    @abstractmethod
    def get_stats(self, symbol: str) -> ProviderStats:
        """Return best-effort instrument metadata. Never raises for a missing
        ``.info`` — returns a minimal :class:`ProviderStats` instead."""
