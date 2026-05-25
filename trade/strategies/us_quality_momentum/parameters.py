"""Frozen parameters for the B025 US Quality Momentum strategy.

Following the ``global_etf_momentum.MomentumParameters`` pattern: every
field needed to reproduce a signal lives on a single frozen dataclass, and
``parameter_hash()`` returns a deterministic 64-char SHA-256 over the
canonical JSON representation so downstream artifacts (backtest reports,
order tickets) can record a single immutable identifier.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

DEFAULT_STRATEGY_ID = "us_quality_momentum"
DEFAULT_TOP_N = 15
DEFAULT_MAX_POSITION_WEIGHT = 0.07
DEFAULT_MAX_SECTOR_WEIGHT = 0.30
DEFAULT_EARNINGS_WINDOW_DAYS = 5
DEFAULT_REBALANCE_FREQUENCY = "monthly"
FACTOR_WEIGHT_SUM_TOLERANCE = 1e-8


class ParameterValidationError(ValueError):
    """Raised when an immutable parameter bundle violates strategy invariants."""


@dataclass(frozen=True, slots=True)
class FactorWeights:
    """Weights applied to each percent-ranked factor in the composite score.

    Must sum to ``1.0`` within :data:`FACTOR_WEIGHT_SUM_TOLERANCE`. Defaults
    follow strategy doc §7 full version (35/30/15/10/10).
    """

    momentum: float = 0.35
    quality: float = 0.30
    low_vol: float = 0.15
    value: float = 0.10
    trend: float = 0.10

    def __post_init__(self) -> None:
        for name in ("momentum", "quality", "low_vol", "value", "trend"):
            value = getattr(self, name)
            if value < 0:
                raise ParameterValidationError(f"factor weight {name} must be >= 0")
        total = self.momentum + self.quality + self.low_vol + self.value + self.trend
        if abs(total - 1.0) > FACTOR_WEIGHT_SUM_TOLERANCE:
            raise ParameterValidationError(
                f"factor weights must sum to 1.0 (got {total:.10f})"
            )

    def as_mapping(self) -> dict[str, float]:
        """Stable mapping used by the score combiner and serialization."""

        return {
            "momentum": self.momentum,
            "quality": self.quality,
            "low_vol": self.low_vol,
            "value": self.value,
            "trend": self.trend,
        }


@dataclass(frozen=True, slots=True)
class UsQualityMomentumParameters:
    """Strategy parameters recorded with every signal artifact.

    All defaults match B025 spec §F003 acceptance.
    """

    strategy_id: str = DEFAULT_STRATEGY_ID
    top_n: int = DEFAULT_TOP_N
    factor_weights: FactorWeights = field(default_factory=FactorWeights)
    max_position_weight: float = DEFAULT_MAX_POSITION_WEIGHT
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT
    earnings_window_days: int = DEFAULT_EARNINGS_WINDOW_DAYS
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ParameterValidationError("strategy_id must be a non-empty string")
        if self.top_n <= 0:
            raise ParameterValidationError("top_n must be > 0")
        if not 0.0 < self.max_position_weight <= 1.0:
            raise ParameterValidationError(
                "max_position_weight must be in (0, 1]"
            )
        if not 0.0 < self.max_sector_weight <= 1.0:
            raise ParameterValidationError("max_sector_weight must be in (0, 1]")
        if self.earnings_window_days < 0:
            raise ParameterValidationError("earnings_window_days must be >= 0")
        if self.rebalance_frequency not in {"monthly", "quarterly"}:
            raise ParameterValidationError(
                "rebalance_frequency must be 'monthly' or 'quarterly'"
            )
        # Top N × max position weight needs to give >= 1.0 — otherwise the
        # post-cap weights can never sum to one and the cash buffer fills
        # silently. Spec wants Top 15 × 7% = 1.05, comfortably above.
        if self.top_n * self.max_position_weight < 1.0:
            raise ParameterValidationError(
                "top_n * max_position_weight must be >= 1.0 (cap is unreachable)"
            )

    def parameter_hash(self) -> str:
        """Deterministic 64-char SHA-256 of the canonical JSON payload.

        Mirrors :meth:`trade.strategies.global_etf_momentum.MomentumParameters.parameter_hash`
        so artifacts that compare hashes across strategies behave consistently.
        """

        payload = {
            "earnings_window_days": self.earnings_window_days,
            "factor_weights": self.factor_weights.as_mapping(),
            "max_position_weight": self.max_position_weight,
            "max_sector_weight": self.max_sector_weight,
            "rebalance_frequency": self.rebalance_frequency,
            "strategy_id": self.strategy_id,
            "top_n": self.top_n,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(canonical).hexdigest()
