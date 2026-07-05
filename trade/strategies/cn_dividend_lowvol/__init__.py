"""B082 F002 — 红利低波 (dividend low-volatility) defensive sleeve strategy.

A single-instrument tactical allocation between a dividend-low-vol basket and cash,
driven by the frozen three-tier 股息率−十年国债利差 rule. Advisory / research-only.
"""

from trade.strategies.cn_dividend_lowvol.parameters import (
    CnDividendLowvolParameterError,
    CnDividendLowvolParameters,
)
from trade.strategies.cn_dividend_lowvol.signal import (
    compute_spread,
    month_end_target_weights,
    reconstruct_dividend_yield,
    target_weight_series,
)

__all__ = [
    "CnDividendLowvolParameterError",
    "CnDividendLowvolParameters",
    "compute_spread",
    "month_end_target_weights",
    "reconstruct_dividend_yield",
    "target_weight_series",
]
