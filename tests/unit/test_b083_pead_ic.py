"""B083 F002 — PEAD IC look-ahead rigor (命门).

The whole first-look hinges on entering STRICTLY after the announcement (no
look-ahead). This pins that: entry is the first trading day > announce_date, and
forward returns are forward-only from that entry.
"""

from __future__ import annotations

import pandas as pd

from scripts.research.b083_pead_ic import compute_surprise, forward_returns


def test_forward_returns_entry_strictly_after_announcement() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    close = pd.DataFrame({"000001": range(100, 110)}, index=dates, dtype=float)
    open_ = close.copy()
    prev = close.shift(1)
    # announced on day index 2 (2024-01-03) → entry MUST be index 3, not 2.
    ev = pd.DataFrame([{"ticker": "000001", "announce_date": dates[2], "surprise": 0.5}])
    fr = forward_returns(close, open_, prev, ev, (1, 5))
    assert len(fr) == 1
    assert fr.iloc[0]["entry"] == dates[3]          # strictly AFTER the announcement
    assert fr.iloc[0]["announce"] < fr.iloc[0]["entry"]
    # ret_1 = close[entry+1]/close[entry] - 1 = 104/103 - 1 (forward-only)
    assert abs(fr.iloc[0]["ret_1"] - (104 / 103 - 1)) < 1e-9


def test_compute_surprise_drops_zero_baseline() -> None:
    ev = pd.DataFrame([
        {"ticker": "1", "forecast_value": 120.0, "prior_year_value": 100.0},   # +0.2
        {"ticker": "2", "forecast_value": 50.0, "prior_year_value": 0.0},       # div0 → dropped
        {"ticker": "3", "forecast_value": -30.0, "prior_year_value": 100.0},    # -1.3
    ])
    out = compute_surprise(ev)
    assert set(out["ticker"]) == {"1", "3"}
    assert abs(out[out["ticker"] == "1"].iloc[0]["surprise"] - 0.2) < 1e-9
