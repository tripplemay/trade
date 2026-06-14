"""B062 F002 — data_refresh CN/HK prices loader (akshare-backed).

Routes a canonical A-share / HK ticker to the akshare-backed CN or HK provider
(the workbench symbols layer) so the data_refresh job can fetch real prices and
append them to the unified CSV (:func:`workbench_api.data_refresh.refresh.run_refresh`).

**akshare lives only here in the workbench job** — the ``trade`` engine never
imports it and only reads the resulting CSV (B061 F003 / B062 §3 offline edge;
an AST guard enforces ``trade/`` stays akshare-free). Matches the
``_PricesLoader`` protocol (``fetch_daily_bars``) so it injects exactly like the
Tiingo loader; a provider failure raises ``SymbolNotFoundError``, which
``run_refresh`` counts as a best-effort per-symbol error.
"""

from __future__ import annotations

from datetime import date

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.hk_provider import HkSymbolProvider
from workbench_api.symbols.provider import SymbolDataProvider
from workbench_api.symbols.symbol_ref import SymbolRef


class CnHkPricesLoader:
    """``_PricesLoader`` for A-share + HK canonical tickers (akshare-backed)."""

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        return self._provider_for(ticker).get_price_history(ticker, from_date, to_date)

    @staticmethod
    def _provider_for(ticker: str) -> SymbolDataProvider:
        if SymbolRef.parse(ticker).market == "HK":
            return HkSymbolProvider()
        return CnSymbolProvider()
