"""B064 F001 — akshare_fundamentals pure parser (units + shape mapping).

Offline + deterministic: feeds the parser plain records mirroring the §23-real
akshare shapes (CN stock_financial_abstract pivot + stock_value_em row; HK
stock_financial_hk_analysis_indicator_em + stock_hk_valuation_baidu) and pins
the unit normalisation that lets the existing yfinance-shaped detail-page
formatter be reused unchanged: margins / ROE → fraction; debt ratios → percent;
market cap / revenue / shares → raw currency (HK baidu 亿 × 1e8).
"""

from __future__ import annotations

from datetime import date

from workbench_api.symbols.akshare_fundamentals import (
    baidu_latest_value,
    cn_fundamentals_facts,
    hk_fundamentals_facts,
)

# --- CN fixtures (real shape: 选项/指标 pivot + value_em row) --------------- #
_CN_ABSTRACT_COLS = ["选项", "指标", "20260331", "20251231"]


def _row(group: str, metric: str, latest: float, prior: float) -> dict[str, object]:
    return {"选项": group, "指标": metric, "20260331": latest, "20251231": prior}


_CN_ABSTRACT = [
    _row("常用指标", "营业总收入", 54702912385.23, 172054171890.91),
    _row("常用指标", "归母净利润", 27242512886.45, 82320067101.68),
    _row("常用指标", "净资产收益率(ROE)", 10.57, 38.0),
    _row("常用指标", "毛利率", 89.759217, 91.0),
    _row("常用指标", "销售净利率", 52.224488, 53.0),
    _row("常用指标", "资产负债率", 12.122748, 13.0),
    _row("常用指标", "基本每股收益", 21.76, 65.0),
    _row("常用指标", "每股净资产", 216.322349, 210.0),
    _row("财务风险", "产权比率", 14.316652, 15.0),
]
_CN_VALUE = [
    {"数据日期": "2026-06-16", "总市值": 1.0, "PE(TTM)": 1.0, "市净率": 1.0, "总股本": 1.0},
    {
        "数据日期": "2026-06-17",
        "总市值": 1550101185240.0,
        "PE(TTM)": 18.74,
        "市净率": 5.72,
        "总股本": 1250081601,
    },
]


def test_cn_facts_units_and_latest_period() -> None:
    facts = cn_fundamentals_facts(
        abstract_records=_CN_ABSTRACT,
        abstract_columns=_CN_ABSTRACT_COLS,
        value_records=_CN_VALUE,
    )
    # Latest report period selected (not the older 20251231 column).
    assert facts["as_of_report"] == date(2026, 3, 31)
    assert facts["revenue"] == 54702912385.23
    assert facts["net_income"] == 27242512886.45
    # Percent → fraction (yfinance convention).
    assert abs(facts["return_on_equity"] - 0.1057) < 1e-9
    assert abs(facts["gross_margins"] - 0.89759217) < 1e-9
    assert abs(facts["profit_margins"] - 0.52224488) < 1e-9
    # Debt ratios kept as percent (yfinance debtToEquity convention).
    assert facts["debt_to_asset"] == 12.122748
    assert facts["debt_to_equity"] == 14.316652  # 产权比率
    assert facts["eps"] == 21.76
    assert facts["book_value_per_share"] == 216.322349
    # Valuation: newest value_em row picked; raw 元 market cap.
    assert facts["market_cap"] == 1550101185240.0
    assert facts["trailing_pe"] == 18.74
    assert facts["price_to_book"] == 5.72
    assert facts["shares_outstanding"] == 1250081601.0


def test_cn_facts_empty_inputs_yield_empty() -> None:
    assert cn_fundamentals_facts(
        abstract_records=[], abstract_columns=[], value_records=[]
    ) == {}


def test_cn_facts_partial_when_only_value_em_reachable() -> None:
    # abstract unreachable, value_em ok → valuation present, statement metrics absent.
    facts = cn_fundamentals_facts(
        abstract_records=[], abstract_columns=[], value_records=_CN_VALUE
    )
    assert facts["market_cap"] == 1550101185240.0
    assert "return_on_equity" not in facts
    assert "as_of_report" not in facts


