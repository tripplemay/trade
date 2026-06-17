"""B064 F001 — Cn/Hk provider get_stats fundamentals (fake akshare, offline).

Injects fake akshare modules exposing the §23-verified fundamentals functions
(CN: stock_financial_abstract + stock_value_em; HK:
stock_financial_hk_analysis_indicator_em + stock_hk_valuation_baidu) so the
provider → parser → ProviderStats chain is exercised with no network. Pins:
real-shape mapping, canonical→native code adaptation, per-call independent
failure (partial facts), and honest degradation when akshare is absent / all
calls fail (minimal identity, never raises).
"""

from __future__ import annotations

from typing import Any

from workbench_api.symbols.cn_provider import CnSymbolProvider
from workbench_api.symbols.hk_provider import HkSymbolProvider


class _Frame:
    """Minimal akshare DataFrame surface (.columns + .to_dict('records'))."""

    def __init__(self, columns: list[str], records: list[dict[str, Any]]) -> None:
        self.columns = columns
        self._records = records

    def to_dict(self, orient: str) -> list[dict[str, Any]]:
        assert orient == "records"
        return list(self._records)


def _cn_abstract_frame() -> _Frame:
    cols = ["选项", "指标", "20260331", "20251231"]
    rows = [
        {"选项": "常用指标", "指标": "营业总收入", "20260331": 5.47e10, "20251231": 1.72e11},
        {"选项": "常用指标", "指标": "归母净利润", "20260331": 2.72e10, "20251231": 8.23e10},
        {"选项": "常用指标", "指标": "净资产收益率(ROE)", "20260331": 10.57, "20251231": 38.0},
        {"选项": "常用指标", "指标": "毛利率", "20260331": 89.76, "20251231": 91.0},
        {"选项": "常用指标", "指标": "销售净利率", "20260331": 52.22, "20251231": 53.0},
        {"选项": "常用指标", "指标": "资产负债率", "20260331": 12.12, "20251231": 13.0},
        {"选项": "常用指标", "指标": "基本每股收益", "20260331": 21.76, "20251231": 65.0},
        {"选项": "常用指标", "指标": "每股净资产", "20260331": 216.32, "20251231": 210.0},
    ]
    return _Frame(cols, rows)


def _cn_value_frame() -> _Frame:
    cols = ["数据日期", "总市值", "PE(TTM)", "市净率", "总股本"]
    rows = [
        {
            "数据日期": "2026-06-17",
            "总市值": 1.55e12,
            "PE(TTM)": 18.74,
            "市净率": 5.72,
            "总股本": 1.25e9,
        }
    ]
    return _Frame(cols, rows)


class _FakeCnAkshare:
    def __init__(self, *, abstract: _Frame | None, value: _Frame | None) -> None:
        self._abstract = abstract
        self._value = value
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def stock_financial_abstract(self, **kwargs: Any) -> _Frame | None:
        self.calls.append(("stock_financial_abstract", kwargs))
        return self._abstract

    def stock_value_em(self, **kwargs: Any) -> _Frame | None:
        self.calls.append(("stock_value_em", kwargs))
        return self._value


def test_cn_get_stats_maps_fundamentals_and_native_code() -> None:
    fake = _FakeCnAkshare(abstract=_cn_abstract_frame(), value=_cn_value_frame())
    stats = CnSymbolProvider(akshare_module=fake).get_stats("600519.SH")
    assert stats.currency == "CNY"
    assert stats.accounting_standard == "CAS"
    assert stats.country == "China"
    assert stats.market_cap == 1.55e12
    assert stats.trailing_pe == 18.74
    assert stats.return_on_equity is not None
    assert abs(stats.return_on_equity - 0.1057) < 1e-9  # percent → fraction
    assert stats.eps == 21.76
    # canonical 600519.SH → akshare native 6-digit code on both calls.
    assert all(call[1].get("symbol") == "600519" for call in fake.calls)


def test_cn_get_stats_partial_when_value_em_fails() -> None:
    fake = _FakeCnAkshare(abstract=_cn_abstract_frame(), value=None)
    stats = CnSymbolProvider(akshare_module=fake).get_stats("600519.SH")
    assert stats.return_on_equity is not None  # abstract still mapped
    assert stats.market_cap is None  # value_em absent → no valuation


