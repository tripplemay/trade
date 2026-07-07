"""B105 unit tests — deterministic, offline (no network, no akshare, no cached CSVs).

Covers the load-bearing guarantees of the inst_buy_net rank-weighted long-short probe:
  1. NO LOOK-AHEAD — entry is the first trading day STRICTLY AFTER the LHB date T (the
     forward-return machinery is imported verbatim from B103/B094; re-asserted here).
  2. RANK WEIGHTS — dollar-neutral (sum w == 0), unit gross (sum|w| == 1), MONOTONE
     increasing in inst_buy_net, and degenerate cross-sections return None.
  3. COST — net return is strictly below gross whenever round_trip_bps > 0, monotone in
     bps, and zero-cost is a no-op.
  4. IC -> RETURN consistency — a cross-section that ranks correctly earns a POSITIVE
     long-short return (the portfolio monetizes the rank-IC).
  5. SUMMARY / VERDICT — cumulative + Sharpe arithmetic and GO/NO-GO gating behave.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

_RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(_RESEARCH))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RESEARCH / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ls = _load("b105_inst_net_longshort")
b094ic = _load("b094_youzi_ic")


# --------------------------------------------------------------------------- #
# 1. NO LOOK-AHEAD (entry strictly after T) — the imported machinery B105 relies on.
# --------------------------------------------------------------------------- #
def _series(days: list[str], closes: list[float]):
    return ([date.fromisoformat(d) for d in days], closes)


def test_entry_is_strictly_after_event_date():
    """Entry is the first bar STRICTLY after T; T's own close is never the entry price."""
    dates = ["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    rets = b094ic.forward_returns(_series(dates, closes),
                                  date.fromisoformat("2023-01-03"), (1,))
    assert rets[1] == pytest.approx(closes[3] / closes[2] - 1.0)  # entry idx2 (2023-01-04)


def test_longshort_series_uses_strict_tplus1_entry():
    """The cohort L/S return is built from entry-T+1 forward returns, never T itself."""
    # Two names, event on 2023-06-01. Entry must be 2023-06-02, exit 2023-06-02+5.
    days = ["2023-06-01", "2023-06-02", "2023-06-03", "2023-06-04",
            "2023-06-05", "2023-06-06", "2023-06-07", "2023-06-08"]
    prices = {
        "AAA": _series(days, [10, 10, 11, 12, 13, 14, 15, 16]),   # rises after entry
        "BBB": _series(days, [10, 10, 10, 10, 10, 10, 10, 10]),   # flat
    }
    events = [
        ls.b103.Event(date.fromisoformat("2023-06-01"), "AAA", None, 1, 1, 5_000_000.0),
        ls.b103.Event(date.fromisoformat("2023-06-01"), "BBB", None, 1, 1, 1_000_000.0),
    ]
    cohorts = ls.b103.build_cohorts(events, prices, (5,))["cohorts"]
    series = ls.longshort_series(cohorts, 5, min_names=2)
    assert len(series) == 1
    # AAA (higher inst_buy_net) is long and rose; BBB (lower) is short and flat -> L/S > 0.
    assert series[0]["gross_ret"] > 0
    # Entry = 2023-06-02 (idx1), exit idx6 for AAA: 15/10-1 = 0.5; weights are +/-0.5.
    assert series[0]["gross_ret"] == pytest.approx(0.5 * 0.5 + (-0.5) * 0.0)


# --------------------------------------------------------------------------- #
# 2. RANK WEIGHTS — dollar-neutral, unit gross, monotone, degenerate -> None.
# --------------------------------------------------------------------------- #
def test_weights_are_dollar_neutral_and_unit_gross():
    for signals in ([1.0, 2.0, 3.0, 4.0], [5.0, -3.0, 0.0, 100.0, 7.0], [10.0, 20.0]):
        w = ls.rank_weights(signals)
        assert w is not None
        assert w.sum() == pytest.approx(0.0, abs=1e-12)          # dollar-neutral
        assert np.abs(w).sum() == pytest.approx(1.0)             # unit gross exposure


