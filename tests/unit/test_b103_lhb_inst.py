"""Deterministic unit tests for B103 LHB institutional follow-signal first-look.

Covers the three load-bearing pieces:
  1. ★no look-ahead — entry is STRICTLY after the LHB event date T (bisect_right).
  2. jiedu institutional-tag parsing — "N家机构买入/卖出" -> (flag, signed count).
  3. rank-IC computation on a known monotone cross-section.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1].parent / "scripts" / "research"
sys.path.insert(0, str(_SCRIPTS))

import b103_lhb_inst_ic as b103  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. jiedu institutional-tag parsing.
# --------------------------------------------------------------------------- #
def test_parse_inst_buy_single():
    flag, count = b103.parse_inst_jiedu("1家机构买入，成功率54.27%")
    assert flag == 1
    assert count == 1


def test_parse_inst_buy_multi():
    flag, count = b103.parse_inst_jiedu("3家机构买入，成功率43.69%")
    assert flag == 1
    assert count == 3


def test_parse_inst_sell_is_not_a_buy():
    # 卖出 must NOT be a buy: flag 0, count NEGATIVE (signed magnitude).
    flag, count = b103.parse_inst_jiedu("2家机构卖出，成功率38.16%")
    assert flag == 0
    assert count == -2


def test_parse_non_institutional_is_zero():
    for jiedu in ("普通席位买入，成功率33.33%", "卖一主卖，成功率33.90%", "", "游资买入"):
        flag, count = b103.parse_inst_jiedu(jiedu)
        assert flag == 0
        assert count == 0


def test_parse_buy_and_sell_are_disjoint_signs():
    buy_flag, buy_count = b103.parse_inst_jiedu("4家机构买入，成功率50%")
    sell_flag, sell_count = b103.parse_inst_jiedu("4家机构卖出，成功率50%")
    assert buy_flag == 1 and sell_flag == 0
    assert buy_count > 0 > sell_count
    assert abs(buy_count) == abs(sell_count) == 4


# --------------------------------------------------------------------------- #
# 2. ★no look-ahead — entry STRICTLY after the LHB event date T.
# --------------------------------------------------------------------------- #
def _series(days: list[str], closes: list[float]):
    return ([date.fromisoformat(d) for d in days], closes)


def test_entry_is_strictly_after_event_date():
    # Bars on/before T=2022-01-05 must NEVER be the entry. T itself (index 2) excluded.
    dates = ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07",
             "2022-01-10", "2022-01-11"]
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    series = _series(dates, closes)
    rets = b103.b094.forward_returns(series, date(2022, 1, 5), (1,))
    # entry = first bar strictly after 2022-01-05 -> 2022-01-06 (close 13.0).
    # N=1 -> exit 2022-01-07 (close 14.0). ret = 14/13 - 1.
    assert rets[1] is not None
    assert abs(rets[1] - (14.0 / 13.0 - 1.0)) < 1e-12


def test_entry_uses_close_after_event_not_on_event_day():
    # If the event day IS a trading day, its own close must not be used as entry.
    dates = ["2022-03-01", "2022-03-02", "2022-03-03"]
    closes = [100.0, 200.0, 400.0]
    series = _series(dates, closes)
    rets = b103.b094.forward_returns(series, date(2022, 3, 1), (1,))
    # entry = 2022-03-02 (200), exit N=1 = 2022-03-03 (400) -> 1.0. NOT 100->200.
    assert abs(rets[1] - 1.0) < 1e-12


def test_event_after_last_bar_yields_none():
    series = _series(["2022-01-03", "2022-01-04"], [10.0, 11.0])
    rets = b103.b094.forward_returns(series, date(2022, 6, 1), (1, 5, 10))
    assert all(v is None for v in rets.values())


def test_build_cohorts_entry_strictly_after_T():
    # End-to-end: an event whose only forward data is on/before T yields NO coverage.
    events = [b103.Event(date(2022, 1, 5), "X.SZ", 1.0, 1, 1, None)]
    # prices for X.SZ end exactly on T -> no strictly-after bar -> no forward return.
    prices = {"X.SZ": _series(["2022-01-04", "2022-01-05"], [10.0, 11.0])}
    built = b103.build_cohorts(events, prices, (1,))
    assert built["coverage"]["events_covered"] == 0
    assert built["coverage"]["events_no_price"] == 1


# --------------------------------------------------------------------------- #
# 3. rank-IC computation.
# --------------------------------------------------------------------------- #
def test_rank_ic_perfect_monotone():
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    ret = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert abs(b103.rank_ic(sig, ret) - 1.0) < 1e-12


def test_rank_ic_perfect_inverse():
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    ret = [0.5, 0.4, 0.3, 0.2, 0.1]
    assert abs(b103.rank_ic(sig, ret) - (-1.0)) < 1e-12


def test_rank_ic_degenerate_returns_none():
    assert b103.rank_ic([1.0, 1.0, 1.0], [0.1, 0.2, 0.3]) is None


def test_monthly_ic_flag_signal_shape():
    # Two months, inst_buy_flag vs fwd where buys clearly out-earn non-buys.
    def row(flag, r):
        return {"inst_buy_flag": flag, "inst_count": flag, "inst_buy_net": None,
                "lhb_net_buy": None, "fwd": {1: r}}
    cohorts = {
        "2022-01": [row(1, 0.05), row(1, 0.04), row(0, -0.01), row(0, -0.02), row(0, 0.0)],
        "2022-02": [row(1, 0.06), row(1, 0.03), row(0, -0.03), row(0, 0.01), row(0, -0.01)],
    }
    res = b103.monthly_ic(cohorts, "inst_buy_flag", (1,))
    assert res["N1"]["n_months"] == 2
    assert res["N1"]["mean_monthly_ic"] > 0


# --------------------------------------------------------------------------- #
# 4. inst_buy_net cross-check.
# --------------------------------------------------------------------------- #
def test_inst_net_crosscheck_agreement():
    events = [
        b103.Event(date(2022, 1, 3), "A.SZ", 1.0, 1, 1, 5.0),    # flag1 & net>0 -> agree
        b103.Event(date(2022, 1, 4), "B.SZ", 1.0, 0, -2, 0.0),   # flag0 & net<=0 -> agree
        b103.Event(date(2022, 1, 5), "C.SZ", 1.0, 0, 0, 0.0),    # flag0 & net<=0 -> agree
        b103.Event(date(2022, 1, 6), "D.SZ", 1.0, 1, 1, -1.0),   # flag1 & net<=0 -> disagree
        b103.Event(date(2022, 1, 7), "E.SZ", 1.0, 0, 0, None),   # not sampled -> excluded
    ]
    res = b103.inst_net_crosscheck(events)
    assert res["n_sample"] == 4
    assert res["direction_agreement_rate"] == 0.75
    assert res["confusion"]["flag1_net_pos"] == 1
    assert res["confusion"]["flag1_net_nonpos"] == 1


# --------------------------------------------------------------------------- #
# 5. judge — NO-GO on a non-positive edge (the honest 劝退 path).
# --------------------------------------------------------------------------- #
def test_judge_no_go_on_nonpositive_edge():
    ic_flag = {"N1": {"mean_monthly_ic": 0.005, "t_stat": 0.4, "thin": False}}
    backtest = {"N1": {"edge_follow_minus_baseline": -0.002, "edge_t_stat": -0.9,
                       "thin": False}}
    out = b103.judge(ic_flag, backtest)
    assert out["verdict"] == "NO-GO"


def test_judge_go_requires_strong_positive_ic_and_edge():
    ic_flag = {
        "N1": {"mean_monthly_ic": 0.05, "t_stat": 3.0, "thin": False},
        "N5": {"mean_monthly_ic": 0.04, "t_stat": 2.5, "thin": False},
    }
    backtest = {"N1": {"edge_follow_minus_baseline": 0.01, "edge_t_stat": 2.5,
                       "thin": False}}
    out = b103.judge(ic_flag, backtest)
    assert out["verdict"] == "GO"