def test_cn_get_stats_degrades_when_akshare_absent() -> None:
    # akshare_module=object() with no fundamentals fns → frame_records returns
    # empty → minimal identity, never raises.
    stats = CnSymbolProvider(akshare_module=object()).get_stats("600519.SH")
    assert stats.currency == "CNY"
    assert stats.accounting_standard == "CAS"
    assert stats.market_cap is None


def _hk_indicator_frame() -> _Frame:
    cols = [
        "SECURITY_NAME_ABBR", "REPORT_DATE", "OPERATE_INCOME", "HOLDER_PROFIT",
        "BASIC_EPS", "BPS", "GROSS_PROFIT_RATIO", "NET_PROFIT_RATIO", "ROE_AVG",
        "DEBT_ASSET_RATIO", "CURRENCY",
    ]
    rows = [
        {
            "SECURITY_NAME_ABBR": "腾讯控股", "REPORT_DATE": "2025-12-31 00:00:00",
            "OPERATE_INCOME": 7.51e11, "HOLDER_PROFIT": 2.24e11, "BASIC_EPS": 24.749,
            "BPS": 126.717, "GROSS_PROFIT_RATIO": 56.21, "NET_PROFIT_RATIO": 30.57,
            "ROE_AVG": 21.13, "DEBT_ASSET_RATIO": 39.13, "CURRENCY": "HKD",
        }
    ]
    return _Frame(cols, rows)


class _FakeHkAkshare:
    def __init__(self, *, indicator: _Frame | None, baidu: dict[str, float] | None) -> None:
        self._indicator = indicator
        self._baidu = baidu or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def stock_financial_hk_analysis_indicator_em(self, **kwargs: Any) -> _Frame | None:
        self.calls.append(("indicator", kwargs))
        return self._indicator

    def stock_hk_valuation_baidu(self, **kwargs: Any) -> _Frame | None:
        self.calls.append(("baidu", kwargs))
        indicator = kwargs["indicator"]
        if indicator not in self._baidu:
            return None
        return _Frame(["date", "value"], [{"date": "2026-06-17", "value": self._baidu[indicator]}])


def test_hk_get_stats_maps_fundamentals_and_native_code() -> None:
    fake = _FakeHkAkshare(
        indicator=_hk_indicator_frame(),
        baidu={"总市值": 40567.38, "市盈率(TTM)": 15.23, "市净率": 3.18},
    )
    stats = HkSymbolProvider(akshare_module=fake).get_stats("700.HK")
    assert stats.currency == "HKD"
    assert stats.accounting_standard == "HKFRS"
    assert stats.country == "Hong Kong"
    assert stats.long_name == "腾讯控股"
    assert stats.market_cap is not None
    assert abs(stats.market_cap - 40567.38e8) < 1.0  # 亿 → raw HKD
    assert stats.trailing_pe == 15.23
    assert stats.price_to_book == 3.18
    assert stats.return_on_equity is not None
    assert abs(stats.return_on_equity - 0.2113) < 1e-9
    assert stats.revenue == 7.51e11
    assert stats.debt_to_equity is None  # HK source has none
    # canonical 700.HK → akshare native 5-digit zero-padded code.
    assert all(call[1].get("symbol") == "00700" for call in fake.calls)


def test_hk_get_stats_partial_when_baidu_unreachable() -> None:
    fake = _FakeHkAkshare(indicator=_hk_indicator_frame(), baidu={})  # baidu all None
    stats = HkSymbolProvider(akshare_module=fake).get_stats("0700.HK")
    assert stats.revenue == 7.51e11  # indicator mapped
    assert stats.market_cap is None  # baidu unreachable → honest null


def test_hk_get_stats_degrades_when_akshare_absent() -> None:
    stats = HkSymbolProvider(akshare_module=object()).get_stats("0700.HK")
    assert stats.currency == "HKD"
    assert stats.accounting_standard == "HKFRS"
    assert stats.market_cap is None
