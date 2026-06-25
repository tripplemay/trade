"""B062 F001 — Hong Kong ``SymbolDataProvider`` (akshare HK EOD history).

The HK implementation of the B059 provider abstraction, mirroring the CN
provider (B061). akshare's ``stock_hk_hist`` endpoint serves Hong Kong EOD
history; **baostock has no HK coverage** (A-share only), so there is no
cross-source fallback here — an akshare failure degrades to an honest
``SymbolNotFoundError`` (never a 500).

canonical ↔ native adaptation (path-doc §9.2): a ``0700.HK`` canonical maps to
akshare's 5-digit zero-padded HK code ``00700``. The akshare frame → PriceBar
parsing is the shared :mod:`akshare_frames` helper (same as the CN provider).

request-path safe: imports neither ``trade`` nor any broker SDK; akshare is
lazy-imported (unit tests inject a fake; production carries it via pyproject).
"""

from __future__ import annotations

import importlib
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.akshare_frames import bars_from_records, frame_records
from workbench_api.symbols.akshare_fundamentals import (
    baidu_latest_value,
    hk_fundamentals_facts,
)
from workbench_api.symbols.provider import (
    HK_GAAP,
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
)
from workbench_api.symbols.symbol_ref import SymbolRef

# A short recent window resolves the latest EOD close for a quote.
_QUOTE_WINDOW_DAYS = 10


def _akshare_hk_code(ref: SymbolRef) -> str:
    """canonical 0700.HK -> akshare HK native 00700 (5-digit zero-padded)."""
    return ref.code.zfill(5)


class HkSymbolProvider(SymbolDataProvider):
    """Hong Kong EOD provider via akshare ``stock_hk_hist`` (no baostock fallback)."""

    name = "akshare"

    def __init__(self, *, akshare_module: Any | None = None) -> None:
        self._akshare = akshare_module
        # Mirrors CnSymbolProvider for honest provenance (HK has akshare only).
        self.last_source: str = self.name

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        ref = SymbolRef.parse(symbol)
        bars = self._fetch_akshare(ref, from_date, to_date)
        if bars:
            self.last_source = "akshare"
            return bars
        raise SymbolNotFoundError(symbol)

    def get_quote(self, symbol: str, *, today: date | None = None) -> ProviderQuote:
        # Clock-injectable so unit tests pin the window deterministically — a fixed
        # fake-frame fixture must not age out of [today-N, today] as the calendar moves.
        anchor = today or datetime.now(UTC).date()
        bars = self.get_price_history(
            symbol, anchor - timedelta(days=_QUOTE_WINDOW_DAYS), anchor
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
        """B064 F001 — HK fundamentals (HKFRS 口径), lazy akshare.

        §23-verified-reachable: ``stock_financial_hk_analysis_indicator_em``
        (annual statement metrics + ratios: revenue / net profit / ROE /
        margins / EPS / BPS / debt-to-asset, CURRENCY=HKD) +
        ``stock_hk_valuation_baidu`` (市值 / PE(TTM) / 市净率, a different baidu
        host than the eastmoney push host that timed out in B062). Each call
        can fail independently → best-effort partial facts; akshare absent
        returns minimal identity (HKD), never a 500."""

        ref = SymbolRef.parse(symbol)
        base = ProviderStats(
            symbol=symbol,
            source=self.name,
            currency=ref.currency,
            quote_type="EQUITY",
            country="Hong Kong",
            accounting_standard=HK_GAAP,
        )
        akshare = self._load_akshare()
        if akshare is None:
            return base
        code = _akshare_hk_code(ref)
        indicator_records, _ = frame_records(
            akshare,
            "stock_financial_hk_analysis_indicator_em",
            symbol=code,
            indicator="年度",
        )
        facts = hk_fundamentals_facts(
            indicator_records=indicator_records,
            market_cap_yi=self._baidu_value(akshare, code, "总市值"),
            trailing_pe=self._baidu_value(akshare, code, "市盈率(TTM)"),
            price_to_book=self._baidu_value(akshare, code, "市净率"),
        )
        return replace(base, **facts)

    def _baidu_value(self, akshare: Any, code: str, indicator: str) -> float | None:
        """Latest scalar for one ``stock_hk_valuation_baidu`` indicator."""
        records, _ = frame_records(
            akshare,
            "stock_hk_valuation_baidu",
            symbol=code,
            indicator=indicator,
            period="近一年",
        )
        return baidu_latest_value(records)

    def _fetch_akshare(
        self, ref: SymbolRef, from_date: date, to_date: date
    ) -> list[PriceBar]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        try:
            # B062 fix (B062-F001-PROD-1): use ``stock_hk_daily`` (sina source),
            # NOT ``stock_hk_hist``. The latter hits eastmoney's HK push host
            # (33.push2his.eastmoney.com) which read-times-out reproducibly
            # (verified locally + prod 0700.HK failure) — distinct from the
            # A-share eastmoney host that works. ``stock_hk_daily`` (sina, which
            # B060 confirmed reachable) returns real data. It has no date params
            # — it returns the FULL history — so we filter to the window below.
            frame = akshare.stock_hk_daily(symbol=_akshare_hk_code(ref), adjust="qfq")
        except Exception:
            return []
        if frame is None:
            return []
        try:
            columns = [str(c) for c in frame.columns]
            records: list[dict[str, Any]] = frame.to_dict("records")
        except Exception:
            return []
        bars = bars_from_records(records, columns, ref.canonical)
        return [bar for bar in bars if from_date <= bar.bar_date <= to_date]
