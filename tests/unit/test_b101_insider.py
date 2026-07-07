"""B101 — deterministic unit tests for the insider-buying first-look.

Focus (the CARDINAL risk): NO LOOK-AHEAD. The follow/entry must use the ANNOUNCEMENT
date (公告日), never the transaction date (变动日期). We prove:
  * normalize_events keeps only buys whose announce_date >= txn_end_date (lag>=0);
  * cohort entry is strictly AFTER the whole announcement month (first td of next month);
  * forward_return reads prices STRICTLY after entry and honours the sanity guard;
  * the monthly signal aggregates buy-% + event count correctly;
  * the rank-IC sign is recovered on a constructed monotone case.
No network, no files — all fixtures are in-memory.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(mod_name: str, rel: str):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


fetch = _load("b101_fetch", "scripts/research/b101_insider_fetch.py")
ic = _load("b101_ic", "scripts/research/b101_insider_ic.py")


# ---- fixtures ----------------------------------------------------------------
def _raw_events():
    """Raw akshare-shaped frame: buys, a sell (dropped), a look-ahead-violating row
    (announce before txn, dropped), and a non-positive-qty row (dropped)."""
    return pd.DataFrame({
        fetch._C_CODE: ["300929", "300929", "002828", "600000", "000001"],
        fetch._C_NAME: ["A", "A", "B", "C", "D"],
        fetch._C_HOLDER: ["h1", "h2", "h3", "h4", "h5"],
        fetch._C_DIR: ["增持", "增持", "增持", "减持", "增持"],
        fetch._C_QTY: [242.0, 141.0, 216.0, 100.0, -5.0],
        fetch._C_PCT: [1.83, 1.07, 1.07, 0.5, 0.2],
        fetch._C_TXN_END: ["2026-07-01", "2026-07-02", "2026-06-01", "2026-06-01",
                           "2026-06-10"],
        fetch._C_ANNOUNCE: ["2026-07-06", "2026-07-06", "2026-07-07", "2026-07-07",
                            "2026-06-05"],  # last: announce < txn -> dropped
    })


def _wide_prices():
    """A clean rising adj_close panel over trading days for two codes."""
    idx = pd.bdate_range("2026-07-01", periods=40)
    return pd.DataFrame({
        "300929": [10.0 + 0.1 * i for i in range(40)],
        "002828": [20.0 - 0.05 * i for i in range(40)],
    }, index=idx)


# ---- normalize / lag ---------------------------------------------------------
def test_normalize_keeps_only_valid_buys():
    out = fetch.normalize_events(_raw_events())
    # sell dropped, negative-qty dropped, announce<txn dropped -> 3 valid buys.
    assert len(out) == 3
    assert list(out.columns) == list(fetch.EVENTS_HEADER)  # 'direction' filtered out
    assert (out["chg_shares_wan"] > 0).all()
    assert set(out["code"]) == {"300929", "002828"}  # 000001 (announce<txn) dropped


def test_announce_never_before_transaction():
    out = fetch.normalize_events(_raw_events())
    lag = (out["announce_date"] - out["txn_end_date"]).dt.days
    assert (lag >= 0).all(), "look-ahead: announcement precedes transaction"


def test_normalize_extracts_six_digit_code():
    raw = _raw_events()
    raw[fetch._C_CODE] = ["sh600000" if c == "600000" else c
                          for c in raw[fetch._C_CODE]]
    out = fetch.normalize_events(raw)
    assert out["code"].str.fullmatch(r"\d{6}").all()


# ---- cohort entry is strictly after the announcement month (no look-ahead) ---
def test_cohort_entry_strictly_after_announcement_month():
    wide = _wide_prices()
    # July announcements -> entry must be the first trading day of AUGUST.
    m = pd.Period("2026-07", freq="M")
    entry = ic.cohort_entry(wide.index, m)
    assert entry is not None
    assert entry >= pd.Timestamp("2026-08-01")
    # every July announcement date is strictly before the entry.
    for ann in ["2026-07-01", "2026-07-02", "2026-07-31"]:
        assert pd.Timestamp(ann) < entry


def test_cohort_entry_none_when_calendar_ends():
    wide = _wide_prices()
    m = pd.Period("2027-01", freq="M")  # beyond the price calendar
    assert ic.cohort_entry(wide.index, m) is None


def test_cohort_entry_none_for_pre_panel_month_does_not_snap_forward():
    """A cohort whose next-month floor sits years before the price panel start must be
    skipped, NOT snapped onto the panel's first day (that would score a stale event
    against unrelated later prices)."""
    wide = _wide_prices()  # panel starts 2026-07-01
    m = pd.Period("2007-05", freq="M")  # floor 2007-06-01, far before the panel
    assert ic.cohort_entry(wide.index, m) is None


# ---- forward return is strictly after entry ----------------------------------
def test_forward_return_uses_prices_after_entry():
    wide = _wide_prices()
    entry = wide.index[0]
    r = ic.forward_return(wide, "300929", entry, 5)
    p0, p1 = wide["300929"].iloc[0], wide["300929"].iloc[5]
    assert r == pytest.approx(p1 / p0 - 1.0)
    assert r > 0  # rising series


def test_forward_return_none_when_horizon_exceeds_calendar():
    wide = _wide_prices()
    entry = wide.index[-3]
    assert ic.forward_return(wide, "300929", entry, 5) is None


def test_forward_return_sanity_guard_rejects_extreme():
    idx = pd.bdate_range("2026-07-01", periods=10)
    wide = pd.DataFrame({"X": [1.0] * 5 + [100.0] * 5}, index=idx)  # 100x jump
    assert ic.forward_return(wide, "X", idx[0], 5) is None


# ---- monthly signal aggregation ----------------------------------------------
def test_monthly_signal_sums_pct_and_counts_events():
    ev = fetch.normalize_events(_raw_events())
    ev["ann_month"] = ev["announce_date"].dt.to_period("M")
    g = ic.monthly_signal(ev, pd.Period("2026-07", freq="M"))
    row = g[g["code"] == "300929"].iloc[0]
    assert row["n_events"] == 2                       # two July buys for 300929
    assert row["buy_pct"] == pytest.approx(1.83 + 1.07)


# ---- IC sign recovery on a monotone construction -----------------------------
def test_spearman_recovers_positive_monotone():
    a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    b = pd.Series([0.1, 0.2, 0.25, 0.4, 0.5])
    assert ic._spearman(a, b) == pytest.approx(1.0)


def test_spearman_recovers_negative_monotone():
    a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    b = pd.Series([0.5, 0.4, 0.3, 0.2, 0.1])
    assert ic._spearman(a, b) == pytest.approx(-1.0)


def test_compound_returns():
    assert ic._compound([0.1, -0.1]) == pytest.approx(0.1 * 0 + (1.1 * 0.9 - 1.0))
    assert ic._compound([]) == 0.0


# ---- end-to-end no-look-ahead property on the run() path ---------------------
def test_run_entry_after_all_cohort_announcements():
    """Integration: build events + a long clean calendar, run() one horizon, and assert
    every scored cohort's entry is strictly after that month's announcements."""
    ev = fetch.normalize_events(_raw_events())
    ev["ann_month"] = ev["announce_date"].dt.to_period("M")
    idx = pd.bdate_range("2026-06-01", periods=120)
    wide = pd.DataFrame(
        {"300929": [10 + 0.05 * i for i in range(120)],
         "002828": [20 + 0.03 * i for i in range(120)]},
        index=idx,
    )
    ev = ev[ev["code"].isin(wide.columns)]
    out = ic.run(ev, wide, "buy_pct", 5)
    for pm in out["per_month"]:
        if pm["ic"] is None:
            continue
        entry = pd.Timestamp(pm["entry"])
        month_end = pd.Period(pm["month"], freq="M").to_timestamp(how="end")
        assert entry > month_end  # entry strictly after the announcement month