def test_cn_facts_indicator_fallback_across_groups() -> None:
    # 选项 relabelled (akshare drift) → 指标-only fallback still resolves.
    abstract = [
        {"选项": "其它分组", "指标": "营业总收入", "20260331": 100.0},
        {"选项": "其它分组", "指标": "净资产收益率(ROE)", "20260331": 20.0},
    ]
    facts = cn_fundamentals_facts(
        abstract_records=abstract, abstract_columns=["选项", "指标", "20260331"], value_records=[]
    )
    assert facts["revenue"] == 100.0
    assert abs(facts["return_on_equity"] - 0.20) < 1e-9


# --- HK fixtures (real shape: English-keyed indicator + baidu date/value) --- #
_HK_INDICATOR = [
    {
        "SECURITY_NAME_ABBR": "腾讯控股",
        "REPORT_DATE": "2025-12-31 00:00:00",
        "OPERATE_INCOME": 751766000000,
        "HOLDER_PROFIT": 224842000000,
        "BASIC_EPS": 24.749,
        "BPS": 126.717,
        "GROSS_PROFIT_RATIO": 56.2134,
        "NET_PROFIT_RATIO": 30.568,
        "ROE_AVG": 21.1347,
        "DEBT_ASSET_RATIO": 39.133,
        "CURRENCY": "HKD",
    },
    {
        "SECURITY_NAME_ABBR": "腾讯控股",
        "REPORT_DATE": "2024-12-31 00:00:00",
        "OPERATE_INCOME": 660257000000,
        "HOLDER_PROFIT": 194073000000,
        "BASIC_EPS": 20.938,
        "BPS": 106.888,
        "GROSS_PROFIT_RATIO": 52.9,
        "NET_PROFIT_RATIO": 29.7,
        "ROE_AVG": 21.77,
        "DEBT_ASSET_RATIO": 40.8,
        "CURRENCY": "HKD",
    },
]


def test_hk_facts_units_and_latest_report() -> None:
    facts = hk_fundamentals_facts(
        indicator_records=_HK_INDICATOR,
        market_cap_yi=40567.38,
        trailing_pe=15.23,
        price_to_book=3.18,
    )
    assert facts["long_name"] == "腾讯控股"
    assert facts["currency"] == "HKD"
    assert facts["as_of_report"] == date(2025, 12, 31)  # newest report, not 2024
    assert facts["revenue"] == 751766000000
    assert facts["net_income"] == 224842000000
    assert facts["eps"] == 24.749
    assert facts["book_value_per_share"] == 126.717
    assert abs(facts["gross_margins"] - 0.562134) < 1e-9
    assert abs(facts["profit_margins"] - 0.30568) < 1e-9
    assert abs(facts["return_on_equity"] - 0.211347) < 1e-9
    assert facts["debt_to_asset"] == 39.133
    # baidu 总市值 亿 → raw HKD.
    assert abs(facts["market_cap"] - 40567.38e8) < 1.0
    assert facts["trailing_pe"] == 15.23
    assert facts["price_to_book"] == 3.18
    # HK source has no debt-to-equity → absent (honest).
    assert "debt_to_equity" not in facts


def test_hk_facts_partial_when_baidu_unreachable() -> None:
    facts = hk_fundamentals_facts(
        indicator_records=_HK_INDICATOR,
        market_cap_yi=None,
        trailing_pe=None,
        price_to_book=None,
    )
    assert facts["revenue"] == 751766000000
    assert "market_cap" not in facts
    assert "trailing_pe" not in facts


def test_hk_facts_empty_indicator_yields_valuation_only() -> None:
    facts = hk_fundamentals_facts(
        indicator_records=[], market_cap_yi=100.0, trailing_pe=10.0, price_to_book=2.0
    )
    assert facts["market_cap"] == 100.0e8
    assert "revenue" not in facts
    assert "long_name" not in facts


def test_baidu_latest_value_picks_newest() -> None:
    assert (
        baidu_latest_value(
            [{"date": date(2026, 6, 16), "value": 1.0}, {"date": date(2026, 6, 17), "value": 9.9}]
        )
        == 9.9
    )
    assert baidu_latest_value([]) is None
    # string dates (CN baidu) also parse.
    assert baidu_latest_value([{"date": "2026-06-17", "value": 3.3}]) == 3.3