def test_weights_are_monotone_increasing_in_signal():
    """Higher inst_buy_net -> larger (more positive) long weight; lowest -> most short."""
    signals = [1.0, 5.0, 2.0, 9.0, 3.0]
    w = ls.rank_weights(signals)
    assert w is not None
    order = np.argsort(signals)                 # ascending signal
    ordered_w = w[order]
    assert np.all(np.diff(ordered_w) > 0)       # strictly increasing along the signal
    assert ordered_w[0] < 0 and ordered_w[-1] > 0   # short the lowest, long the highest


def test_weights_none_on_degenerate_cross_section():
    assert ls.rank_weights([3.0]) is None                 # single name
    assert ls.rank_weights([7.0, 7.0, 7.0]) is None       # all tied -> no bet


def test_weights_handle_ties_with_average_ranks_still_neutral():
    w = ls.rank_weights([1.0, 1.0, 5.0, 5.0])   # two ties
    assert w is not None
    assert w.sum() == pytest.approx(0.0, abs=1e-12)
    assert np.abs(w).sum() == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# 3. COST — net strictly below gross, monotone in bps, zero-cost no-op.
# --------------------------------------------------------------------------- #
def test_cost_reduces_net_below_gross():
    gross = [0.02, -0.01, 0.03, 0.00]
    net = ls.net_returns(gross, 40.0)
    assert all(n < g for n, g in zip(net, gross, strict=True))   # every cohort charged
    assert ls._cumulative(net) < ls._cumulative(gross)      # cumulative strictly lower


def test_cost_is_monotone_in_bps():
    gross = [0.02, 0.01, 0.03]
    cums = [ls._cumulative(ls.net_returns(gross, bp)) for bp in (0, 30, 40, 50, 80)]
    assert cums == sorted(cums, reverse=True)               # higher bps -> lower net


def test_zero_cost_is_identity():
    gross = [0.02, -0.01, 0.03]
    assert ls.net_returns(gross, 0.0) == pytest.approx(gross)


def test_cost_charges_exact_round_trip_on_unit_gross():
    """40bp round-trip on unit-gross book = 0.004 charged per cohort."""
    net = ls.net_returns([0.05], 40.0)
    assert net[0] == pytest.approx(0.05 - 0.004)


# --------------------------------------------------------------------------- #
# 4. IC -> RETURN consistency — correct ranking earns a positive L/S return.
# --------------------------------------------------------------------------- #
def test_positive_ic_cohort_earns_positive_longshort():
    """A cross-section where fwd-ret rises with inst_buy_net (IC=+1) must earn L/S > 0."""
    rows = [{"inst_buy_net": s, "fwd": {5: r}}
            for s, r in zip([1.0, 2.0, 3.0, 4.0, 5.0], [-0.02, -0.01, 0.0, 0.03, 0.05],
                            strict=True)]
    cohorts = {"2023-01": rows}
    series = ls.longshort_series(cohorts, 5, min_names=5)
    assert len(series) == 1
    assert series[0]["cohort_ic"] == pytest.approx(1.0)      # perfect ranking
    assert series[0]["gross_ret"] > 0                        # monetized as positive L/S


def test_negative_ic_cohort_earns_negative_longshort():
    rows = [{"inst_buy_net": s, "fwd": {5: r}}
            for s, r in zip([1.0, 2.0, 3.0, 4.0, 5.0], [0.05, 0.03, 0.0, -0.01, -0.02],
                            strict=True)]
    series = ls.longshort_series({"2023-01": rows}, 5, min_names=5)
    assert series[0]["cohort_ic"] == pytest.approx(-1.0)
    assert series[0]["gross_ret"] < 0


def test_consistency_metric_positive_corr_when_return_tracks_ic():
    series = [
        {"cohort_ic": 0.3, "gross_ret": 0.03},
        {"cohort_ic": -0.2, "gross_ret": -0.02},
        {"cohort_ic": 0.1, "gross_ret": 0.01},
        {"cohort_ic": 0.4, "gross_ret": 0.05},
    ]
    out = ls.ic_return_consistency(series)
    assert out["corr_ic_vs_lsret"] > 0.9
    assert out["same_sign_rate"] == pytest.approx(1.0)


