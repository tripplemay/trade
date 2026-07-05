"""B085 F001 screen — forward_return is strictly future (no look-ahead)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.research.b085_residual_vs_raw_ic import forward_return, raw_momentum


def test_forward_return_is_strictly_future() -> None:
    dates = pd.date_range("2020-01-01", periods=40, freq="B")
    prices = pd.DataFrame({"A": np.arange(100.0, 140.0)}, index=dates)
    fwd = forward_return(prices, horizon=5)
    # fwd at t must equal price_{t+5}/price_t − 1 (uses FUTURE prices, not past)
    t = 10
    expected = prices["A"].iloc[t + 5] / prices["A"].iloc[t] - 1.0
    assert abs(fwd["A"].iloc[t] - expected) < 1e-9
    # the last `horizon` rows have no future → NaN (cannot leak)
    assert fwd["A"].iloc[-5:].isna().all()


def test_raw_momentum_is_past_only() -> None:
    # raw momentum at t must not depend on any price after t (shifted by SKIP, past window)
    dates = pd.date_range("2019-01-01", periods=300, freq="B")
    prices = pd.DataFrame({"A": np.linspace(100, 200, 300)}, index=dates)
    rm = raw_momentum(prices)
    # perturbing a FUTURE price must not change raw momentum at an earlier date
    t = 200
    base = rm["A"].iloc[t]
    prices2 = prices.copy()
    prices2.iloc[t + 10] *= 1.5  # change a future price
    base2 = raw_momentum(prices2)["A"].iloc[t]
    assert abs(base - base2) < 1e-12  # earlier signal unaffected by future
