"""B089 F001 — static VIX tail-risk overlay (SPY + X% VIXY) analysis primitives.

A small static allocation to VIXY (ProShares VIX Short-Term Futures) hedges equity tail
risk: when SPY crashes, VIXY spikes (measured 2020 covid: SPY −34%, VIXY +278%). The
trade-off is VIXY's structural **negative carry** (roll cost) that drags long-run return.
This module builds the monthly-rebalanced overlay return series and the two objective
metrics that quantify BOTH sides — tail-loss reduction and the carry cost. Honest by
construction: the hedge is not free, and the report must show the drag alongside the
protection.

Research module (pure numpy/pandas): touches no strategy, no cn_attack flagship, no
production data path. The turnover/tail metrics are mechanical, so this is objectively
measurable — not a subtle-edge claim.
"""

from __future__ import annotations

from typing import Any


def static_overlay_returns(spy_ret: Any, vixy_ret: Any, vixy_weight: float) -> Any:
    """Monthly-rebalanced (1−w) SPY + w VIXY daily return series.

    Weights reset to the target each month-start and drift with returns within the month
    (so the overlay captures both the hedge payoff and the rebalance discipline).
    """

    import pandas as pd

    w_spy0, w_vixy0 = 1.0 - vixy_weight, vixy_weight
    out: list[float] = []
    cur_spy, cur_vixy = w_spy0, w_vixy0
    prev_month = None
    for date, sr, vr in zip(spy_ret.index, spy_ret, vixy_ret, strict=True):
        month = (date.year, date.month)
        if prev_month is not None and month != prev_month:
            cur_spy, cur_vixy = w_spy0, w_vixy0  # month-start rebalance
        out.append(cur_spy * sr + cur_vixy * vr)
        v_spy, v_vixy = cur_spy * (1.0 + sr), cur_vixy * (1.0 + vr)  # drift
        total = v_spy + v_vixy
        cur_spy, cur_vixy = v_spy / total, v_vixy / total
        prev_month = month
    return pd.Series(out, index=spy_ret.index, name=f"overlay_{vixy_weight:.0%}")


def max_drawdown(returns: Any) -> float:
    """Worst peak-to-trough of the cumulative-return equity curve (negative)."""

    equity = (1.0 + returns).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def cagr(returns: Any) -> float:
    """Annualised compound growth (252 trading days/year)."""

    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    equity = float((1.0 + r).cumprod().iloc[-1])
    years = len(r) / 252.0
    return equity ** (1.0 / years) - 1.0 if equity > 0 else -1.0
