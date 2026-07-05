"""B085 F001 — residual-momentum computation isolates idiosyncratic from market."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.research.b085_residual_momentum import (
    LOOKBACK_BETA,
    LOOKBACK_MOM,
    SKIP,
    residual_momentum,
)


def test_residual_momentum_captures_idiosyncratic_not_market() -> None:
    n = LOOKBACK_BETA + LOOKBACK_MOM + SKIP + 30
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    t = np.arange(n)
    m = 0.0005 + 0.01 * np.sin(t / 20.0)  # common market daily return
    data = {f"MKT{i:02d}": m for i in range(50)}  # pure market (β=1, zero residual)
    data["RESID_UP"] = m + 0.002    # steady POSITIVE idiosyncratic drift
    data["RESID_DOWN"] = m - 0.002  # steady NEGATIVE idiosyncratic drift
    prices = 100.0 * (1 + pd.DataFrame(data, index=dates)).cumprod()

    last = residual_momentum(prices).iloc[-1]
    # captures the idiosyncratic sign: up positive, down negative, up > down
    assert last["RESID_UP"] > last["RESID_DOWN"]
    assert last["RESID_UP"] > 0 > last["RESID_DOWN"]
    # market-only names ≈ 0 residual momentum (isolated from the market trend)
    mkt_avg = abs(last[[f"MKT{i:02d}" for i in range(50)]].mean())
    assert mkt_avg < abs(last["RESID_UP"]) / 5  # market residual momentum ≪ idiosyncratic
