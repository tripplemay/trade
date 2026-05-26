"""Vendor-agnostic company-fundamentals Repository.

The :class:`FundamentalsLoader` abstract base class is the contract every
real fundamentals vendor adapter implements. Strategy code and the
B029 backfill driver depend on this surface, not on the SEC EDGAR JSON
shape or any future paid vendor SDK, so a downstream vendor swap (e.g.
SEC EDGAR free → EODHD paid downgrade if SEC parse cost balloons) is a
new ``<vendor>_loader.py`` file plus a constructor swap, not a code
rewrite.

The companion :class:`FundamentalsRow` is the normalised in-process
shape every adapter must return. Schema matches the B025
``us_quality_momentum/fundamentals.csv`` fixture **column-for-column,
12 fields** (Planner pre-impl adjudication 2026-05-26 #1 — fixture is
source of truth; B029 spec §4.2 草案 漏 ``fiscal_quarter_end`` 已在裁决
后修订).

PIT correctness is the loader's invariant: ``report_date`` is the SEC
filing date (when the 10-K/10-Q became publicly visible), not the
fiscal-quarter-end. Caller-side ``effective_date = report_date + 1
business day`` (B025 §4.1 enforcement) lands in B029 F003 inside
``trade/data/loader.py.load_fundamentals``; F001 only fixes the
in-process row shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class FundamentalsRow:
    """One fiscal quarter's eight ratios for one ticker, in the canonical
    fixture order.

    Field order mirrors ``data/fixtures/us_quality_momentum/fundamentals.csv``
    1:1:

    ``report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,
    fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield``

    ``fiscal_quarter`` uses the compact ``YYYYQn`` form (e.g. ``"2014Q4"``,
    not ``"2014-Q4"``) per fixture convention and the F003 deterministic
    constraint (B025 既有回测 不变).

    ``fiscal_quarter_end`` is the last calendar day of the fiscal quarter
    (e.g. ``date(2014, 12, 31)`` for ``2014Q4``); F002 PIT validation
    asserts ``fiscal_quarter_end < report_date`` and
    ``report_date >= fiscal_quarter_end + 30 days`` directly off this
    column rather than reverse-parsing ``fiscal_quarter`` (decision #1).
    """

    report_date: date
    ticker: str
    fiscal_quarter: str
    fiscal_quarter_end: date
    roe: float
    gross_margin: float
    fcf_yield: float
    debt_to_assets: float
    pe: float
    pb: float
    ev_ebitda: float
    earnings_yield: float


class FundamentalsLoader(ABC):
    """Abstract repository for quarterly company fundamentals.

    Concrete implementations:

    * :class:`workbench_api.data.sec_edgar_loader.SECEDGARFundamentalsLoader`
      — B029 main vendor (SEC EDGAR companyfacts free).
    * Future ``EODHDFundamentalsLoader`` — paid downgrade if EDGAR parse
      cost > 3-5 days (data-source-evaluation §6.2).

    The class is intentionally narrow: ``fetch_quarterly_fundamentals``
    + a ``health_check`` probe is enough for B029. Wider surface (TTM
    rolling, forward estimates, segment data) lands in future batches
    alongside the corresponding tests.
    """

    @abstractmethod
    def fetch_quarterly_fundamentals(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FundamentalsRow]:
        """Return all quarterly fundamentals **filed** in
        ``[from_date, to_date]`` inclusive.

        ``from_date`` / ``to_date`` filter on the SEC filing date
        (``report_date``), not the fiscal-quarter-end. Callers that
        need PIT-correct visibility downstream filter by
        ``effective_date = report_date + 1 business day`` in
        :func:`trade.data.loader.load_fundamentals` (B029 F003).
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Probe vendor connectivity + (where applicable) auth header
        validity.

        Returns ``True`` on a 200 response from a low-impact endpoint
        (typically a single-ticker submissions index fetch). Returns
        ``False`` on auth failure (403 — for SEC EDGAR this means
        missing or invalid User-Agent header). Network / 5xx errors
        propagate so the caller can distinguish "vendor down" from
        "request rejected".
        """
