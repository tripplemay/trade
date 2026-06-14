"""B063 F002 — frozen parameters for the real-data HK-China momentum research
strategy.

Mirrors :class:`trade.strategies.hk_china_momentum.parameters.HkChinaMomentumParameters`
(same momentum weights / 200D trend / quarterly cadence, reusing its
:class:`MomentumWeights`) but differs where the universe differs:

* **No KWEB sub-limit / ETF special-casing** — the candidates are individual
  stocks, so weighting is generic equal-weight of the selected top names with a
  single per-name cap.
* **Wider ``top_n``** — the proxy holds 1-2 *diversified ETFs*; a fair real
  basket holds several *single* names. Default ``top_n = 6`` is a deliberately
  concentrated-but-not-degenerate basket. It is a parameter so B063 F003/F004
  can sensitivity-test concentration (spec §3 requires attributing any return
  difference to concentration vs data-source, not conflating them).

Sleeve-relative weights sum to ``1.0`` over the selected names + the defensive
asset, identical to the proxy convention.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

# Reuse the proxy strategy's momentum-weight bundle verbatim (same 0.4/0.3/0.3
# composite); a single definition keeps the two strategies' momentum identical.
from trade.strategies.hk_china_momentum.parameters import (
    MomentumWeights,
    ParameterValidationError,
)

DEFAULT_STRATEGY_ID = "hk_china_real"
DEFAULT_TOP_N = 6
# Per-name sleeve-relative cap. 1.0 lets equal-weight stand uncapped; a tighter
# value (e.g. 0.25) caps single-name concentration and rotates the excess to the
# defensive asset.
DEFAULT_MAX_POSITION_WEIGHT = 1.0
DEFAULT_MA_LONG = 200
DEFAULT_REBALANCE_FREQUENCY = "quarterly"
DEFAULT_DEFENSIVE_ASSET = "SGOV"

_MAX_TOP_N = 30  # bounded by the wide universe size; a guard, not a real limit


@dataclass(frozen=True, slots=True)
class HkChinaRealParameters:
    """Parameters recorded with every real-data HK-China signal artifact."""

    strategy_id: str = DEFAULT_STRATEGY_ID
    top_n: int = DEFAULT_TOP_N
    momentum_weights: MomentumWeights = field(default_factory=MomentumWeights)
    max_position_weight: float = DEFAULT_MAX_POSITION_WEIGHT
    ma_long: int = DEFAULT_MA_LONG
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY
    defensive_asset: str = DEFAULT_DEFENSIVE_ASSET

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ParameterValidationError("strategy_id must be a non-empty string")
        if not 1 <= self.top_n <= _MAX_TOP_N:
            raise ParameterValidationError(
                f"top_n must be in [1, {_MAX_TOP_N}] (got {self.top_n})"
            )
        if not 0.0 < self.max_position_weight <= 1.0:
            raise ParameterValidationError("max_position_weight must be in (0, 1]")
        if self.ma_long <= 1:
            raise ParameterValidationError("ma_long must be > 1")
        if not self.defensive_asset:
            raise ParameterValidationError("defensive_asset must be non-empty")
        if self.rebalance_frequency not in {"monthly", "quarterly"}:
            raise ParameterValidationError(
                "rebalance_frequency must be 'monthly' or 'quarterly'"
            )

    def parameter_hash(self) -> str:
        """Deterministic 64-char SHA-256 of the canonical JSON payload."""

        payload = {
            "defensive_asset": self.defensive_asset,
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


__all__ = ["HkChinaRealParameters", "MomentumWeights", "ParameterValidationError"]
