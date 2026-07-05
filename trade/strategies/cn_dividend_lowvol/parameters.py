"""B082 F002 — frozen parameters for the 红利低波 (dividend low-vol) defensive sleeve.

The strategy is a SINGLE-instrument tactical allocation between the dividend-low-vol
basket (H20269 total-return index primary口径; 512890 ETF implementability layer) and
cash, driven by the **dividend-yield − 10Y-treasury spread**. The target weight is a
three-tier step function of that spread:

- spread ≥ 2.5%  → 满配 100%  (wide spread: the sleeve is cheap vs. bonds)
- 1.5% ≤ spread < 2.5% → 半配 50%
- spread < 1.5%  → 低配 25%   (narrow spread: crowded / expensive vs. bonds)

★ INVARIANT (spec §3 ①): the three thresholds (2.5% / 1.5%) and their target weights
are a **spec-先验 death rule** — set from the review's "利差 <2% 降配" guidance, NOT
optimised on the backtest. They are module-level constants; there is **no** search /
sweep / optimisation path over them anywhere in the codebase. The backtest DISCLOSES
their effect; it never tunes them (防过拟合, 评审 §2 纪律).

Mirrors the frozen-dataclass + deterministic ``parameter_hash`` shape of
:class:`trade.strategies.cn_attack_momentum_quality.parameters.CnAttackParameters`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

DEFAULT_STRATEGY_ID = "cn_dividend_lowvol"

# ★ Spec-先验 three-tier spread rule (焊死 — 禁止回测扫参). Spread is measured in
# PERCENTAGE POINTS (dividend-yield% − 10Y-yield%).
SATURATED_SPREAD_PCT = 2.5  # ≥ this → 满配
HALF_SPREAD_PCT = 1.5  # ≥ this (and < saturated) → 半配; < this → 低配

FULL_WEIGHT = 1.0  # 满配
HALF_WEIGHT = 0.5  # 半配
LOW_WEIGHT = 0.25  # 低配

# The trailing-window (trading days) used to back out the index's own dividend yield
# from the TR−PR growth spread (探针 报告 §3: ≈1 year = 252 trading days).
DIVIDEND_YIELD_LOOKBACK_DAYS = 252

# Monthly execution + a no-trade band on the TARGET tier: because the target is
# already a coarse 3-step function, the band is expressed as "only re-trade when the
# spread crosses a tier boundary" (handled in signal.py); this scalar records the
# minimum weight change worth executing at the ETF layer (手数取整 noise below it is
# skipped). It is an EXECUTION knob, never a signal threshold.
MIN_REBALANCE_WEIGHT_DELTA = 0.05


class CnDividendLowvolParameterError(ValueError):
    """Raised when an immutable dividend-lowvol parameter bundle is invalid."""


@dataclass(frozen=True, slots=True)
class CnDividendLowvolParameters:
    """Immutable parameter bundle recorded with every dividend-lowvol artifact.

    Every field DEFAULTS to the spec-先验 constant above. The thresholds are exposed
    as fields only so the frozen bundle can be *recorded* (and its ``parameter_hash``
    computed) — NOT so they can be swept: the backtest constructs exactly one bundle
    (the defaults) and never varies ``saturated_spread_pct`` / ``half_spread_pct``.
    ``__post_init__`` enforces the tier ordering so a mis-constructed bundle fails
    loudly rather than silently inverting the rule.
    """

    strategy_id: str = DEFAULT_STRATEGY_ID
    saturated_spread_pct: float = SATURATED_SPREAD_PCT
    half_spread_pct: float = HALF_SPREAD_PCT
    full_weight: float = FULL_WEIGHT
    half_weight: float = HALF_WEIGHT
    low_weight: float = LOW_WEIGHT
    dividend_yield_lookback_days: int = DIVIDEND_YIELD_LOOKBACK_DAYS
    min_rebalance_weight_delta: float = MIN_REBALANCE_WEIGHT_DELTA

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise CnDividendLowvolParameterError("strategy_id must be a non-empty string")
        if not self.saturated_spread_pct > self.half_spread_pct:
            raise CnDividendLowvolParameterError(
                "saturated_spread_pct must be > half_spread_pct "
                f"(got {self.saturated_spread_pct} <= {self.half_spread_pct})"
            )
        # Tier weights must be a monotone non-decreasing ladder in [0, 1]: wider
        # spread never maps to a *smaller* allocation.
        weights = (self.low_weight, self.half_weight, self.full_weight)
        for weight in weights:
            if not 0.0 <= weight <= 1.0:
                raise CnDividendLowvolParameterError(
                    f"tier weights must be in [0, 1]; got {weights}"
                )
        if not self.low_weight <= self.half_weight <= self.full_weight:
            raise CnDividendLowvolParameterError(
                f"tier weights must be non-decreasing low<=half<=full; got {weights}"
            )
        if self.dividend_yield_lookback_days <= 0:
            raise CnDividendLowvolParameterError(
                "dividend_yield_lookback_days must be > 0"
            )
        if self.min_rebalance_weight_delta < 0:
            raise CnDividendLowvolParameterError(
                "min_rebalance_weight_delta must be >= 0"
            )

    def target_weight_for_spread(self, spread_pct: float) -> float:
        """Map a spread (percentage points) to its tier target weight (焊死 rule).

        ``NaN`` spread (insufficient history to back out the yield) maps to the LOW
        tier — the honest 'do not lean in without the signal' default, never a
        silent full allocation.
        """

        if spread_pct != spread_pct:  # NaN
            return self.low_weight
        if spread_pct >= self.saturated_spread_pct:
            return self.full_weight
        if spread_pct >= self.half_spread_pct:
            return self.half_weight
        return self.low_weight

    def parameter_hash(self) -> str:
        """Deterministic 64-char SHA-256 of the canonical JSON payload.

        Mirrors the CN attack engine's ``parameter_hash`` so backtest reports and
        trial-registry rows record a single immutable identifier per configuration.
        """

        payload = {
            "dividend_yield_lookback_days": self.dividend_yield_lookback_days,
            "full_weight": self.full_weight,
            "half_spread_pct": self.half_spread_pct,
            "half_weight": self.half_weight,
            "low_weight": self.low_weight,
            "min_rebalance_weight_delta": self.min_rebalance_weight_delta,
            "saturated_spread_pct": self.saturated_spread_pct,
            "strategy_id": self.strategy_id,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "DEFAULT_STRATEGY_ID",
    "DIVIDEND_YIELD_LOOKBACK_DAYS",
    "FULL_WEIGHT",
    "HALF_SPREAD_PCT",
    "HALF_WEIGHT",
    "LOW_WEIGHT",
    "MIN_REBALANCE_WEIGHT_DELTA",
    "SATURATED_SPREAD_PCT",
    "CnDividendLowvolParameterError",
    "CnDividendLowvolParameters",
]
