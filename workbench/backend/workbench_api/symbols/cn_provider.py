"""B061 F002 — China A-share ``SymbolDataProvider`` (akshare main + baostock fallback).

The CN implementation of the B059 provider abstraction. akshare (东财 EOD
history) is primary — B060's P0 spike found it the most reachable from the
overseas prod VM; baostock is the cross-check / fallback when akshare is
unavailable or returns nothing. Both are **data** libraries (databases), never
broker SDKs — the no-broker guard's banlist is futu / tiger / ib / alpaca / …,
which this module never touches.

canonical ↔ native adaptation (path-doc §9.2) lives here: a ``600519.SH``
canonical becomes akshare's ``600519`` (6-digit code) or baostock's
``sh.600519``. The :class:`SymbolRef` value object (F001) is the single source
of truth for that mapping; the akshare/baostock frame → PriceBar parsing is the
shared :mod:`akshare_frames` helper (B062, also used by the HK provider).

request-path safe: imports neither ``trade`` nor any broker SDK. akshare /
baostock are **lazy-imported** inside the fetch methods so the module loads
even where the heavy libs are absent (unit tests inject fakes; production
carries them via pyproject). Every external call is wrapped so a provider
failure degrades to the fallback / an honest ``SymbolNotFoundError`` rather
than a 500.

Full history (not a sample) is fetched per the §8 depth requirement — the
caller (service) passes the same ~13-month window it uses for US symbols.
"""

from __future__ import annotations

import importlib
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.akshare_frames import (
    bars_from_records,
    frame_records,
    to_iso,
    to_ymd,
)
from workbench_api.symbols.akshare_fundamentals import cn_fundamentals_facts
from workbench_api.symbols.provider import (
    CHINA_GAAP,
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
)
from workbench_api.symbols.symbol_ref import SymbolRef

# A short recent window resolves the latest EOD close for a quote.
_QUOTE_WINDOW_DAYS = 10


def _baostock_code(ref: SymbolRef) -> str:
    """canonical 600519.SH -> baostock sh.600519 (sz for .SZ)."""
    prefix = "sh" if ref.canonical.endswith(".SH") else "sz"
    return f"{prefix}.{ref.code}"


class CnSymbolProvider(SymbolDataProvider):
    """A-share EOD provider: akshare primary, baostock cross-check / fallback."""

    name = "akshare"

    def __init__(
        self,
        *,
        akshare_module: Any | None = None,
        baostock_module: Any | None = None,
    ) -> None:
        self._akshare = akshare_module
        self._baostock = baostock_module
        # The source that actually served the most recent fetch (akshare or
        # baostock) — the service records it for honest provenance.
        self.last_source: str = self.name

    # -- module loading (lazy; injectable for tests) --------------------- #

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def _load_baostock(self) -> Any | None:
        if self._baostock is not None:
            return self._baostock
        try:
            return importlib.import_module("baostock")
        except Exception:
            return None

    # -- SymbolDataProvider surface -------------------------------------- #

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        ref = SymbolRef.parse(symbol)
        bars = self._fetch_akshare(ref, from_date, to_date)
        if bars:
            self.last_source = "akshare"
            return bars
        bars = self._fetch_baostock(ref, from_date, to_date)
        if bars:
            self.last_source = "baostock"
            return bars
        raise SymbolNotFoundError(symbol)

    def get_quote(self, symbol: str) -> ProviderQuote:
        today = datetime.now(UTC).date()
        bars = self.get_price_history(
            symbol, today - timedelta(days=_QUOTE_WINDOW_DAYS), today
        )
        if not bars:
            raise SymbolNotFoundError(symbol)
        latest = bars[-1]
        return ProviderQuote(
            symbol=symbol,
            as_of=latest.bar_date,
            close=latest.close,
            source=self.last_source,
        )

    def get_stats(self, symbol: str) -> ProviderStats:
        """B064 F001 — A-share fundamentals (CAS 口径), lazy akshare.

        Two §23-verified-reachable functions: ``stock_financial_abstract``
        (CAS statement metrics + ratios: revenue / net profit / ROE / margins /
        EPS / BPS / debt ratios) and ``stock_value_em`` (valuation: 总市值 /
        PE(TTM) / 市净率 / 总股本). Either can fail independently → the facts are
        best-effort + partial; akshare absent / both failing returns minimal
        identity (CNY) so the service degrades honestly, never a 500.
        """

        ref = SymbolRef.parse(symbol)
        base = ProviderStats(
            symbol=symbol,
            source=self.name,
            currency=ref.currency,
            quote_type="EQUITY",
            country="China",
            accounting_standard=CHINA_GAAP,
        )
        akshare = self._load_akshare()
        if akshare is None:
            return base
        abstract_records, abstract_columns = frame_records(
            akshare, "stock_financial_abstract", symbol=ref.code
        )
        value_records, _ = frame_records(akshare, "stock_value_em", symbol=ref.code)
        facts = cn_fundamentals_facts(
            abstract_records=abstract_records,
            abstract_columns=abstract_columns,
            value_records=value_records,
        )
        return replace(base, **facts)

    # -- per-source fetchers (never raise; empty list on any failure) ---- #

    def _fetch_akshare(
        self, ref: SymbolRef, from_date: date, to_date: date
    ) -> list[PriceBar]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        try:
            frame = akshare.stock_zh_a_hist(
                symbol=ref.code,
                period="daily",
                start_date=to_ymd(from_date),
                end_date=to_ymd(to_date),
                adjust="qfq",
            )
        except Exception:
            return []
        if frame is None:
            return []
        try:
            columns = [str(c) for c in frame.columns]
            records: list[dict[str, Any]] = frame.to_dict("records")
        except Exception:
            return []
        return bars_from_records(records, columns, ref.canonical)

    def _fetch_baostock(
        self, ref: SymbolRef, from_date: date, to_date: date
    ) -> list[PriceBar]:
        baostock = self._load_baostock()
        if baostock is None:
            return []
        try:
            baostock.login()
        except Exception:
            return []
        try:
            result = baostock.query_history_k_data_plus(
                _baostock_code(ref),
                "date,open,high,low,close,volume",
                start_date=to_iso(from_date),
                end_date=to_iso(to_date),
                frequency="d",
                adjustflag="2",  # 2 = 前复权 (matches akshare qfq)
            )
            if getattr(result, "error_code", "0") != "0":
                return []
            columns = list(result.fields)
            records: list[dict[str, Any]] = []
            while result.next():
                records.append(dict(zip(columns, result.get_row_data(), strict=False)))
        except Exception:
            return []
        finally:
            with suppress(Exception):
                baostock.logout()
        return bars_from_records(records, columns, ref.canonical)
