"""B065 F002 — A-share CAS fundamentals → unified ``fundamentals.csv`` schema.

Covers the disclosure-date (point-in-time) mapping, the CAS → FUNDAMENTALS_HEADER
ratio mapping (percent→fraction, fcf_yield with CFO fallback, ev_ebitda null),
the akshare loader (faked frames), the §12.10.2/§26.2 boundary, and the **core
acceptance** that the offline ``trade`` ``quality_score`` produces a real ranking
on a CN-only frame (the spec §1 insight: same schema → factor works on A-shares).

Real akshare values are exercised at L2 on the VM (Codex F004); these assert
logic/mapping/schema, not market numbers (v0.9.21 fixture-vs-real signal).
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from workbench_api.data_refresh.cn_fundamentals import (
    CnFundamentalsLoader,
    cas_disclosure_date,
    cn_fundamentals_rows,
    fiscal_quarter_label,
)
from workbench_api.data_refresh.cn_universe import MarketCapBar
from workbench_api.data_refresh.refresh import FUNDAMENTALS_HEADER

# --------------------------------------------------------------------------- #
# disclosure date (point-in-time, no lookahead) + fiscal quarter
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("period_end", "expected"),
    [
        (date(2024, 3, 31), date(2024, 4, 30)),  # Q1 by Apr 30
        (date(2024, 6, 30), date(2024, 8, 31)),  # Semi by Aug 31
        (date(2024, 9, 30), date(2024, 10, 31)),  # Q3 by Oct 31
        (date(2024, 12, 31), date(2025, 4, 30)),  # Annual by NEXT Apr 30
    ],
)
def test_cas_disclosure_date_is_conservative_deadline(period_end: date, expected: date) -> None:
    disclosed = cas_disclosure_date(period_end)
    assert disclosed == expected
    assert disclosed >= period_end  # never before the period end (no lookahead)


def test_cas_disclosure_date_nonstandard_period_uses_lag() -> None:
    # A non-standard period end → conservative ~quarter lag, still after the period.
    out = cas_disclosure_date(date(2024, 5, 15))
    assert out > date(2024, 5, 15)


def test_fiscal_quarter_label() -> None:
    assert fiscal_quarter_label(date(2024, 3, 31)) == "2024Q1"
    assert fiscal_quarter_label(date(2024, 9, 30)) == "2024Q3"
    assert fiscal_quarter_label(date(2024, 12, 31)) == "2024Q4"


# --------------------------------------------------------------------------- #
# CAS → FUNDAMENTALS_HEADER mapping
# --------------------------------------------------------------------------- #


def _abstract(values: dict[str, dict[str, float]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Build a stock_financial_abstract-shaped (records, columns) for the given
    ``{indicator: {YYYYMMDD: value}}``."""

    periods = sorted({p for vals in values.values() for p in vals})
    columns = ["选项", "指标", *periods]
    records: list[dict[str, Any]] = []
    for indicator, by_period in values.items():
        row: dict[str, Any] = {"选项": "常用指标", "指标": indicator}
        for period in periods:
            row[period] = by_period.get(period)
        records.append(row)
    return records, columns


def _val_bar(day: date, *, close: float, pe: float, pb: float) -> MarketCapBar:
    return MarketCapBar(
        ticker="600519.SH", bar_date=day, total_mv=1.0e12, close=close, pe_ttm=pe, pb=pb
    )


