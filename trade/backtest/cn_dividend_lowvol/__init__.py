"""B082 F002 — dividend-lowvol single-asset backtest engine (monthly, T+1)."""

from trade.backtest.cn_dividend_lowvol.engine import (
    BacktestMetrics,
    BacktestResult,
    compute_metrics,
    cpcv_lite_fold_cagrs,
    simulate_single_asset,
    walk_forward_oos_metrics,
    window_max_drawdown,
)

__all__ = [
    "BacktestMetrics",
    "BacktestResult",
    "compute_metrics",
    "cpcv_lite_fold_cagrs",
    "simulate_single_asset",
    "walk_forward_oos_metrics",
    "window_max_drawdown",
]