def test_cohort_below_min_names_is_skipped():
    rows = [{"inst_buy_net": 1.0, "fwd": {5: 0.01}},
            {"inst_buy_net": 2.0, "fwd": {5: 0.02}}]     # only 2 names
    assert ls.longshort_series({"2023-01": rows}, 5, min_names=5) == []


# --------------------------------------------------------------------------- #
# 5. SUMMARY / SHARPE / VERDICT arithmetic.
# --------------------------------------------------------------------------- #
def test_annualized_sharpe_uses_sqrt_12():
    rets = [0.01, 0.02, -0.01, 0.03, 0.00, 0.015]
    arr = np.asarray(rets)
    expected = arr.mean() / arr.std(ddof=1) * math.sqrt(12)
    assert ls._annualized_sharpe(rets) == pytest.approx(expected)


def test_cumulative_compounds():
    assert ls._cumulative([0.1, 0.1]) == pytest.approx(0.21)   # 1.1*1.1 - 1


def test_summary_net_is_below_gross_and_reports_sensitivity():
    series = [{"month": f"2023-{m:02d}", "n_names": 10, "gross_ret": 0.02, "cohort_ic": 0.1}
              for m in range(1, 13)]
    summ = ls.summarize_horizon(series)
    assert summ["gross_cum_ret"] > summ["cost_sensitivity"]["40bp"]["net_cum_ret"]
    assert set(summ["cost_sensitivity"]) == {"30bp", "40bp", "50bp", "80bp"}
    assert summ["turnover"]["round_trips_per_year"] == 12


def test_verdict_go_when_net_survives_central_and_50bp():
    def _summ(gross_cum, net40_sharpe, net40_pos, net50_pos):
        return {
            "thin": False, "gross_cum_ret": gross_cum,
            "cost_sensitivity": {
                "40bp": {"net_positive": net40_pos, "net_ann_sharpe": net40_sharpe},
                "50bp": {"net_positive": net50_pos, "net_ann_sharpe": 0.6},
            },
        }
    summaries = {"N5": _summ(0.5, 0.8, True, True), "N10": _summ(0.9, 1.2, True, True)}
    assert ls.judge(summaries)["verdict"] == "GO"


def test_verdict_nogo_when_costs_eat_net_at_central():
    def _summ(gross_cum):
        return {
            "thin": False, "gross_cum_ret": gross_cum,
            "cost_sensitivity": {
                "40bp": {"net_positive": False, "net_ann_sharpe": -0.2},
                "50bp": {"net_positive": False, "net_ann_sharpe": -0.4},
            },
        }
    summaries = {"N5": _summ(0.05), "N10": _summ(0.03)}      # gross positive, net eaten
    assert ls.judge(summaries)["verdict"] == "NO-GO"


def test_verdict_inconclusive_when_net_marginal():
    def _summ(gross_cum):
        return {
            "thin": False, "gross_cum_ret": gross_cum,
            "cost_sensitivity": {
                "40bp": {"net_positive": True, "net_ann_sharpe": 0.2},   # <0.5
                "50bp": {"net_positive": False, "net_ann_sharpe": -0.1},  # flips
            },
        }
    summaries = {"N5": _summ(0.1), "N10": _summ(0.08)}
    assert ls.judge(summaries)["verdict"] == "INCONCLUSIVE"


def test_verdict_no_gross_when_gross_nonpositive():
    def _summ(gross_cum):
        return {
            "thin": False, "gross_cum_ret": gross_cum,
            "cost_sensitivity": {
                "40bp": {"net_positive": False, "net_ann_sharpe": -1.0},
                "50bp": {"net_positive": False, "net_ann_sharpe": -1.0},
            },
        }
    summaries = {"N5": _summ(-0.1), "N10": _summ(-0.05)}
    assert ls.judge(summaries)["verdict"] == "NO-GROSS"