def test_cn_fundamentals_rows_maps_all_ratios() -> None:
    records, columns = _abstract(
        {
            "净资产收益率(ROE)": {"20240930": 24.64},
            "毛利率": {"20240930": 91.29},
            "资产负债率": {"20240930": 12.81},
            "基本每股收益": {"20240930": 51.53},
            "每股企业自由现金流量": {"20240930": 40.0},
        }
    )
    bars = [_val_bar(date(2024, 10, 30), close=1600.0, pe=19.89, pb=6.97)]
    rows, skips = cn_fundamentals_rows(
        "600519.SH", records, columns, bars, from_date=date(2024, 1, 1), to_date=date(2024, 12, 31)
    )
    assert len(rows) == 1
    row = rows[0]
    assert list(row.keys()) == FUNDAMENTALS_HEADER  # exact schema + order
    assert row["report_date"] == "2024-10-31"  # Q3 disclosure deadline
    assert row["fiscal_quarter"] == "2024Q3"
    assert row["fiscal_quarter_end"] == "2024-09-30"
    assert row["roe"] == 0.2464  # percent → fraction
    assert row["gross_margin"] == 0.9129
    assert row["debt_to_assets"] == 0.1281
    assert row["fcf_yield"] == round(40.0 / 1600.0, 4)  # FCF/share ÷ close
    assert row["pe"] == 19.89 and row["pb"] == 6.97  # from nearest valuation bar
    assert row["ev_ebitda"] is None  # honest null
    assert row["earnings_yield"] == round(51.53 / 1600.0, 4)  # EPS ÷ close


def test_fcf_yield_falls_back_to_cfo_when_free_cash_flow_missing() -> None:
    records, columns = _abstract(
        {
            "净资产收益率(ROE)": {"20240930": 10.0},
            "每股经营现金流": {"20240930": 20.0},  # CFO/share present; FCF/share absent
        }
    )
    bars = [_val_bar(date(2024, 10, 30), close=100.0, pe=10.0, pb=2.0)]
    rows, _ = cn_fundamentals_rows(
        "600519.SH", records, columns, bars, from_date=date(2024, 1, 1), to_date=date(2024, 12, 31)
    )
    assert rows[0]["fcf_yield"] == round(20.0 / 100.0, 4)  # CFO/share fallback


def test_cn_fundamentals_rows_filters_to_window_and_skips_empty() -> None:
    records, columns = _abstract(
        {
            "净资产收益率(ROE)": {"20200331": 5.0, "20240930": 24.0},  # 2020 out of window
            "毛利率": {"20240930": 90.0},
        }
    )
    bars = [_val_bar(date(2024, 10, 30), close=100.0, pe=10.0, pb=2.0)]
    rows, _ = cn_fundamentals_rows(
        "600519.SH", records, columns, bars, from_date=date(2023, 1, 1), to_date=date(2024, 12, 31)
    )
    quarters = {r["fiscal_quarter"] for r in rows}
    assert quarters == {"2024Q3"}  # the 2020 period is outside the window


def test_cn_fundamentals_rows_multi_quarter_report_date_series() -> None:
    records, columns = _abstract(
        {
            "净资产收益率(ROE)": {"20240331": 8.0, "20240630": 16.0, "20240930": 24.0},
        }
    )
    bars = [_val_bar(date(2024, m, 1), close=100.0, pe=10.0, pb=2.0) for m in (5, 9, 11)]
    rows, _ = cn_fundamentals_rows(
        "600519.SH", records, columns, bars, from_date=date(2024, 1, 1), to_date=date(2024, 12, 31)
    )
    # A point-in-time report_date series (each disclosure strictly after its end).
    report_dates = [r["report_date"] for r in rows]
    assert report_dates == ["2024-04-30", "2024-08-31", "2024-10-31"]


# --------------------------------------------------------------------------- #
# akshare loader (faked frame, no network)
# --------------------------------------------------------------------------- #


class _FakeAkshare:
    def __init__(self, abstract: pd.DataFrame | None, value: pd.DataFrame | None) -> None:
        self._abstract = abstract
        self._value = value

    def stock_financial_abstract(self, symbol: str) -> pd.DataFrame:
        if self._abstract is None:
            raise RuntimeError("unreachable")
        return self._abstract

    def stock_value_em(self, symbol: str) -> pd.DataFrame:
        if self._value is None:
            raise RuntimeError("unreachable")
        return self._value


