"""B035 F003 — market-context display catalog.

The ordered ``(series_id, source, label)`` catalog the ``/market-context``
route renders. Labels are **materialised in code here** (inside the
deploy artifact), never read from a repo-root fixture on the request
path — that is the v0.9.32 §12.10 self-containment rule, learned the
hard way in B034 (``ticker_match`` read an un-deployed CSV and 500'd in
production). ``test_market_context_request_self_contained`` enforces it.

The series set mirrors the loaders' ``FRED_SERIES`` +
``ALPHA_VANTAGE_SERIES``; ``test_catalog_matches_loader_series`` fails if
the two ever drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from workbench_api.data.market_context_common import (
    SOURCE_ALPHA_VANTAGE,
    SOURCE_FRED,
)


@dataclass(frozen=True, slots=True)
class SeriesCatalogEntry:
    """One market-context series' display metadata."""

    series_id: str
    source: str
    label: str


SERIES_CATALOG: tuple[SeriesCatalogEntry, ...] = (
    SeriesCatalogEntry("DGS10", SOURCE_FRED, "10-Year Treasury Yield (%)"),
    SeriesCatalogEntry("VIXCLS", SOURCE_FRED, "VIX — Volatility Index"),
    SeriesCatalogEntry("CPIAUCSL", SOURCE_FRED, "CPI — Consumer Price Index"),
    SeriesCatalogEntry("SPY", SOURCE_ALPHA_VANTAGE, "S&P 500 (SPY)"),
    SeriesCatalogEntry("QQQ", SOURCE_ALPHA_VANTAGE, "Nasdaq-100 (QQQ)"),
    SeriesCatalogEntry("UUP", SOURCE_ALPHA_VANTAGE, "US Dollar Index (UUP)"),
)
