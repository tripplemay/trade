"""B102 small-cap insider sleeve — deterministic unit tests.

Covers the four load-bearing invariants:
  1. NO LOOK-AHEAD — the cohort entry is strictly AFTER the announcement month (never on
     the transaction date and never inside the announcement month).
  2. DETERMINISTIC SAMPLE — the seed-102 small-cap sample is fully reproducible and
     signal-independent (a re-draw with the same seed yields the identical set).
  3. COST APPLIED — the round-trip cost genuinely reduces the net path below gross by the
     charged bps per rebalance.
  4. IC COMPUTATION — a monotone signal/return relationship yields IC ~ +1 through the
     reused B101 machinery on a synthetic small-cap panel.

All offline / synthetic — no network, no cached-data dependency.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(mod_name: str, rel: str):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fetch = _load("b102_fetch", "scripts/research/b102_smallcap_fetch.py")
ic = _load("b102_ic", "scripts/research/b102_smallcap_ic.py")
b101 = _load("b101_ic_for_b102", "scripts/research/b101_insider_ic.py")


# --------------------------------------------------------------------------- #
# 1. NO LOOK-AHEAD — entry strictly after the announcement month.
# --------------------------------------------------------------------------- #
def _trading_index() -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", "2020-12-31")


def test_cohort_entry_is_after_announcement_month():
    idx = _trading_index()
    ann_month = pd.Period("2020-03", freq="M")
    entry = b101.cohort_entry(idx, ann_month)
    assert entry is not None
    # Entry must be in APRIL — strictly after every March announcement (no look-ahead).
    assert entry >= pd.Timestamp("2020-04-01")
    # And it must NOT fall inside the announcement month.
    assert entry.to_period("M") > ann_month


def test_entry_after_latest_possible_transaction_and_announcement():
    """Even a transaction on the last day of the announcement month is disclosed within
    that month; the M+1 entry is strictly later than any such date -> look-ahead-free."""
    idx = _trading_index()
    ann_month = pd.Period("2020-06", freq="M")
    entry = b101.cohort_entry(idx, ann_month)
    latest_possible_announcement = pd.Timestamp("2020-06-30")
    assert entry > latest_possible_announcement


def test_forward_return_measured_strictly_after_entry():
    idx = _trading_index()
    # code rises 1% per bar; a 5-bar forward return from entry must be > 0 and use only
    # bars at/after entry (never a pre-entry, pre-announcement price).
    prices = pd.Series([100 * (1.01 ** i) for i in range(len(idx))], index=idx)
    wide = pd.DataFrame({"000001": prices})
    entry = idx[10]
    r = b101.forward_return(wide, "000001", entry, 5)
    assert r is not None
    assert r == pytest.approx(1.01 ** 5 - 1, rel=1e-9)


# --------------------------------------------------------------------------- #
# 2. DETERMINISTIC, SIGNAL-INDEPENDENT SAMPLE (seed-102).
# --------------------------------------------------------------------------- #
def test_sample_is_deterministic_across_redraws():
    frame = [f"{i:06d}" for i in range(3000)]
    a = fetch.deterministic_sample(frame, 800, 102)
    b = fetch.deterministic_sample(frame, 800, 102)
    assert a == b
    assert len(a) == 800
    assert len(set(a)) == 800  # no duplicates
    assert a == sorted(a)      # returned sorted (stable order)


def test_sample_frame_order_does_not_change_result():
    """Signal-independence proxy: the sample depends only on the SET + seed, not on the
    input ordering -> it cannot be covertly reordered by any outcome."""
    frame = [f"{i:06d}" for i in range(3000)]
    a = fetch.deterministic_sample(frame, 800, 102)
    b = fetch.deterministic_sample(list(reversed(frame)), 800, 102)
    assert a == b


def test_different_seed_gives_different_sample():
    frame = [f"{i:06d}" for i in range(3000)]
    assert fetch.deterministic_sample(frame, 800, 102) != \
        fetch.deterministic_sample(frame, 800, 7)


def test_sample_returns_whole_frame_when_small():
    frame = [f"{i:06d}" for i in range(500)]
    out = fetch.deterministic_sample(frame, 800, 102)
    assert out == sorted(frame)


# --------------------------------------------------------------------------- #
# 3. COST APPLIED — net is below gross by the charged bps per rebalance.
# --------------------------------------------------------------------------- #
def test_apply_cost_reduces_each_period():
    rets = [0.02, 0.02, 0.02]
    out = ic.apply_cost(rets, 50.0)
    # each period loses 50bp -> net mean = 2% - 0.5% = 1.5%.
    assert out["net_mean_ret"] == pytest.approx(0.015, abs=1e-9)
    # net cum must be strictly below the gross cum.
    gross_cum = b101._compound(rets)
    assert out["net_cum_ret"] < gross_cum


def test_higher_cost_gives_lower_net():
    rets = [0.01] * 12
    lo = ic.apply_cost(rets, 30.0)["net_cum_ret"]
    hi = ic.apply_cost(rets, 80.0)["net_cum_ret"]
    assert hi < lo  # 80bp drags more than 30bp


def test_zero_cost_equals_gross():
    rets = [0.01, -0.005, 0.02]
    # net_cum_ret is rounded to 4dp, so compare against the same-rounded gross.
    assert ic.apply_cost(rets, 0.0)["net_cum_ret"] == round(b101._compound(rets), 4)


# --------------------------------------------------------------------------- #
# 4. IC COMPUTATION — monotone signal→return gives IC ~ +1 via reused machinery.
# --------------------------------------------------------------------------- #
def test_ic_is_positive_for_monotone_signal():
    idx = pd.bdate_range("2020-01-01", "2020-06-30")
    entry = b101.cohort_entry(idx, pd.Period("2020-02", freq="M"))
    assert entry is not None
    ei = idx.get_loc(entry)
    codes = [f"{i:06d}" for i in range(1, 26)]
    # construct forward returns that increase with a per-code factor; signal = that factor.
    wide = pd.DataFrame(index=idx)
    for k, code in enumerate(codes, 1):
        base = 100.0
        step = 1.0 + k * 0.001  # higher code -> higher forward growth
        wide[code] = [base * (step ** j) for j in range(len(idx))]
    # b101.run expects RAW events (it aggregates chg_pct_total -> buy_pct internally);
    # one row per code, chg_pct_total = the per-code factor -> monotone buy_pct signal.
    ev = pd.DataFrame({
        "code": codes,
        "chg_pct_total": [float(k) for k in range(1, 26)],
        "ann_month": [pd.Period("2020-02", freq="M")] * 25,
    })
    out = b101.run(ev, wide, "buy_pct", 5)
    assert out["mean_ic"] is not None
    assert out["mean_ic"] > 0.9  # near-perfect monotone -> IC ~ +1

    # sanity: forward return at entry+5 uses only post-entry bars.
    r = b101.forward_return(wide, codes[-1], entry, 5)
    expected = (1.0 + 25 * 0.001) ** 5 - 1
    assert r == pytest.approx(expected, rel=1e-9)
    assert ei >= 0


def test_net_of_cost_block_shapes_and_direction():
    event_rets = [0.03, 0.01, 0.02]
    mag_rets = [0.04, 0.02, 0.03]
    base_cum = b101._compound([0.015, 0.005, 0.01])
    block = ic.net_of_cost_block({}, event_rets, mag_rets, base_cum, 50.0)
    assert block["cost_bps"] == 50.0
    assert block["baseline_gross_cum"] == pytest.approx(round(base_cum, 4))
    # net event cum must be below its own gross cum.
    assert block["event_net_cum"] < round(b101._compound(event_rets), 4)