def test_loader_parses_live_shape_frames() -> None:
    abstract = pd.DataFrame(
        [
            {"选项": "常用指标", "指标": "净资产收益率(ROE)", "20240930": 24.0},
            {"选项": "常用指标", "指标": "毛利率", "20240930": 90.0},
            {"选项": "常用指标", "指标": "资产负债率", "20240930": 30.0},
            {"选项": "常用指标", "指标": "基本每股收益", "20240930": 5.0},
            {"选项": "常用指标", "指标": "每股企业自由现金流量", "20240930": 4.0},
        ]
    )
    value = pd.DataFrame(
        {
            "数据日期": [date(2024, 10, 30)],
            "当日收盘价": [100.0],
            "总市值": [1.0e12],
            "流通市值": [1.0e12],
            "总股本": [1.0e10],
            "PE(TTM)": [18.0],
            "市净率": [3.0],
        }
    )
    loader = CnFundamentalsLoader(akshare_module=_FakeAkshare(abstract, value))
    rows = loader.fetch_fundamentals_rows("600519.SH", date(2024, 1, 1), date(2024, 12, 31))
    assert len(rows) == 1
    assert rows[0]["roe"] == 0.24 and rows[0]["pe"] == 18.0


def test_loader_absent_akshare_returns_empty() -> None:
    loader = CnFundamentalsLoader(akshare_module=_FakeAkshare(None, None))
    assert loader.fetch_fundamentals_rows("600519.SH", date(2024, 1, 1), date(2024, 12, 31)) == []


# --------------------------------------------------------------------------- #
# ★ core acceptance: the trade quality factor works on a CN-only frame
# --------------------------------------------------------------------------- #


def test_quality_score_ranks_a_share_frame() -> None:
    """The spec §1 insight: CN rows in the same schema → the offline
    ``us_quality_momentum.quality_score`` produces a real (non-NaN) ranking on
    A-shares with no strategy change."""

    from trade.strategies.us_quality_momentum.factors import (  # type: ignore[import-untyped]
        quality_score,
    )

    def cn_rows(
        ticker: str, roe: float, gm: float, fcf_ps: float, debt: float
    ) -> list[dict[str, Any]]:
        records, columns = _abstract(
            {
                "净资产收益率(ROE)": {"20240930": roe},
                "毛利率": {"20240930": gm},
                "资产负债率": {"20240930": debt},
                "基本每股收益": {"20240930": 5.0},
                "每股企业自由现金流量": {"20240930": fcf_ps},
            }
        )
        bars = [
            MarketCapBar(
                ticker=ticker,
                bar_date=date(2024, 10, 30),
                total_mv=1e12,
                close=100.0,
                pe_ttm=15.0,
                pb=3.0,
            )
        ]
        rows, _ = cn_fundamentals_rows(
            ticker, records, columns, bars, from_date=date(2024, 1, 1), to_date=date(2024, 12, 31)
        )
        return rows

    rows = cn_rows("600519.SH", 30.0, 90.0, 40.0, 12.0) + cn_rows("000001.SZ", 8.0, 20.0, 5.0, 80.0)
    frame = pd.DataFrame(rows)
    frame["report_date"] = pd.to_datetime(frame["report_date"])

    scores = quality_score(frame, date(2024, 12, 31))
    assert set(scores.index) == {"600519.SH", "000001.SZ"}
    assert scores.notna().all()  # real scores for the A-shares
    # The high-ROE / high-margin / high-FCF / low-debt name ranks above the other.
    assert scores["600519.SH"] > scores["000001.SZ"]


# --------------------------------------------------------------------------- #
# §12.10.2 / §26.2 boundary — the module never imports trade
# --------------------------------------------------------------------------- #


def test_cn_fundamentals_does_not_import_trade() -> None:
    pkg = Path(__file__).resolve().parents[2] / "workbench_api" / "data_refresh"
    path = pkg / "cn_fundamentals.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not (node.level == 0 and (module == "trade" or module.startswith("trade.")))
        elif isinstance(node, ast.Import):
            assert not any(a.name == "trade" or a.name.startswith("trade.") for a in node.names)
