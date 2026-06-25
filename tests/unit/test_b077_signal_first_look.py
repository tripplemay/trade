"""B077 F002 — unit tests for the first-look IC / grouped-spread compute.

Lock the PURE join + IC + grouping logic offline with synthetic data (the real run
is a CSV crunch over B070 prices). Covers the no-lookahead entry, delisted-name
truncation, Spearman rank-IC sign/degeneracy, quantile spread, coverage bookkeeping,
and the soufflé verdict thresholds.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from scripts.research.b077_signal_first_look import (
    LhbEvent,
    _average_ranks,
    analyse,
    build_pairs,
    forward_returns,
    grouped_spread,
    judge,
    load_events,
    rank_ic,
)


def _series(closes: list[float], start: date = date(2024, 1, 1)) -> tuple[list[date], list[float]]:
    dates = [date.fromordinal(start.toordinal() + i) for i in range(len(closes))]
    return dates, closes


# --------------------------------------------------------------------------- #
# forward_returns — entry is t+1 (no lookahead), truncates when series runs out.
# --------------------------------------------------------------------------- #
def test_forward_returns_enters_next_trading_day() -> None:
    series = _series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])  # d0..d5
    # event on d0 -> entry d1 (close 11); N=1 -> d2/d1, N=2 -> d3/d1
    out = forward_returns(series, date(2024, 1, 1), horizons=(1, 2, 3))
    assert out[1] == pytest.approx(12.0 / 11.0 - 1.0)
    assert out[2] == pytest.approx(13.0 / 11.0 - 1.0)
    assert out[3] == pytest.approx(14.0 / 11.0 - 1.0)


def test_forward_returns_no_lookahead_on_event_day() -> None:
    series = _series([10.0, 11.0, 12.0, 13.0])  # d0..d3
    # event ON a trading day d1 -> entry is STRICTLY after (d2), not d1
    out = forward_returns(series, date(2024, 1, 2), horizons=(1,))
    assert out[1] == pytest.approx(13.0 / 12.0 - 1.0)  # d3/d2, not using d1


def test_forward_returns_none_when_series_too_short() -> None:
    series = _series([10.0, 11.0])  # only d0, d1
    out = forward_returns(series, date(2024, 1, 1), horizons=(1, 5))
    assert out[1] is None  # entry d1, +1 -> d2 absent
    assert out[5] is None  # delisted within horizon -> None (cannot hold)


# --------------------------------------------------------------------------- #
# rank_ic — Spearman sign + degeneracy.
# --------------------------------------------------------------------------- #
def test_rank_ic_perfect_monotone() -> None:
    sig = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert rank_ic(sig, [10.0, 20.0, 30.0, 40.0, 50.0]) == pytest.approx(1.0)
    assert rank_ic(sig, [50.0, 40.0, 30.0, 20.0, 10.0]) == pytest.approx(-1.0)


def test_rank_ic_degenerate_returns_none() -> None:
    assert rank_ic([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # no signal variance
    assert rank_ic([1.0], [2.0]) is None  # < 2 pairs
    assert rank_ic([1.0, 2.0], [3.0]) is None  # mismatched lengths


def test_average_ranks_handles_ties() -> None:
    ranks = _average_ranks(np.array([10.0, 10.0, 20.0]))
    assert list(ranks) == [1.5, 1.5, 3.0]  # tied first two -> (1+2)/2


# --------------------------------------------------------------------------- #
# grouped_spread — monotone signal -> positive top-minus-bottom.
# --------------------------------------------------------------------------- #
def test_grouped_spread_monotone_positive() -> None:
    sig = [float(i) for i in range(10)]
    ret = [float(i) for i in range(10)]  # higher signal -> higher return
    out = grouped_spread(sig, ret, n_groups=5)
    assert out["top_minus_bottom"] is not None and out["top_minus_bottom"] > 0
    assert out["group_mean_returns"] == sorted(out["group_mean_returns"])  # monotone up


def test_grouped_spread_thin_sample() -> None:
    assert grouped_spread([1.0, 2.0], [1.0, 2.0], n_groups=5)["top_minus_bottom"] is None


# --------------------------------------------------------------------------- #
# load_events — parse + skip malformed.
# --------------------------------------------------------------------------- #
def test_load_events_skips_malformed(tmp_path) -> None:
    path = tmp_path / "ev.csv"
    path.write_text(
        "event_date,ticker,inst_net_buy,inst_buyers,inst_sellers,inst_net_buy_pct\n"
        "2019-01-03,000750.SZ,151843768.38,2,0,4.43\n"
        "bad-date,000001.SZ,1.0,1,0,1.0\n"  # bad date -> skip
        ",000002.SZ,1.0,1,0,1.0\n"  # blank date -> skip
        "2019-02-01,,1.0,1,0,1.0\n"  # blank ticker -> skip
        "2019-02-02,000003.SZ,,1,0,\n",  # blank net-buy -> skip
        encoding="utf-8",
    )
    events = load_events(path)
    assert len(events) == 1
    assert events[0].ticker == "000750.SZ"
    assert events[0].inst_net_buy == pytest.approx(151843768.38)


# --------------------------------------------------------------------------- #
# build_pairs — coverage bookkeeping + universe filter.
# --------------------------------------------------------------------------- #
def test_build_pairs_coverage_and_universe_filter() -> None:
    events = [
        LhbEvent(date(2024, 1, 1), "AAA.SZ", 100.0, 2.0),  # priced + in universe
        LhbEvent(date(2024, 1, 1), "BBB.SZ", -50.0, -1.0),  # priced, NOT in universe
        LhbEvent(date(2024, 1, 1), "CCC.SZ", 10.0, 0.5),  # in universe but NO price
    ]
    prices = {
        "AAA.SZ": _series([10.0, 11.0, 12.0, 13.0]),
        "BBB.SZ": _series([20.0, 21.0, 22.0, 23.0]),
    }
    pairs = build_pairs(events, prices, universe={"AAA.SZ", "CCC.SZ"}, horizons=(1,))
    cov = pairs["coverage"]
    assert cov["events_total"] == 3
    assert cov["events_out_of_universe"] == 1  # BBB filtered by universe
    assert cov["events_no_price"] == 1  # CCC has no price
    assert cov["events_covered"] == 1  # only AAA
    assert pairs["net_buy"][1] == [100.0]


# --------------------------------------------------------------------------- #
# judge — soufflé thresholds.
# --------------------------------------------------------------------------- #
def test_judge_no_souffle_on_weak_ic() -> None:
    # ICs below the faint bar (0.015) AND full coverage -> clean 劝退.
    analysis = {
        "inst_net_buy": {
            "N1": {"rank_ic": 0.005, "grouped": {"top_minus_bottom": 0.001}},
            "N5": {"rank_ic": -0.01, "grouped": {"top_minus_bottom": 0.0}},
        }
    }
    v = judge(analysis, {"coverage_rate": 0.8})
    assert v["verdict"] == "NO_SOUFFLE"
    assert v["strong_cells"] == 0


def test_judge_souffle_when_two_strong_cells() -> None:
    analysis = {
        "inst_net_buy": {
            "N1": {"rank_ic": 0.05, "grouped": {"top_minus_bottom": 0.02}},  # same sign +
            "N5": {"rank_ic": 0.04, "grouped": {"top_minus_bottom": 0.03}},  # same sign +
        },
        "inst_net_buy_pct": {
            "N1": {
                "rank_ic": 0.05,
                "grouped": {"top_minus_bottom": -0.02},
            },  # sign mismatch -> not counted
        },
    }
    v = judge(analysis, {"coverage_rate": 0.3})
    assert v["verdict"] == "SOUFFLE_WORTH_BACKTEST"
    assert v["strong_cells"] == 2
    assert v["max_abs_ic"] == pytest.approx(0.05)


def test_judge_inconclusive_when_faint_consistent_and_coverage_partial() -> None:
    """The real F002 shape: faint consistent positive direction (sub-0.03) on a
    partial-coverage subset -> neither soufflé nor clean 劝退."""
    analysis = {
        "inst_net_buy": {
            "N1": {"rank_ic": 0.020, "grouped": {"top_minus_bottom": 0.0019}},
            "N5": {"rank_ic": 0.023, "grouped": {"top_minus_bottom": 0.0048}},
            "N10": {"rank_ic": 0.018, "grouped": {"top_minus_bottom": 0.0048}},
            "N20": {"rank_ic": 0.018, "grouped": {"top_minus_bottom": 0.0167}},
        }
    }
    v = judge(analysis, {"coverage_rate": 0.192})
    assert v["verdict"] == "INCONCLUSIVE_COVERAGE_LIMITED"
    assert v["faint_consistent_horizons"] == 4
    assert v["strong_cells"] == 0


def test_judge_faint_but_full_coverage_is_no_souffle() -> None:
    # faint consistent direction BUT full coverage -> no coverage excuse -> 劝退.
    analysis = {
        "inst_net_buy": {
            "N1": {"rank_ic": 0.020, "grouped": {"top_minus_bottom": 0.0019}},
            "N5": {"rank_ic": 0.023, "grouped": {"top_minus_bottom": 0.0048}},
            "N10": {"rank_ic": 0.018, "grouped": {"top_minus_bottom": 0.0048}},
        }
    }
    v = judge(analysis, {"coverage_rate": 0.85})
    assert v["verdict"] == "NO_SOUFFLE"


def test_analyse_thin_sample_guard() -> None:
    # below _MIN_PAIRS -> rank_ic None, grouped None, thin True
    pairs = {
        "net_buy": {1: [1.0, 2.0, 3.0]},
        "net_buy_fwd": {1: [1.0, 2.0, 3.0]},
        "pct": {1: []},
        "pct_fwd": {1: []},
    }
    out = analyse(pairs, horizons=(1,))
    assert out["inst_net_buy"]["N1"]["thin"] is True
    assert out["inst_net_buy"]["N1"]["rank_ic"] is None
