"""B094 — deterministic unit tests for the 游资 (hot-money) seat first-look.

Covers the three load-bearing, offline-checkable properties:
  1. ★no look-ahead — forward return is measured STRICTLY AFTER the LHB date (entry
     t+1); a same-day / prior bar can never enter the return.
  2. 游资-seat classification — 机构专用 → 机构, 股通 → 股通, named branch → 游资, on a
     synthetic seat sample; and the seat-level 游资 net-buy aggregation.
  3. IC computation — Spearman rank-IC on a known monotone relation + degenerate guard,
     and the monthly-cohort IC / follow-backtest edge on a hand-built cohort.

Pure functions only; no network, no files, no akshare. research-only.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # register so @dataclass can resolve the module
    spec.loader.exec_module(module)
    return module


fetch = _load("b094_youzi_fetch", "scripts/research/b094_youzi_fetch.py")
ic = _load("b094_youzi_ic", "scripts/research/b094_youzi_ic.py")


# --------------------------------------------------------------------------- #
# 1. ★No look-ahead.
# --------------------------------------------------------------------------- #
def _series(start: date, closes: list[float]):
    # consecutive trading days starting at `start`
    from datetime import timedelta
    dates = [start + timedelta(days=i) for i in range(len(closes))]
    return dates, closes


def test_forward_return_enters_strictly_after_event_date():
    # event on index-2 date; entry MUST be index 3 (t+1), not index 2 (t).
    dates, closes = _series(date(2024, 1, 1), [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
    event = dates[2]  # close 12.0 on event day
    rets = ic.forward_returns((dates, closes), event, horizons=(1, 2))
    # entry = closes[3] = 13.0 (first bar strictly after event day)
    assert rets[1] == pytest.approx(14.0 / 13.0 - 1.0)  # entry+1
    assert rets[2] == pytest.approx(15.0 / 13.0 - 1.0)  # entry+2
    # the event-day close (12.0) never appears as an entry -> no lookahead
    assert 12.0 not in (13.0, 14.0, 15.0)


def test_forward_return_none_when_series_runs_out():
    dates, closes = _series(date(2024, 1, 1), [10.0, 11.0])
    # event on last date -> no bar strictly after -> all None
    rets = ic.forward_returns((dates, closes), dates[-1], horizons=(1, 5))
    assert rets[1] is None and rets[5] is None


def test_event_exactly_on_a_bar_uses_next_bar_not_same_bar():
    # Regression guard: bisect_right on an exact date match must skip the matched bar.
    dates, closes = _series(date(2024, 3, 10), [5.0, 6.0, 7.0])
    rets = ic.forward_returns((dates, closes), date(2024, 3, 10), horizons=(1,))
    # entry = index 1 (6.0), exit = index 2 (7.0) -> not the same-day 5.0
    assert rets[1] == pytest.approx(7.0 / 6.0 - 1.0)


# --------------------------------------------------------------------------- #
# 2. 游资-seat classification + net-buy aggregation.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,expected",
    [
        ("机构专用", "机构"),
        ("华鑫证券有限责任公司上海分公司", "游资"),
        ("财通证券股份有限公司杭州九和路证券营业部", "游资"),
        ("深股通专用", "股通"),
        ("沪股通专用", "股通"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_classify_branch(name, expected):
    assert fetch.classify_branch(name) == expected


def test_youzi_jiedu_tag_buy_only():
    assert fetch.is_youzi_jiedu("实力游资买入，成功率51.54%") is True
    assert fetch.is_youzi_jiedu("实力游资卖出，成功率40.0%") is False  # sell != follow
    assert fetch.is_youzi_jiedu("1家机构买入") is False
    assert fetch.is_youzi_jiedu("主力做T") is False


def test_youzi_seat_nets_sums_only_youzi_and_inst_separately():
    seats = [
        {"交易营业部名称": "华鑫证券上海分公司", "净额": 11_000_000.0},   # 游资
        {"交易营业部名称": "财通证券杭州九和路证券营业部", "净额": 9_000_000.0},  # 游资
        {"交易营业部名称": "机构专用", "净额": 5_000_000.0},            # 机构
        {"交易营业部名称": "深股通专用", "净额": 3_000_000.0},          # 股通 (ignored)
    ]
    nets = fetch.youzi_seat_nets(seats)
    assert nets["youzi"] == pytest.approx(20_000_000.0)
    assert nets["inst"] == pytest.approx(5_000_000.0)
    assert nets["youzi_top"] == pytest.approx(11_000_000.0)  # largest single 游资 seat


def test_code_conversions():
    assert fetch.code_to_symbol("600000") == "sh600000"
    assert fetch.code_to_symbol("000001") == "sz000001"
    assert fetch.code_to_ticker("600000") == "600000.SH"
    assert fetch.code_to_ticker("000001") == "000001.SZ"
    assert fetch.code_to_symbol("12") is None


def test_price_guard_drops_corruption():
    assert fetch.guard_price(None, 10.0) == 10.0
    assert fetch.guard_price(10.0, 0.0) is None       # non-positive
    assert fetch.guard_price(10.0, 0.001) is None     # sub-floor
    assert fetch.guard_price(10.0, 100.0) is None     # >5x spike up
    assert fetch.guard_price(100.0, 10.0) is None     # >5x spike down
    assert fetch.guard_price(10.0, 11.0) == 11.0      # normal move kept


# --------------------------------------------------------------------------- #
# 3. IC computation.
# --------------------------------------------------------------------------- #
def test_rank_ic_perfect_monotone():
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    ret = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert ic.rank_ic(sig, ret) == pytest.approx(1.0)
    assert ic.rank_ic(sig, list(reversed(ret))) == pytest.approx(-1.0)


def test_rank_ic_degenerate_returns_none():
    assert ic.rank_ic([1.0, 1.0, 1.0], [0.1, 0.2, 0.3]) is None  # no signal variance
    assert ic.rank_ic([1.0], [0.1]) is None                       # too few pairs


def test_monthly_ic_and_backtest_on_synthetic_cohorts():
    # Two months; within each, youzi_flag==1 names have higher forward returns.
    def row(flag, r):
        return {"youzi_flag": flag, "youzi_net": None, "lhb_net_buy": None,
                "fwd": {1: r, 5: r, 10: r}}

    cohorts = {
        "2024-01": [row(1, 0.05), row(1, 0.04), row(0, -0.01), row(0, -0.02), row(0, 0.00)],
        "2024-02": [row(1, 0.06), row(1, 0.03), row(0, 0.00), row(0, -0.01), row(0, -0.03)],
    }
    ic_flag = ic.monthly_ic(cohorts, "youzi_flag", horizons=(1,))
    cell = ic_flag["N1"]
    assert cell["mean_monthly_ic"] is not None and cell["mean_monthly_ic"] > 0
    assert cell["n_months"] == 2

    bt = ic.follow_backtest(cohorts, horizons=(1,))["N1"]
    # follow (flag==1) beats the all-names baseline in this construction
    assert bt["edge_follow_minus_baseline"] > 0
    assert bt["months_follow_beats_base"] == 2


def test_build_cohorts_coverage_and_no_price_drop():
    events = [
        ic.Event(date(2024, 1, 3), "600000.SH", 1e6, 1, None),
        ic.Event(date(2024, 1, 4), "999999.SZ", 1e6, 0, None),  # no price -> dropped
    ]
    dates, closes = _series(date(2024, 1, 1), [10.0, 11.0, 12.0, 13.0, 14.0])
    prices = {"600000.SH": (dates, closes)}
    built = ic.build_cohorts(events, prices, horizons=(1,))
    assert built["coverage"]["events_covered"] == 1
    assert built["coverage"]["events_no_price"] == 1
    assert "2024-01" in built["cohorts"]


def test_judge_no_go_on_zero_signal():
    ic_flag = {"N1": {"mean_monthly_ic": 0.002, "t_stat": 0.3, "n_months": 12,
                      "n_pairs_pooled": 500, "thin": False}}
    backtest = {"N1": {"n_months": 12, "edge_follow_minus_baseline": -0.001,
                       "edge_t_stat": -0.4, "thin": False}}
    verdict = ic.judge(ic_flag, backtest, {})
    assert verdict["verdict"] == "NO-GO"


def test_judge_no_go_on_significant_negative_signal():
    # The actual B094 shape: significantly NEGATIVE IC + negative follow edge.
    # A follow signal that predicts LOWER returns is a NO-GO, not INCONCLUSIVE.
    ic_flag = {
        "N5": {"mean_monthly_ic": -0.065, "t_stat": -3.7, "n_months": 35,
               "n_pairs_pooled": 3800, "thin": False},
        "N10": {"mean_monthly_ic": -0.067, "t_stat": -3.3, "n_months": 35,
                "n_pairs_pooled": 3800, "thin": False},
    }
    backtest = {"N5": {"n_months": 35, "edge_follow_minus_baseline": -0.019,
                       "edge_t_stat": -3.75, "thin": False}}
    verdict = ic.judge(ic_flag, backtest, {})
    assert verdict["verdict"] == "NO-GO"
    assert verdict["significant_negative_ic_horizons"] == 2
    assert verdict["strong_positive_ic_horizons"] == 0


def test_judge_inconclusive_on_faint_positive():
    ic_flag = {"N1": {"mean_monthly_ic": 0.018, "t_stat": 1.1, "n_months": 20,
                      "n_pairs_pooled": 500, "thin": False}}
    backtest = {"N1": {"n_months": 20, "edge_follow_minus_baseline": 0.004,
                       "edge_t_stat": 0.9, "thin": False}}
    assert ic.judge(ic_flag, backtest, {})["verdict"] == "INCONCLUSIVE"


def test_judge_go_requires_strong_ic_and_significant_edge():
    ic_flag = {
        "N1": {"mean_monthly_ic": 0.05, "t_stat": 3.0, "n_months": 20,
               "n_pairs_pooled": 800, "thin": False},
        "N5": {"mean_monthly_ic": 0.04, "t_stat": 2.5, "n_months": 20,
               "n_pairs_pooled": 800, "thin": False},
    }
    backtest = {"N1": {"n_months": 20, "edge_follow_minus_baseline": 0.02,
                       "edge_t_stat": 2.4, "thin": False}}
    assert ic.judge(ic_flag, backtest, {})["verdict"] == "GO"
