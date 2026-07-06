"""B099 — institutional-BUILDING first-look: deterministic tests.

The whole first-look hinges on NO LOOK-AHEAD: the quarterly institutional-holding for
quarter Q is not public until ~1-4 months after Q-end, so the follow signal can only be
acted on AFTER its disclosure deadline. These tests pin that property plus signal /
forward-return / IC construction, all on tiny synthetic fixtures (no akshare, no cache).
"""

from __future__ import annotations

import pandas as pd

from scripts.research.b099_inst_ic import (
    _spearman,
    build_quarter_frame,
    disclosure_deadline,
    entry_floor,
    first_trading_day_on_or_after,
    forward_return,
    parse_quarter,
)


# --------------------------------------------------------------------------- #
# NO LOOK-AHEAD — the cardinal property.
# --------------------------------------------------------------------------- #
def test_entry_floor_strictly_after_disclosure_deadline_all_quarters() -> None:
    for year in (2020, 2021, 2024):
        for q in (1, 2, 3, 4):
            assert entry_floor(year, q) > disclosure_deadline(year, q)


def test_disclosure_deadline_calendar() -> None:
    from datetime import date

    assert disclosure_deadline(2024, 1) == date(2024, 4, 30)
    assert disclosure_deadline(2024, 2) == date(2024, 8, 31)
    assert disclosure_deadline(2024, 3) == date(2024, 10, 31)
    # Q4 / annual discloses by Apr 30 of the FOLLOWING year.
    assert disclosure_deadline(2024, 4) == date(2025, 4, 30)


def test_entry_floor_month_after_deadline() -> None:
    from datetime import date

    assert entry_floor(2024, 1) == date(2024, 5, 1)
    assert entry_floor(2024, 2) == date(2024, 9, 1)
    assert entry_floor(2024, 3) == date(2024, 11, 1)
    assert entry_floor(2024, 4) == date(2025, 5, 1)


def test_build_quarter_frame_entry_is_after_deadline() -> None:
    # calendar spanning a Q1 disclosure window; entry must land on/after May 1.
    dates = pd.date_range("2024-04-25", periods=40, freq="B")
    wide = pd.DataFrame({"000001": range(100, 140)}, index=dates, dtype=float)
    panel = pd.DataFrame([{"quarter": "20241", "code": "000001", "hold_pct_chg": 1.0}])
    df, entry = build_quarter_frame(panel, wide, "20241", "hold_pct_chg", horizon=1)
    year, q = parse_quarter("20241")
    assert entry is not None
    assert entry.date() > disclosure_deadline(year, q)      # STRICTLY after deadline
    assert entry.date() >= entry_floor(year, q)


def test_first_trading_day_on_or_after_skips_to_open_day() -> None:
    from datetime import date

    # May 1 (holiday) absent; first trading bar is May 6 -> that is the entry.
    dates = pd.to_datetime(["2024-04-30", "2024-05-06", "2024-05-07"])
    got = first_trading_day_on_or_after(dates, date(2024, 5, 1))
    assert got == pd.Timestamp("2024-05-06")


# --------------------------------------------------------------------------- #
# Forward return — strictly forward from entry, sanity-guarded.
# --------------------------------------------------------------------------- #
def test_forward_return_is_forward_only_from_entry() -> None:
    dates = pd.date_range("2024-05-06", periods=10, freq="B")
    wide = pd.DataFrame({"000001": range(100, 110)}, index=dates, dtype=float)
    entry = dates[0]
    # horizon=3 -> price[entry+3]/price[entry]-1 = 103/100 - 1, using ONLY future bars.
    r = forward_return(wide, "000001", entry, horizon=3)
    assert r is not None
    assert abs(r - (103 / 100 - 1)) < 1e-12


def test_forward_return_none_when_horizon_runs_off_calendar() -> None:
    dates = pd.date_range("2024-05-06", periods=4, freq="B")
    wide = pd.DataFrame({"000001": range(100, 104)}, index=dates, dtype=float)
    assert forward_return(wide, "000001", dates[0], horizon=10) is None


def test_forward_return_sanity_guard_drops_data_error_spikes() -> None:
    dates = pd.date_range("2024-05-06", periods=3, freq="B")
    # 100 -> 1000 in one step = 10x = corrupted split-adjust, must be dropped.
    wide = pd.DataFrame({"000001": [100.0, 500.0, 1000.0]}, index=dates)
    assert forward_return(wide, "000001", dates[0], horizon=2) is None


def test_forward_return_none_for_missing_ticker() -> None:
    dates = pd.date_range("2024-05-06", periods=5, freq="B")
    wide = pd.DataFrame({"000001": range(100, 105)}, index=dates, dtype=float)
    assert forward_return(wide, "999999", dates[0], horizon=1) is None


# --------------------------------------------------------------------------- #
# Signal / IC construction.
# --------------------------------------------------------------------------- #
def test_spearman_monotone_and_reversed() -> None:
    a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(_spearman(a, a) - 1.0) < 1e-12
    assert abs(_spearman(a, a[::-1].reset_index(drop=True)) + 1.0) < 1e-12


def test_build_quarter_frame_carries_signal_and_return() -> None:
    dates = pd.date_range("2024-04-25", periods=80, freq="B")
    wide = pd.DataFrame(
        {"000001": range(100, 180), "000002": range(200, 280)},
        index=dates, dtype=float,
    )
    panel = pd.DataFrame([
        {"quarter": "20241", "code": "000001", "hold_pct_chg": 2.5},
        {"quarter": "20241", "code": "000002", "hold_pct_chg": -1.0},
    ])
    df, _ = build_quarter_frame(panel, wide, "20241", "hold_pct_chg", horizon=5)
    assert set(df["code"]) == {"000001", "000002"}
    assert set(df.columns) >= {"code", "signal", "ret", "entry"}
    # signal preserved verbatim from the panel.
    assert df.set_index("code").loc["000001", "signal"] == 2.5


def test_parse_quarter() -> None:
    assert parse_quarter("20241") == (2024, 1)
    assert parse_quarter("20203") == (2020, 3)
