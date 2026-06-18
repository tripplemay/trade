"""B061 F002 — CnSymbolProvider (akshare main + baostock fallback) + routing.

Offline + deterministic: akshare / baostock are injected as fakes (no network,
no heavy libs needed). A minimal frame stub mimics the akshare DataFrame
surface the provider actually uses (``.columns`` + ``.to_dict("records")``) so
the test never imports pandas. Covers: akshare primary parse + canonical→native
adaptation, baostock fallback (incl. native code + adjustflag), both-down →
SymbolNotFoundError, quote, CNY stats, market routing, and the service
integration that persists market / currency / honest source to the cache.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_price_cache import SymbolPriceCacheRepository
from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.provider import SymbolNotFoundError
from workbench_api.symbols.service import _resolve_provider, get_symbol_price_detail
from workbench_api.symbols.yfinance_provider import YFinanceSymbolProvider

_TODAY = date(2026, 6, 13)


class _FakeFrame:
    """Minimal stand-in for the akshare DataFrame surface the provider uses."""

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

    def stock_zh_a_hist(
        self, *, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> _FakeFrame | None:
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            }
        )
        if self._raises:
            raise RuntimeError("akshare unreachable")
        return self._frame


class _FakeBsResult:
    def __init__(self, fields: list[str], rows: list[list[str]], error_code: str = "0") -> None:
        self.fields = fields
        self._rows = rows
        self._index = -1
        self.error_code = error_code
        self.error_msg = ""

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._index]


class _FakeBaostock:
    def __init__(self, result: _FakeBsResult | None = None, *, raises: bool = False) -> None:
        self._result = result
        self._raises = raises
        self.queries: list[dict[str, Any]] = []
        self.logout_called = False

    def login(self) -> Any:
        return type("Login", (), {"error_code": "0", "error_msg": ""})()

    def query_history_k_data_plus(
        self,
        code: str,
        fields: str,
        *,
        start_date: str,
        end_date: str,
        frequency: str,
        adjustflag: str,
    ) -> _FakeBsResult | None:
        self.queries.append({"code": code, "fields": fields, "adjustflag": adjustflag})
        if self._raises:
            raise RuntimeError("baostock unreachable")
        return self._result

    def logout(self) -> None:
        self.logout_called = True


def _ak_frame() -> _FakeFrame:
    # Chinese akshare headers; rows deliberately out of date order to test sort.
    cols = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
    rows: list[tuple[Any, ...]] = [
        ("2026-06-12", 1620.0, 1630.0, 1635.0, 1615.0, 120000),
        ("2026-06-10", 1600.0, 1610.0, 1615.0, 1595.0, 100000),
        ("2026-06-11", 1610.0, 1620.0, 1625.0, 1605.0, 110000),
    ]
    records = [dict(zip(cols, row, strict=True)) for row in rows]
    return _FakeFrame(columns=cols, records=records)


def _bs_result() -> _FakeBsResult:
    return _FakeBsResult(
        fields=["date", "open", "high", "low", "close", "volume"],
        rows=[
            ["2026-06-10", "1600", "1615", "1595", "1610", "100000"],
            ["2026-06-11", "1610", "1625", "1605", "1620", "110000"],
        ],
    )


class TestAksharePrimary:
    def test_parses_chinese_columns_sorts_and_adapts_code(self) -> None:
        fake = _FakeAkshare(_ak_frame())
        provider = CnSymbolProvider(akshare_module=fake)
        bars = provider.get_price_history("600519.SH", _TODAY - timedelta(days=400), _TODAY)
        assert [b.bar_date for b in bars] == [
            date(2026, 6, 10),
            date(2026, 6, 11),
            date(2026, 6, 12),
        ]
        assert bars[-1].close == 1630.0
        assert bars[-1].adj_close == 1630.0  # qfq close
        assert bars[0].ticker == "600519.SH"
        assert bars[0].volume == 100000
        assert provider.last_source == "akshare"
        # canonical 600519.SH -> akshare native code 600519 + qfq
        assert fake.calls[0]["symbol"] == "600519"
        assert fake.calls[0]["adjust"] == "qfq"

    def test_get_quote_returns_latest_close(self) -> None:
        provider = CnSymbolProvider(akshare_module=_FakeAkshare(_ak_frame()))
        quote = provider.get_quote("600519.SH")
        assert quote.close == 1630.0
        assert quote.as_of == date(2026, 6, 12)
        assert quote.source == "akshare"

    def test_get_stats_minimal_cny(self) -> None:
        provider = CnSymbolProvider(akshare_module=_FakeAkshare(_ak_frame()))
        stats = provider.get_stats("600519.SH")
        assert stats.currency == "CNY"
        assert stats.source == "akshare"
        assert stats.quote_type == "EQUITY"


class TestBaostockFallback:
    def test_akshare_failure_falls_back_and_adapts_native_code(self) -> None:
        bs = _FakeBaostock(_bs_result())
        provider = CnSymbolProvider(
            akshare_module=_FakeAkshare(raises=True), baostock_module=bs
        )
        bars = provider.get_price_history("600519.SH", _TODAY - timedelta(days=400), _TODAY)
        assert len(bars) == 2
        assert bars[-1].close == 1620.0
        assert provider.last_source == "baostock"
        assert bs.queries[0]["code"] == "sh.600519"  # canonical -> baostock native
        assert bs.queries[0]["adjustflag"] == "2"  # 前复权 (matches qfq)
        assert bs.logout_called is True

    def test_shenzhen_symbol_maps_to_sz_prefix(self) -> None:
        bs = _FakeBaostock(_bs_result())
        provider = CnSymbolProvider(
            akshare_module=_FakeAkshare(raises=True), baostock_module=bs
        )
        provider.get_price_history("000001.SZ", _TODAY - timedelta(days=400), _TODAY)
        assert bs.queries[0]["code"] == "sz.000001"

    def test_empty_akshare_frame_falls_back(self) -> None:
        bs = _FakeBaostock(_bs_result())
        provider = CnSymbolProvider(
            akshare_module=_FakeAkshare(_FakeFrame(columns=[], records=[])),
            baostock_module=bs,
        )
        bars = provider.get_price_history("600519.SH", _TODAY - timedelta(days=400), _TODAY)
        assert len(bars) == 2
        assert provider.last_source == "baostock"


class _FakeAkshareWithSina:
    """akshare fake whose eastmoney ``stock_zh_a_hist`` is down but sina works.

    Models the B065 prod-VM reality: the eastmoney push2his host
    ConnectionErrors while sina's ``stock_zh_a_daily`` is reachable. sina takes no
    date params (it returns the full history); the provider filters to the window.
    """

    def __init__(self, sina_frame: _FakeFrame) -> None:
        self._sina_frame = sina_frame
        self.hist_calls = 0
        self.sina_calls: list[dict[str, Any]] = []

    def stock_zh_a_hist(
        self, *, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> _FakeFrame | None:
        self.hist_calls += 1
        raise RuntimeError("eastmoney push2his ConnectionError")

    def stock_zh_a_daily(self, *, symbol: str, adjust: str) -> _FakeFrame | None:
        self.sina_calls.append({"symbol": symbol, "adjust": adjust})
        return self._sina_frame


def _sina_frame() -> _FakeFrame:
    # sina stock_zh_a_daily columns; one row is OUTSIDE the requested window to
    # prove the provider's date filtering (sina returns full history).
    cols = ["date", "open", "high", "low", "close", "volume", "outstanding_share"]
    rows: list[tuple[Any, ...]] = [
        ("2024-01-01", 900.0, 905.0, 895.0, 902.0, 90000, 1e9),  # out of window
        ("2026-06-10", 1600.0, 1615.0, 1595.0, 1610.0, 100000, 1e9),
        ("2026-06-11", 1610.0, 1625.0, 1605.0, 1620.0, 110000, 1e9),
        ("2026-06-12", 1620.0, 1635.0, 1615.0, 1630.0, 120000, 1e9),
    ]
    records = [dict(zip(cols, row, strict=True)) for row in rows]
    return _FakeFrame(columns=cols, records=records)


class TestSinaMiddleTier:
    def test_eastmoney_down_falls_to_sina_and_filters_window(self) -> None:
        fake = _FakeAkshareWithSina(_sina_frame())
        provider = CnSymbolProvider(akshare_module=fake)
        bars = provider.get_price_history(
            "600519.SH", _TODAY - timedelta(days=400), _TODAY
        )
        # The 2024-01-01 row is filtered out; 3 in-window bars remain, sorted.
        assert [b.bar_date for b in bars] == [
            date(2026, 6, 10),
            date(2026, 6, 11),
            date(2026, 6, 12),
        ]
        assert bars[-1].close == 1630.0
        assert provider.last_source == "sina"
        assert fake.hist_calls == 1  # eastmoney tried first
        # canonical 600519.SH -> sina code sh600519 + qfq
        assert fake.sina_calls[0]["symbol"] == "sh600519"
        assert fake.sina_calls[0]["adjust"] == "qfq"

    def test_shenzhen_symbol_maps_to_sz_prefix(self) -> None:
        fake = _FakeAkshareWithSina(_sina_frame())
        provider = CnSymbolProvider(akshare_module=fake)
        provider.get_price_history("000001.SZ", _TODAY - timedelta(days=400), _TODAY)
        assert fake.sina_calls[0]["symbol"] == "sz000001"

    def test_sina_preferred_over_baostock_when_reachable(self) -> None:
        fake = _FakeAkshareWithSina(_sina_frame())
        bs = _FakeBaostock(_bs_result())
        provider = CnSymbolProvider(akshare_module=fake, baostock_module=bs)
        provider.get_price_history("600519.SH", _TODAY - timedelta(days=400), _TODAY)
        # sina served → baostock (the slower login fallback) is never queried.
        assert provider.last_source == "sina"
        assert bs.queries == []


class TestBothUnavailable:
    def test_both_sources_failing_raises_symbol_not_found(self) -> None:
        # Both sources present but failing (unreachable / empty) → honest
        # SymbolNotFoundError, never a 500. Injected raising fakes keep this
        # deterministic + offline (a non-injected real-lazy-import variant
        # would hit the network in CI where akshare IS installed).
        provider = CnSymbolProvider(
            akshare_module=_FakeAkshare(raises=True),
            baostock_module=_FakeBaostock(raises=True),
        )
        with pytest.raises(SymbolNotFoundError):
            provider.get_price_history("600519.SH", _TODAY - timedelta(days=400), _TODAY)


class TestRouting:
    def test_cn_canonical_routes_to_cn_provider(self) -> None:
        assert isinstance(_resolve_provider("600519.SH"), CnSymbolProvider)

    def test_us_bare_routes_to_yfinance(self) -> None:
        assert isinstance(_resolve_provider("AAPL"), YFinanceSymbolProvider)


class TestServiceIntegration:
    def test_cn_lookup_persists_market_currency_and_source(self, initialised_db: str) -> None:
        with Session(get_engine()) as session:
            provider = CnSymbolProvider(akshare_module=_FakeAkshare(_ak_frame()))
            detail = get_symbol_price_detail(
                session, "600519.sh", provider=provider, today=lambda: _TODAY
            )
            session.commit()

            assert detail.symbol == "600519.SH"  # canonical
            assert detail.currency == "CNY"
            assert detail.source == "akshare"
            assert detail.close == 1630.0

            repo = SymbolPriceCacheRepository(session)
            rows = repo.bars_since("600519.SH", _TODAY - timedelta(days=400))
            assert rows
            assert rows[0].market == "CN"
            assert rows[0].currency == "CNY"
            assert rows[0].source == "akshare"
