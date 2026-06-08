"""Frozen parameters for the BL-B011-S2 HK-China Momentum satellite.

Mirrors the B025 ``us_quality_momentum.parameters`` pattern (frozen
dataclass + deterministic ``parameter_hash``) but is far simpler — the
HK-China strategy is **price-only** (momentum + trend + regional-risk), so
there are no fundamentals / sector caps / earnings windows.

**Weight convention (generator decision, design doc §8.2 authoritative).**
``generate_signal().weights_dict()`` returns **sleeve-relative** weights
summing to ``1.0`` over the selected HK-China ETFs + the defensive asset.
The Master scales these by the sleeve's ``planning_weight`` (0.10), so the
design doc's TOTAL-portfolio caps (§9.1: per-ETF ≤ 10%, KWEB ≤ 5-10%) are
realised as ``sleeve_weight × within_sleeve_weight``:

* a single ETF filling the sleeve → ``1.0 × 0.10 = 10%`` total = the per-ETF
  cap (design §8.2 "Top-1 占用模块全部允许仓位"); so the within-sleeve
  per-ETF cap is ``1.0``.
* ``kweb_sublimit`` IS enforced within the sleeve (sleeve-relative): default
  ``0.5`` → ``0.5 × 0.10 = 5%`` total, the conservative end of design §9.1's
  5-10% China-internet sub-limit. Excess rotates to the defensive asset.

The literal "max_position_weight=0.10" in the batch plan is the TOTAL-level
cap; it is recorded here for the audit trail but the binding within-sleeve
caps are ``top_n`` (1-2 ETFs) + ``kweb_sublimit``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

DEFAULT_STRATEGY_ID = "hk_china_momentum"
DEFAULT_TOP_N = 2
# Sleeve-relative per-ETF cap. 1.0 lets a single ETF fill the sleeve (Top-1,
# design §8.2); the 10%-of-total cap is the Master's planning_weight job.
DEFAULT_MAX_POSITION_WEIGHT = 1.0
# Sleeve-relative China-internet (KWEB) sub-limit: 0.5 → 5% of total.
DEFAULT_KWEB_SUBLIMIT = 0.5
DEFAULT_MA_LONG = 200
DEFAULT_REBALANCE_FREQUENCY = "quarterly"
# The defensive proxy the sleeve rotates to (design §8.2 "短债"); matches the
# Master's default ``defensive_asset``.
DEFAULT_DEFENSIVE_ASSET = "SGOV"
KWEB_TICKER = "KWEB"
FACTOR_WEIGHT_SUM_TOLERANCE = 1e-8


class ParameterValidationError(ValueError):
    """Raised when an immutable parameter bundle violates strategy invariants."""


@dataclass(frozen=True, slots=True)
class MomentumWeights:
    """Weights on the 3-, 6-, 12-month returns in the composite momentum score.

    Defaults follow design doc §7.1: ``0.4·r3m + 0.3·r6m + 0.3·r12m``. Must
    sum to ``1.0`` within :data:`FACTOR_WEIGHT_SUM_TOLERANCE`.
    """

    r3m: float = 0.4
    r6m: float = 0.3
    r12m: float = 0.3

    def __post_init__(self) -> None:
        for name in ("r3m", "r6m", "r12m"):
            if getattr(self, name) < 0:
                raise ParameterValidationError(f"momentum weight {name} must be >= 0")
        total = self.r3m + self.r6m + self.r12m
        if abs(total - 1.0) > FACTOR_WEIGHT_SUM_TOLERANCE:
            raise ParameterValidationError(
                f"momentum weights must sum to 1.0 (got {total:.10f})"
            )

    def as_mapping(self) -> dict[str, float]:
        return {"r3m": self.r3m, "r6m": self.r6m, "r12m": self.r12m}


@dataclass(frozen=True, slots=True)
class HkChinaMomentumParameters:
    """Parameters recorded with every HK-China signal artifact."""

    strategy_id: str = DEFAULT_STRATEGY_ID
    top_n: int = DEFAULT_TOP_N
    momentum_weights: MomentumWeights = field(default_factory=MomentumWeights)
    max_position_weight: float = DEFAULT_MAX_POSITION_WEIGHT
    kweb_sublimit: float = DEFAULT_KWEB_SUBLIMIT
    ma_long: int = DEFAULT_MA_LONG
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY
    defensive_asset: str = DEFAULT_DEFENSIVE_ASSET

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ParameterValidationError("strategy_id must be a non-empty string")
        if self.top_n not in (1, 2):
            raise ParameterValidationError("top_n must be 1 or 2 (design §8.2 Top 1-2)")
        if not 0.0 < self.max_position_weight <= 1.0:
            raise ParameterValidationError("max_position_weight must be in (0, 1]")
        if not 0.0 < self.kweb_sublimit <= 1.0:
            raise ParameterValidationError("kweb_sublimit must be in (0, 1]")
        if self.ma_long <= 1:
            raise ParameterValidationError("ma_long must be > 1")
        if not self.defensive_asset:
            raise ParameterValidationError("defensive_asset must be non-empty")
        if self.rebalance_frequency not in {"monthly", "quarterly"}:
            raise ParameterValidationError(
                "rebalance_frequency must be 'monthly' or 'quarterly'"
            )

    def parameter_hash(self) -> str:
        """Deterministic 64-char SHA-256 of the canonical JSON payload.

        Mirrors the other strategies' ``parameter_hash`` so artifacts that
        compare hashes across sleeves behave consistently."""

        payload = {
            "defensive_asset": self.defensive_asset,
            "kweb_sublimit": self.kweb_sublimit,
            "ma_long": self.ma_long,
            "max_position_weight": self.max_position_weight,
            "momentum_weights": self.momentum_weights.as_mapping(),
            "rebalance_frequency": self.rebalance_frequency,
            "strategy_id": self.strategy_id,
            "top_n": self.top_n,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(canonical).hexdigest()
