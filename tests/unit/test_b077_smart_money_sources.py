"""B077 F001 — unit tests for the smart-money data-availability probe.

The live probe is an akshare network job; these tests lock the PURE parse + judge
logic offline (no network) with a fake-akshare module whose canned frames encode
the **real §23 reality measured 2026-06-25**: northbound per-stock holdings frozen
at 2024-08-16 with the aggregate net-buy gone NaN (the 2024.8 disclosure cut),
dragon-tiger institutional seats live-but-sparse, and main fund flow broad. The
fixtures double as executable documentation of that measured reality, so the
freeze-detection + verdict logic is a permanent regression.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from scripts.research.b077_smart_money_feasibility_probe import (
    DragonTigerInstitutionalProbe,
    MainFundFlowProbe,
    NorthboundHoldingProbe,
    canonical_to_code_market,
    coerce_date,
    coerce_float,
    extract_dated_series,
    frame_records,
    judge_source,
    latest_non_null_date,
    resolve_column,
    run_probe,
    series_span,
)

TODAY = date(2026, 6, 25)


# --------------------------------------------------------------------------- #
# Fake pandas-like frame + akshare module (only .columns + .to_dict needed).
# --------------------------------------------------------------------------- #
class _FakeFrame:
    def __init__(self, columns: list[str], records: list[dict[str, Any]]) -> None:
        self.columns = columns
        self._records = records

    def to_dict(self, _orient: str) -> list[dict[str, Any]]:
        return list(self._records)


NAN = float("nan")


def _northbound_individual_frame() -> _FakeFrame:
    cols = [
        "持股日期",
        "当日收盘价",
        "持股数量",
        "持股数量占A股百分比",
        "今日增持股数",
        "今日增持资金",
    ]
    rows = [
        {
            "持股日期": "2017-03-16",
            "当日收盘价": 374.77,
            "持股数量": 73748969,
            "持股数量占A股百分比": 5.87,
            "今日增持股数": NAN,
            "今日增持资金": NAN,
        },
        {
            "持股日期": "2020-06-30",
            "当日收盘价": 1420.0,
            "持股数量": 80000000,
            "持股数量占A股百分比": 6.4,
            "今日增持股数": 12000,
            "今日增持资金": 17040000.0,
        },
        {
            "持股日期": "2024-08-16",
            "当日收盘价": 1431.2,
            "持股数量": 82354427,
            "持股数量占A股百分比": 6.55,
            "今日增持股数": 39399.0,
            "今日增持资金": 56264037.44,
        },
    ]
    return _FakeFrame(cols, rows)


def _northbound_aggregate_frame() -> _FakeFrame:
    cols = ["日期", "当日成交净买额", "买入成交额", "持股市值"]
    rows = [
        {"日期": "2014-11-17", "当日成交净买额": 120.82, "买入成交额": 120.82, "持股市值": 0.0},
        {"日期": "2024-08-16", "当日成交净买额": -33.5, "买入成交额": 500.0, "持股市值": 2.3e12},
        # post-cut: row index keeps advancing to today, but net-buy is NaN
        {"日期": "2025-01-02", "当日成交净买额": NAN, "买入成交额": NAN, "持股市值": 2.4e12},
        {"日期": "2026-06-24", "当日成交净买额": NAN, "买入成交额": NAN, "持股市值": 2.5e12},
    ]
    return _FakeFrame(cols, rows)


def _iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _lhb_inst_frame(end_yyyymmdd: str = "20240430") -> _FakeFrame:
    # 上榜日期 stamped to the window end so the probe measures REAL recency/depth
    # by aggregating dates across windows (not a hardcoded today/0).
    on_date = _iso(end_yyyymmdd)
    cols = [
        "序号",
        "代码",
        "名称",
        "买方机构数",
        "卖方机构数",
        "机构买入净额",
        "上榜原因",
        "上榜日期",
    ]
    rows = [
        {
            "序号": 1,
            "代码": "600919",
            "名称": "江苏银行",
            "买方机构数": 3,
            "卖方机构数": 0,
            "机构买入净额": 541072808.45,
            "上榜原因": "x",
            "上榜日期": on_date,
        },
        {
            "序号": 2,
            "代码": "688032",
            "名称": "禾迈股份",
            "买方机构数": 3,
            "卖方机构数": 1,
            "机构买入净额": 221200700.0,
            "上榜原因": "y",
            "上榜日期": on_date,
        },
    ]
    return _FakeFrame(cols, rows)


def _lhb_detail_frame(end_yyyymmdd: str = "20240430") -> _FakeFrame:
    # Broad LHB carries built-in forward-return columns (上榜后N日) — an F002 convenience.
    on_date = _iso(end_yyyymmdd)
    cols = ["代码", "名称", "上榜日", "解读", "龙虎榜净买额", "上榜原因", "上榜后1日", "上榜后5日"]
    rows = [
        {
            "代码": "000002",
            "名称": "万科A",
            "上榜日": on_date,
            "解读": "1家机构买入",
            "龙虎榜净买额": 3.07e8,
            "上榜原因": "z",
            "上榜后1日": -1.98,
            "上榜后5日": -3.44,
        },
    ]
    return _FakeFrame(cols, rows)


def _fund_flow_individual_frame() -> _FakeFrame:
    # ~0.5y span (120 td) — mirrors the real VM measurement (eastmoney fflow daykline
    # returns only ~recent 120 days): live but too shallow for a deep backtest.
    cols = [
        "日期",
        "收盘价",
        "涨跌幅",
        "主力净流入-净额",
        "超大单净流入-净额",
        "超大单净流入-净占比",
    ]
    rows = [
        {
            "日期": "2025-12-22",
            "收盘价": 1400.0,
            "涨跌幅": 0.5,
            "主力净流入-净额": -1.0e8,
            "超大单净流入-净额": 5.0e7,
            "超大单净流入-净占比": 1.2,
        },
        {
            "日期": "2026-06-24",
            "收盘价": 1500.0,
            "涨跌幅": -0.3,
            "主力净流入-净额": 2.0e8,
            "超大单净流入-净额": 9.0e7,
            "超大单净流入-净占比": 2.1,
        },
    ]
    return _FakeFrame(cols, rows)


def _fund_flow_rank_frame() -> _FakeFrame:
    cols = ["序号", "代码", "名称", "今日主力净流入-净额", "今日超大单净流入-净额"]
    rows = [
        {
            "序号": i,
            "代码": f"{i:06d}",
            "名称": "x",
            "今日主力净流入-净额": 1.0,
            "今日超大单净流入-净额": 1.0,
        }
        for i in range(1, 51)
    ]
    return _FakeFrame(cols, rows)


class _FakeAkshare:
    """Encodes the measured §23 reality. ``raise_fund_flow`` mimics the push-host
    SSL/JSON failure; ``empty_lhb`` mimics an unreachable dragon-tiger feed."""

    def __init__(self, *, raise_fund_flow: bool = False, empty_lhb: bool = False) -> None:
        self._raise_fund_flow = raise_fund_flow
        self._empty_lhb = empty_lhb

    def stock_hsgt_individual_em(self, symbol: str) -> _FakeFrame:
        # akshare wants the BARE 6-digit code; a canonical "600519.SH" returns an
        # empty frame upstream. Asserting here locks the canonical->code fix so the
        # probe never silently regresses to "northbound UNREACHABLE".
        assert "." not in symbol, f"expected bare code, got canonical {symbol!r}"
        return _northbound_individual_frame()

    def stock_hsgt_hist_em(self, symbol: str) -> _FakeFrame:
        return _northbound_aggregate_frame()

    def stock_lhb_jgmmtj_em(self, start_date: str, end_date: str) -> _FakeFrame:
        if self._empty_lhb:
            return _FakeFrame(["序号", "代码", "上榜日期"], [])
        return _lhb_inst_frame(end_date)

    def stock_lhb_detail_em(self, start_date: str, end_date: str) -> _FakeFrame:
        if self._empty_lhb:
            return _FakeFrame(["代码", "上榜日"], [])
        return _lhb_detail_frame(end_date)

    def stock_individual_fund_flow(self, stock: str, market: str) -> _FakeFrame:
        if self._raise_fund_flow:
            raise OSError("HTTPSConnectionPool push2his.eastmoney.com SSL record layer failure")
        return _fund_flow_individual_frame()

    def stock_individual_fund_flow_rank(self, indicator: str) -> _FakeFrame:
        if self._raise_fund_flow:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return _fund_flow_rank_frame()


# --------------------------------------------------------------------------- #
# coerce / resolve / canonical helpers.
# --------------------------------------------------------------------------- #
def test_coerce_float_is_nan_safe() -> None:
    assert coerce_float(float("nan")) is None  # the post-2024.8 net-buy cells
    assert coerce_float("") is None
    assert coerce_float(None) is None
    assert coerce_float("abc") is None
    assert coerce_float("3.5") == pytest.approx(3.5)
    assert coerce_float(7) == pytest.approx(7.0)


def test_coerce_date_formats() -> None:
    assert coerce_date("2024-08-16") == date(2024, 8, 16)
    assert coerce_date("20240816") == date(2024, 8, 16)
    assert coerce_date(date(2024, 8, 16)) == date(2024, 8, 16)
    assert coerce_date("not-a-date") is None
    assert coerce_date(None) is None


def test_resolve_column_exact_then_substring_then_none() -> None:
    cols = ["代码", "机构买入净额", "超大单净流入-净额"]
    assert resolve_column(cols, ["机构买入净额"]) == "机构买入净额"  # exact
    assert resolve_column(cols, ["超大单净流入"]) == "超大单净流入-净额"  # substring
    assert resolve_column(cols, ["不存在的列"]) is None


def test_canonical_to_code_market() -> None:
    assert canonical_to_code_market("600519.SH") == ("600519", "sh")
    assert canonical_to_code_market("000858.SZ") == ("000858", "sz")
    assert canonical_to_code_market("920931.BJ") == ("920931", "bj")
    assert canonical_to_code_market("600036") == ("600036", "sh")  # infer from leading digit
    assert canonical_to_code_market("000001") == ("000001", "sz")


# --------------------------------------------------------------------------- #
# frame_records best-effort + pure series parsing.
# --------------------------------------------------------------------------- #
def test_frame_records_best_effort_degrades() -> None:
    ak = _FakeAkshare()
    records, columns = frame_records(ak, "stock_hsgt_individual_em", symbol="600519")
    assert len(records) == 3 and "今日增持资金" in columns

    class _Boom:
        def boom(self, **_kw: Any) -> Any:
            raise RuntimeError("network")

        @property
        def none_fn(self) -> Any:
            return lambda **_kw: None

    assert frame_records(_Boom(), "missing_fn") == ([], [])  # absent function
    assert frame_records(_Boom(), "boom") == ([], [])  # raising function
    assert frame_records(_Boom(), "none_fn") == ([], [])  # returns None


def test_extract_dated_series_skips_nan_and_sorts() -> None:
    frame = _northbound_individual_frame()
    series = extract_dated_series(frame._records, frame.columns, ["今日增持资金"])
    # row 1 has NaN 今日增持资金 -> dropped; rows 2 & 3 kept, sorted ascending
    assert [d.isoformat() for d, _ in series] == ["2020-06-30", "2024-08-16"]
    assert series[-1][1] == pytest.approx(56264037.44)


def test_extract_dated_series_missing_column_returns_empty() -> None:
    frame = _northbound_individual_frame()
    assert extract_dated_series(frame._records, frame.columns, ["不存在"]) == []


def test_series_span_years_and_empty() -> None:
    span = series_span([(date(2017, 3, 16), 1.0), (date(2024, 8, 16), 2.0)])
    assert (
        span["n_obs"] == 2 and span["earliest"] == "2017-03-16" and span["latest"] == "2024-08-16"
    )
    assert span["years"] == pytest.approx(7.42, abs=0.1)
    assert series_span([]) == {"earliest": None, "latest": None, "n_obs": 0, "years": 0.0}


def test_latest_non_null_date_is_the_disclosure_cutoff() -> None:
    """The §23 detector: aggregate rows run to 2026 but net-buy NaN after 2024-08-16."""
    frame = _northbound_aggregate_frame()
    cutoff = latest_non_null_date(frame._records, frame.columns, ["当日成交净买额"])
    assert cutoff == date(2024, 8, 16)  # NOT 2026-06-24 (the row-index max)


# --------------------------------------------------------------------------- #
# Probe classes — offline path with injected fake akshare.
# --------------------------------------------------------------------------- #
def test_northbound_probe_detects_freeze() -> None:
    probe = NorthboundHoldingProbe(_FakeAkshare())
    out = probe.probe(["600519.SH", "000858.SZ"], TODAY)
    summary = out["summary"]
    assert summary["reachable"] is True
    assert summary["signal_column_found"] is True
    assert summary["latest_date"] == "2024-08-16"  # per-stock frozen
    assert summary["lag_days"] > 600  # ~678 days stale on a 2026 run
    assert summary["coverage"] == "per_stock_connect"
    assert out["aggregate"]["net_buy_last_disclosed"] == "2024-08-16"


def test_dragon_tiger_probe_measures_real_dates_and_depth() -> None:
    probe = DragonTigerInstitutionalProbe(_FakeAkshare())
    out = probe.probe([("20240401", "20240430"), ("20260501", "20260531")], TODAY)
    summary = out["summary"]
    assert summary["reachable"] is True
    assert summary["signal_column_found"] is True
    assert summary["coverage"] == "sparse_event"
    # latest/earliest are derived from the REAL 上榜日期 (window ends), not today/0.
    assert summary["earliest_date"] == "2024-04-30"
    assert summary["latest_date"] == "2026-05-31"
    assert summary["lag_days"] == 25  # TODAY 2026-06-25 minus 2026-05-31, measured
    # broad-LHB (stock_lhb_detail_em) reachability + forward-return columns measured
    assert summary["broad_lhb_reachable"] is True
    assert summary["broad_lhb_has_fwd_returns"] is True


def test_dragon_tiger_probe_unreachable_branch() -> None:
    probe = DragonTigerInstitutionalProbe(_FakeAkshare(empty_lhb=True))
    out = probe.probe([("20200727", "20200825"), ("20260520", "20260618")], TODAY)
    summary = out["summary"]
    assert summary["reachable"] is False
    assert summary["latest_date"] is None
    assert summary["earliest_date"] is None
    assert summary["lag_days"] is None  # not a stamped 0


def test_fund_flow_probe_full_coverage_when_reachable() -> None:
    probe = MainFundFlowProbe(_FakeAkshare())
    out = probe.probe(["600519.SH", "000858.SZ"], TODAY)
    summary = out["summary"]
    assert summary["reachable"] is True
    assert summary["signal_column_found"] is True
    assert summary["coverage"] == "full_market"
    assert summary["cross_section_breadth"] == 50
    assert summary["cross_section_snapshot_ok"] is True


def test_fund_flow_probe_degrades_on_push_host_failure() -> None:
    probe = MainFundFlowProbe(_FakeAkshare(raise_fund_flow=True))
    out = probe.probe(["600519.SH"], TODAY)
    # frame_records swallows the SSL error -> empty, reachable False (off-VM reality)
    assert out["summary"]["reachable"] is False
    assert out["summary"]["empty"] == 1


class _StubNoFns:
    """An object with none of the akshare functions -> frame_records returns []."""


def test_probe_with_unusable_akshare_is_empty_not_crash() -> None:
    # akshare present but carrying none of the smart-money functions (or all
    # unreachable) must degrade to reachable=False, never raise.
    out = NorthboundHoldingProbe(_StubNoFns()).probe(["600519.SH"], TODAY)
    assert out["summary"]["reachable"] is False
    assert out["aggregate"].get("ok") is False


# --------------------------------------------------------------------------- #
# judge_source verdicts (the §23 backtest-supportability call).
# --------------------------------------------------------------------------- #
def test_judge_frozen_source_is_backtest_only() -> None:
    summary = {
        "reachable": True,
        "signal_column_found": True,
        "coverage": "per_stock_connect",
        "earliest_date": "2017-03-16",
        "latest_date": "2024-08-16",
        "lag_days": 678,
    }
    v = judge_source(summary, TODAY)
    assert v["verdict"] == "BACKTEST_ONLY_FROZEN"
    assert v["can_support_backtest"] is True
    assert v["live_tradeable"] is False


def test_judge_sparse_live_source_with_deep_history() -> None:
    summary = {
        "reachable": True,
        "signal_column_found": True,
        "coverage": "sparse_event",
        "earliest_date": "2020-07-30",  # ~6y measured depth (dragon-tiger reality)
        "latest_date": "2026-06-18",
        "lag_days": 7,
    }
    v = judge_source(summary, TODAY)
    assert v["verdict"] == "USABLE_SPARSE"
    assert v["can_support_backtest"] is True and v["live_tradeable"] is True
    assert v["history_years"] is not None and v["history_years"] >= 5.0


def test_judge_full_live_source() -> None:
    summary = {
        "reachable": True,
        "signal_column_found": True,
        "coverage": "full_market",
        "earliest_date": "2022-01-01",
        "latest_date": TODAY.isoformat(),
        "lag_days": 1,
    }
    v = judge_source(summary, TODAY)
    assert v["verdict"] == "USABLE_FULL"
    assert v["live_tradeable"] is True
    assert v["can_support_backtest"] is True  # ~4.5y deep enough


def test_judge_shallow_full_source_is_live_but_not_backtestable() -> None:
    """The F002-candidate fund flow: live + broad, but ~0.5y < 2.0y → the depth
    gate must say can_support_backtest=False (in the FLAG, not only prose). The
    failed bulk-snapshot probe must qualify the 'broad coverage' claim."""
    summary = {
        "reachable": True,
        "signal_column_found": True,
        "coverage": "full_market",
        "earliest_date": "2025-12-22",
        "latest_date": "2026-06-24",
        "lag_days": 1,
        "cross_section_snapshot_ok": False,
    }
    v = judge_source(summary, TODAY)
    assert v["verdict"] == "USABLE_FULL"
    assert v["live_tradeable"] is True
    assert v["can_support_backtest"] is False  # ~0.5y too shallow — gated flag
    assert v["history_years"] == pytest.approx(0.5, abs=0.05)
    assert "shallow history" in v["reason"]
    assert "bulk cross-section" in v["reason"]  # breadth-unmeasured qualifier


def test_judge_unreachable_and_no_signal() -> None:
    unreachable = judge_source({"reachable": False}, TODAY)
    assert unreachable["verdict"] == "UNREACHABLE"
    assert unreachable["can_support_backtest"] is False

    no_signal = judge_source({"reachable": True, "signal_column_found": False}, TODAY)
    assert no_signal["verdict"] == "NO_SIGNAL_COLUMN"
    assert no_signal["can_support_backtest"] is False


def test_judge_unreachable_surfaces_2024_8_disclosure_cut() -> None:
    """Northbound on the VM: per-stock empty BUT aggregate net-buy still readable,
    frozen at 2024-08-16 — the headline §23 reality must land in the verdict reason."""
    v = judge_source({"reachable": False, "agg_net_buy_last_disclosed": "2024-08-16"}, TODAY)
    assert v["verdict"] == "UNREACHABLE"
    assert v["can_support_backtest"] is False
    assert "2024-08-16" in v["reason"]
    assert "2024.8" in v["reason"]


# --------------------------------------------------------------------------- #
# End-to-end run_probe — the honest §23 picture falls out of measurement.
# --------------------------------------------------------------------------- #
def test_run_probe_yields_the_honest_three_source_picture() -> None:
    result = run_probe(
        sample=["600519.SH", "000858.SZ"], today=TODAY, akshare_module=_FakeAkshare()
    )
    verdicts = result["verdicts"]
    # 北向: frozen 2024.8 → backtestable history exists, but not live-tradeable.
    nb = verdicts["northbound_hold"]
    assert nb["verdict"] == "BACKTEST_ONLY_FROZEN" and nb["live_tradeable"] is False
    # 龙虎榜机构席位: live + sparse + ~6y measured depth → backtest-supportable.
    dt = verdicts["dragon_tiger_inst"]
    assert dt["verdict"] == "USABLE_SPARSE" and dt["can_support_backtest"] is True
    # 主力资金流: live + broad BUT ~0.5y shallow → live yet NOT backtest-supportable.
    ff = verdicts["main_fund_flow"]
    assert ff["verdict"] == "USABLE_FULL" and ff["live_tradeable"] is True
    assert ff["can_support_backtest"] is False


def test_run_probe_fund_flow_unreachable_off_vm() -> None:
    result = run_probe(
        sample=["600519.SH"], today=TODAY, akshare_module=_FakeAkshare(raise_fund_flow=True)
    )
    assert result["verdicts"]["main_fund_flow"]["verdict"] == "UNREACHABLE"
