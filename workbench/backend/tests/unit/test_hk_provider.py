"""B062 F001 — HkSymbolProvider (akshare HK history, no baostock) + routing.

Offline + deterministic: akshare is injected as a fake (no network, no heavy
libs). A minimal frame stub mimics the akshare DataFrame surface the provider
uses (``.columns`` + ``.to_dict("records")``). Covers: akshare parse + the
0700.HK -> 00700 (5-digit zero-pad) native adaptation, no-baostock-fallback ->
SymbolNotFoundError on failure, quote, HKD stats, market routing (HK vs CN vs
US), and the service integration persisting market=HK / currency=HKD / source.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_price_cache import SymbolPriceCacheRepository
from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.hk_provider import HkSymbolProvider
from workbench_api.symbols.provider import SymbolNotFoundError
from workbench_api.symbols.service import _resolve_provider, get_symbol_price_detail
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider

_TODAY = date(2026, 6, 13)


class _FakeFrame:
    def __init__(self, columns: list[str], records: list[dict[str, Any]]) -> None:
        self.columns = columns
        self._records = records

    def to_dict(self, orient: str) -> list[dict[str, Any]]:
        assert orient == "records"
        return list(self._records)


class _FakeAkshare:
    def __init__(self, frame: _FakeFrame | None = None, *, raises: bool = False) -> None:
        self._frame = frame
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def stock_hk_hist(
        self, *, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> _FakeFrame | None:
        self.calls.append({"symbol": symbol, "period": period, "adjust": adjust})
        if self._raises:
            raise RuntimeError("akshare HK unreachable")
        return self._frame


def _hk_frame() -> _FakeFrame:
    cols = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
    rows: list[tuple[Any, ...]] = [
        ("2026-06-12", 370.0, 375.0, 378.0, 369.0, 12_000_000),
        ("2026-06-10", 360.0, 365.0, 366.0, 359.0, 10_000_000),
        ("2026-06-11", 365.0, 370.0, 372.0, 364.0, 11_000_000),
    ]
    records = [dict(zip(cols, row, strict=True)) for row in rows]
    return _FakeFrame(columns=cols, records=records)


class TestAksharePrimary:
    def test_parses_sorts_and_zero_pads_native_code(self) -> None:
        fake = _FakeAkshare(_hk_frame())
        provider = HkSymbolProvider(akshare_module=fake)
        bars = provider.get_price_history("0700.HK", _TODAY - timedelta(days=400), _TODAY)
        assert [b.bar_date for b in bars] == [
            date(2026, 6, 10),
            date(2026, 6, 11),
            date(2026, 6, 12),
        ]
        assert bars[-1].close == 375.0
        assert bars[-1].adj_close == 375.0
        assert bars[0].ticker == "0700.HK"
        assert provider.last_source == "akshare"
        # canonical 0700.HK -> akshare HK native 00700 (5-digit zero-pad) + qfq
        assert fake.calls[0]["symbol"] == "00700"
        assert fake.calls[0]["adjust"] == "qfq"

    def test_get_quote_returns_latest_close(self) -> None:
        provider = HkSymbolProvider(akshare_module=_FakeAkshare(_hk_frame()))
        quote = provider.get_quote("0700.HK")
        assert quote.close == 375.0
        assert quote.as_of == date(2026, 6, 12)
        assert quote.source == "akshare"

    def test_get_stats_minimal_hkd(self) -> None:
        provider = HkSymbolProvider(akshare_module=_FakeAkshare(_hk_frame()))
        stats = provider.get_stats("0700.HK")
        assert stats.currency == "HKD"
        assert stats.source == "akshare"
        assert stats.quote_type == "EQUITY"


class TestFailure:
    def test_akshare_failure_raises_not_found_no_fallback(self) -> None:
        # HK has no baostock fallback — an akshare failure is an honest 404.
        provider = HkSymbolProvider(akshare_module=_FakeAkshare(raises=True))
        with pytest.raises(SymbolNotFoundError):
            provider.get_price_history("0700.HK", _TODAY - timedelta(days=400), _TODAY)

    def test_empty_frame_raises_not_found(self) -> None:
        provider = HkSymbolProvider(
            akshare_module=_FakeAkshare(_FakeFrame(columns=[], records=[]))
        )
        with pytest.raises(SymbolNotFoundError):
            provider.get_price_history("0700.HK", _TODAY - timedelta(days=400), _TODAY)


class TestRouting:
    def test_hk_routes_to_hk_provider(self) -> None:
        assert isinstance(_resolve_provider("0700.HK"), HkSymbolProvider)

    def test_cn_routes_to_cn_provider(self) -> None:
        assert isinstance(_resolve_provider("600519.SH"), CnSymbolProvider)

    def test_us_routes_to_yfinance(self) -> None:
        assert isinstance(_resolve_provider("AAPL"), YFinanceSymbolProvider)


class TestServiceIntegration:
    def test_hk_lookup_persists_market_currency_and_source(self, initialised_db: str) -> None:
        with Session(get_engine()) as session:
            provider = HkSymbolProvider(akshare_module=_FakeAkshare(_hk_frame()))
            detail = get_symbol_price_detail(
                session, "0700.hk", provider=provider, today=lambda: _TODAY
            )
            session.commit()

            assert detail.symbol == "0700.HK"  # canonical
            assert detail.currency == "HKD"
            assert detail.source == "akshare"
            assert detail.close == 375.0

            repo = SymbolPriceCacheRepository(session)
            rows = repo.bars_since("0700.HK", _TODAY - timedelta(days=400))
            assert rows
            assert rows[0].market == "HK"
            assert rows[0].currency == "HKD"
            assert rows[0].source == "akshare"
