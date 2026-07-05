"""B089 F001 — VIX overlay mechanics: weighted-average return, monthly rebalance, metrics."""

from __future__ import annotations

import pandas as pd

from trade.analysis.vix_overlay import cagr, max_drawdown, static_overlay_returns


def test_overlay_is_weighted_average_on_first_day() -> None:
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    spy = pd.Series([0.10, -0.10], index=idx)
    vixy = pd.Series([-0.20, 0.30], index=idx)
    o = static_overlay_returns(spy, vixy, 0.10)
    assert abs(o.iloc[0] - (0.9 * 0.10 + 0.1 * -0.20)) < 1e-12  # 0.07


def test_overlay_rebalances_at_month_change() -> None:
    idx = pd.to_datetime(["2020-01-31", "2020-02-03"])  # month boundary between days
    spy = pd.Series([0.10, -0.10], index=idx)
    vixy = pd.Series([-0.20, 0.30], index=idx)
    o = static_overlay_returns(spy, vixy, 0.10)
    # day 2 is a new month → weights reset to target 0.9/0.1 (not drifted)
    assert abs(o.iloc[1] - (0.9 * -0.10 + 0.1 * 0.30)) < 1e-12  # -0.06


def test_max_drawdown_peak_to_trough() -> None:
    r = pd.Series([0.10, -0.50])  # equity 1.1 → 0.55 → dd = -0.5
    assert abs(max_drawdown(r) - (-0.5)) < 1e-12


def test_cagr_doubling_over_one_year() -> None:
    daily = 2 ** (1 / 252) - 1  # compounds to 2x over 252 days
    r = pd.Series([daily] * 252)
    assert abs(cagr(r) - 1.0) < 1e-6
