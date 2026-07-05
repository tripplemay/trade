"""B082 F002 — dividend-lowvol spread signal (股息率 − 十年国债利差 → 三档目标仓位).

Pure pandas (no akshare / broker import — ``trade`` stays offline; the backtest and
producer feed it series read from the frozen CSV snapshot). Three steps:

1. ``reconstruct_dividend_yield`` — back out the index's OWN trailing dividend yield
   from the total-return (H20269) minus price (H30269) rolling growth spread
   (探针 报告 §3: the csindex valuation endpoint only returns ~1 month, but TR−PR over
   a trailing year IS the index-口径 dividend yield, 21.5y deep). Additive form
   ``TR_return − PR_return`` over ``lookback_days`` trading days, expressed in percent.
2. ``compute_spread`` — dividend-yield% minus the 10Y-treasury yield% (both percent),
   the review's "利差" monitor. The 10Y series is forward-filled onto the yield dates.
3. ``target_weight_series`` / ``month_end_target_weights`` — apply the frozen three-tier
   step rule (parameters.py) elementwise. The step IS the no-trade band: the target
   only moves when the spread crosses a tier boundary (2.5% / 1.5%).

★ The thresholds live in parameters.py and are spec-先验 (禁止扫参); this module only
READS them — it has no optimisation / grid path.
"""

from __future__ import annotations

import pandas as pd

from trade.strategies.cn_dividend_lowvol.parameters import (
    CnDividendLowvolParameters,
)


def reconstruct_dividend_yield(
    total_return: pd.Series,
    price: pd.Series,
    lookback_days: int,
) -> pd.Series:
    """Index-口径 trailing dividend yield (percent) from the TR−PR growth spread.

    ``total_return`` (H20269) and ``price`` (H30269) are date-indexed close series.
    They are aligned on their common trading dates, each compounded over the trailing
    ``lookback_days`` observations, and the additive difference of the two trailing
    returns (探针 §3 prescription) is returned in percentage points. The leading
    ``lookback_days`` rows are ``NaN`` (insufficient history) and dropped.
    """

    if lookback_days <= 0:
        raise ValueError("lookback_days must be > 0")
    tr = _clean(total_return)
    pr = _clean(price)
    common = tr.index.intersection(pr.index)
    tr = tr.reindex(common)
    pr = pr.reindex(common)
    tr_return = tr / tr.shift(lookback_days) - 1.0
    pr_return = pr / pr.shift(lookback_days) - 1.0
    dividend_yield_pct = (tr_return - pr_return) * 100.0
    return dividend_yield_pct.dropna()


def compute_spread(
    dividend_yield_pct: pd.Series,
    yield_10y_pct: pd.Series,
) -> pd.Series:
    """Spread (percentage points) = dividend-yield% − 10Y-treasury%.

    The 10Y series is forward-filled onto the dividend-yield dates (a bond yield is a
    step function between quotes), then subtracted. Dates without any prior 10Y quote
    are dropped (no silent zero-yield).
    """

    divy = _clean(dividend_yield_pct)
    y10 = _clean(yield_10y_pct)
    aligned_y10 = y10.reindex(divy.index.union(y10.index)).ffill().reindex(divy.index)
    spread = divy - aligned_y10
    return spread.dropna()


def target_weight_series(
    spread_pct: pd.Series,
    params: CnDividendLowvolParameters,
) -> pd.Series:
    """Elementwise three-tier target weight for a daily spread series (焊死 rule)."""

    return spread_pct.map(params.target_weight_for_spread).astype(float)


def month_end_target_weights(
    spread_pct: pd.Series,
    params: CnDividendLowvolParameters,
) -> pd.Series:
    """Month-end (execution cadence) three-tier target weights.

    Resamples the daily spread to its last observation per calendar month, then maps
    each to its tier. The monthly cadence + the coarse 3-step target together are the
    strategy's low-turnover 'monitor daily, act monthly, 不动区' rule (spec §0).
    """

    monthly_spread = _clean(spread_pct).resample("ME").last().dropna()
    return target_weight_series(monthly_spread, params)


def _clean(series: pd.Series) -> pd.Series:
    """Sorted, positive-index, de-duplicated numeric series (defensive boundary)."""

    numeric = pd.to_numeric(series, errors="coerce").dropna()
    numeric = numeric[~numeric.index.duplicated(keep="last")]
    return numeric.sort_index()


__all__ = [
    "compute_spread",
    "month_end_target_weights",
    "reconstruct_dividend_yield",
    "target_weight_series",
]
