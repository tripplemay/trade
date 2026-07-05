"""B084 F002 — ETF trend mechanics: forward-only returns + past-momentum signal."""

from __future__ import annotations

import pandas as pd

from scripts.research.b084_etf_trend_ic import trend_vs_hold


def test_trend_uses_forward_return_and_past_momentum() -> None:
    # One ETF, monotonically rising month-end prices → positive 12m momentum after
    # warmup → held every month → strat_ret must equal the FORWARD (t+1) hold return.
    dates = pd.date_range("2020-01-31", periods=15, freq="ME")
    panel = pd.DataFrame({"510300": [100.0 * (1.02 ** i) for i in range(15)]}, index=dates)
    out = trend_vs_hold(panel)
    # after 12m warmup, before the last month (no forward) → rows 12..13
    assert len(out) >= 1
    row = out.iloc[0]  # month index 12
    assert row["n_held"] == 1  # positive momentum → held
    # forward return t→t+1 = 1.02 - 1; strat (single held) == hold
    assert abs(row["strat_ret"] - 0.02) < 1e-9
    assert abs(row["strat_ret"] - row["hold_ret"]) < 1e-9


def test_trend_goes_to_cash_on_negative_momentum() -> None:
    # Monotonically FALLING → negative 12m momentum → not held → strat_ret = 0 (cash),
    # protecting from the down move the buy-hold leg suffers.
    dates = pd.date_range("2020-01-31", periods=15, freq="ME")
    panel = pd.DataFrame({"510300": [100.0 * (0.98 ** i) for i in range(15)]}, index=dates)
    out = trend_vs_hold(panel)
    row = out.iloc[0]
    assert row["n_held"] == 0  # negative momentum → cash
    assert row["strat_ret"] == 0.0  # cash
    assert row["hold_ret"] < 0  # buy-hold takes the loss
