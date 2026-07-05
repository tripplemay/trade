"""B082 F002 — unit tests for the dividend-lowvol spread signal.

Hand-computed tiny series pin the TR−PR dividend-yield reconstruction, the spread, and
the three-tier target mapping (the acceptance's "TR−PR 反推正确性 / 三档规则边界").
"""

from __future__ import annotations

import pandas as pd

from trade.strategies.cn_dividend_lowvol.parameters import CnDividendLowvolParameters
from trade.strategies.cn_dividend_lowvol.signal import (
    compute_spread,
    month_end_target_weights,
    reconstruct_dividend_yield,
    target_weight_series,
)


def _series(pairs: list[tuple[str, float]]) -> pd.Series:
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx)


def test_reconstruct_dividend_yield_hand_computed() -> None:
    # TR grows faster than PR by exactly the reinvested dividend; lookback=2.
    tr = _series([("2020-01-01", 100.0), ("2020-01-02", 100.0),
                  ("2020-01-03", 110.0), ("2020-01-06", 121.0)])
    pr = _series([("2020-01-01", 100.0), ("2020-01-02", 100.0),
                  ("2020-01-03", 105.0), ("2020-01-06", 110.0)])
    divy = reconstruct_dividend_yield(tr, pr, lookback_days=2)
    # t=2: (110/100 - 105/100) * 100 = 5.0 ; t=3: (121/100 - 110/100) * 100 = 11.0
    assert list(divy.round(6)) == [5.0, 11.0]
    assert [d.date().isoformat() for d in divy.index] == ["2020-01-03", "2020-01-06"]


def test_reconstruct_aligns_on_common_dates_only() -> None:
    tr = _series([("2020-01-01", 100.0), ("2020-01-02", 110.0), ("2020-01-03", 121.0)])
    pr = _series([("2020-01-01", 100.0), ("2020-01-03", 110.0)])  # missing 01-02
    divy = reconstruct_dividend_yield(tr, pr, lookback_days=1)
    # Only 01-01 and 01-03 are common; with lookback=1 the first common date is NaN,
    # so exactly one value survives (01-03), computed over the common-date step.
    assert len(divy) == 1
    assert divy.index[0].date().isoformat() == "2020-01-03"


def test_compute_spread_forward_fills_10y() -> None:
    divy = _series([("2020-03-31", 5.0), ("2020-04-30", 11.0)])
    y10 = _series([("2020-03-01", 3.0), ("2020-04-30", 4.0)])
    spread = compute_spread(divy, y10)
    # 03-31 ffills the 03-01 quote (3.0) → 5-3=2.0 ; 04-30 uses 4.0 → 11-4=7.0.
    assert list(spread.round(6)) == [2.0, 7.0]


def test_target_weight_series_applies_three_tiers() -> None:
    params = CnDividendLowvolParameters()
    spread = _series([("2020-01-01", 2.0), ("2020-02-01", 7.0), ("2020-03-01", 0.5)])
    weights = target_weight_series(spread, params)
    assert list(weights) == [0.5, 1.0, 0.25]  # 半配 / 满配 / 低配


def test_month_end_target_weights_resamples_to_last_of_month() -> None:
    params = CnDividendLowvolParameters()
    # Two obs in Jan (last is 3.0 → 满配), one in Feb (1.0 → 低配).
    spread = _series([("2020-01-10", 1.0), ("2020-01-31", 3.0), ("2020-02-28", 1.0)])
    monthly = month_end_target_weights(spread, params)
    assert len(monthly) == 2
    assert list(monthly) == [1.0, 0.25]
