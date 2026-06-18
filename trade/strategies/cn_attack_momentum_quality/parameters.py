"""B066 F001 — frozen parameters for the A-share attack momentum+quality engine.

Mirrors :class:`trade.strategies.us_quality_momentum.parameters.UsQualityMomentumParameters`
(single frozen dataclass + deterministic ``parameter_hash``) but is A-share /
attack specific:

- a **factor variant** selector (``quality_momentum`` vs ``pure_momentum``) instead
  of the US 5-factor blend — the spec's A/B test of whether quality adds value;
- ``max_position_weight`` defaults to 8% (the spec's single-name cap) and
  ``top_n`` to 25 (the spec's "top 20-30 equal weight");
- **no** sector / earnings fields — A-shares have neither a GICS sector map nor an
  earnings calendar in this pipeline (degraded by design, spec §3).

F002 will extend this bundle (additively, it is frozen) with the no-trade-band
threshold, the exit-variant selector, and the directional cost fields.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

DEFAULT_STRATEGY_ID = "cn_attack_momentum_quality"
DEFAULT_TOP_N = 25
DEFAULT_MAX_POSITION_WEIGHT = 0.08
DEFAULT_MOMENTUM_WEIGHT = 0.5
DEFAULT_QUALITY_WEIGHT = 0.5
DEFAULT_REBALANCE_FREQUENCY = "monthly"

# Factor variants (the spec's A/B test).
FACTOR_VARIANT_QUALITY_MOMENTUM = "quality_momentum"
FACTOR_VARIANT_PURE_MOMENTUM = "pure_momentum"
FACTOR_VARIANTS: frozenset[str] = frozenset(
    {FACTOR_VARIANT_QUALITY_MOMENTUM, FACTOR_VARIANT_PURE_MOMENTUM}
)

# B068 F002 — weighting schemes (the spec's second A/B dimension). ``equal`` is the
# B066/B067 default (1/N capital); ``inverse_vol`` sizes each name ∝ 1/σ_i
# (risk-managed-momentum weighting, Barroso-Santa-Clara / Daniel-Moskowitz). The
# analyst decision (spec §2) excludes momentum/score-weighting and MVO; inverse_vol
# is the ONLY weighting optimisation tested (risk control, not return prediction →
# low overfit). ``equal`` stays the default so B066/B067 are zero-regression.
WEIGHTING_SCHEME_EQUAL = "equal"
WEIGHTING_SCHEME_INVERSE_VOL = "inverse_vol"
WEIGHTING_SCHEMES: frozenset[str] = frozenset(
    {WEIGHTING_SCHEME_EQUAL, WEIGHTING_SCHEME_INVERSE_VOL}
)
DEFAULT_WEIGHTING_SCHEME = WEIGHTING_SCHEME_EQUAL

REBALANCE_FREQUENCIES: frozenset[str] = frozenset({"daily", "weekly", "monthly", "quarterly"})

WEIGHT_SUM_TOLERANCE = 1e-8


class CnAttackParameterError(ValueError):
    """Raised when an immutable CN attack parameter bundle violates an invariant."""


@dataclass(frozen=True, slots=True)
class CnAttackParameters:
    """Strategy parameters recorded with every CN attack signal artifact.

    ``factor_variant`` drives which factors are scored:

    - ``quality_momentum`` → composite of ``momentum_weight`` * momentum +
      ``quality_weight`` * quality (the two must sum to 1.0); tickers without CAS
      fundamentals drop out (the soft quality filter);
    - ``pure_momentum`` → momentum only (weight 1.0); ``momentum_weight`` /
      ``quality_weight`` are ignored, and fundamentals are not required.
    """

    strategy_id: str = DEFAULT_STRATEGY_ID
    factor_variant: str = FACTOR_VARIANT_QUALITY_MOMENTUM
    top_n: int = DEFAULT_TOP_N
    momentum_weight: float = DEFAULT_MOMENTUM_WEIGHT
    quality_weight: float = DEFAULT_QUALITY_WEIGHT
    max_position_weight: float = DEFAULT_MAX_POSITION_WEIGHT
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY
    weighting_scheme: str = DEFAULT_WEIGHTING_SCHEME

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise CnAttackParameterError("strategy_id must be a non-empty string")
        if self.factor_variant not in FACTOR_VARIANTS:
            raise CnAttackParameterError(
                f"factor_variant must be one of {sorted(FACTOR_VARIANTS)}; "
                f"got {self.factor_variant!r}"
            )
        if self.top_n <= 0:
            raise CnAttackParameterError("top_n must be > 0")
        if self.momentum_weight < 0 or self.quality_weight < 0:
            raise CnAttackParameterError("factor weights must be >= 0")
        if not 0.0 < self.max_position_weight <= 1.0:
            raise CnAttackParameterError("max_position_weight must be in (0, 1]")
        if self.rebalance_frequency not in REBALANCE_FREQUENCIES:
            raise CnAttackParameterError(
                f"rebalance_frequency must be one of {sorted(REBALANCE_FREQUENCIES)}"
            )
        if self.weighting_scheme not in WEIGHTING_SCHEMES:
            raise CnAttackParameterError(
                f"weighting_scheme must be one of {sorted(WEIGHTING_SCHEMES)}; "
                f"got {self.weighting_scheme!r}"
            )
        # The blend weights only have to sum to 1.0 for the quality_momentum
        # variant; pure_momentum ignores them (the mapping forces momentum=1.0).
        if self.factor_variant == FACTOR_VARIANT_QUALITY_MOMENTUM:
            total = self.momentum_weight + self.quality_weight
            if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
                raise CnAttackParameterError(
                    f"quality_momentum weights must sum to 1.0 (got {total:.10f})"
                )
        # Top N * max position weight must reach 1.0 so that full investment is
        # *reachable* when top_n names have factor data (25 * 8% = 2.0, ample).
        # A thin cross-section (fewer scored names than top_n) still legitimately
        # leaves cash — that is honest under-population, not a misconfiguration.
        if self.top_n * self.max_position_weight < 1.0:
            raise CnAttackParameterError(
                "top_n * max_position_weight must be >= 1.0 (cap is unreachable)"
            )

    def factor_weight_mapping(self) -> dict[str, float]:
        """Active factor → weight map driving the composite score.

        ``pure_momentum`` collapses to ``{"momentum": 1.0}`` so no quality series
        is required and names without fundamentals stay eligible; the
        ``quality_momentum`` blend includes quality so they are filtered out.
        """

        if self.factor_variant == FACTOR_VARIANT_PURE_MOMENTUM:
            return {"momentum": 1.0}
        return {"momentum": self.momentum_weight, "quality": self.quality_weight}

    def parameter_hash(self) -> str:
        """Deterministic 64-char SHA-256 of the canonical JSON payload.

        Mirrors the US engine's ``parameter_hash`` so backtest reports / tickets
        record a single immutable identifier per configuration.
        """

        payload = {
            "factor_variant": self.factor_variant,
            "max_position_weight": self.max_position_weight,
            "momentum_weight": self.momentum_weight,
            "quality_weight": self.quality_weight,
            "rebalance_frequency": self.rebalance_frequency,
            "strategy_id": self.strategy_id,
            "top_n": self.top_n,
        }
        # B068 F002 — only fold weighting_scheme into the payload when it differs
        # from the default, so the equal-weight (B066/B067) hash stays byte-identical
        # to the pre-B068 hash (zero-regression: the live advisory's recorded
        # identifier does not churn just because a new dimension was added).
        if self.weighting_scheme != DEFAULT_WEIGHTING_SCHEME:
            payload["weighting_scheme"] = self.weighting_scheme
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "DEFAULT_WEIGHTING_SCHEME",
    "FACTOR_VARIANTS",
    "FACTOR_VARIANT_PURE_MOMENTUM",
    "FACTOR_VARIANT_QUALITY_MOMENTUM",
    "WEIGHTING_SCHEMES",
    "WEIGHTING_SCHEME_EQUAL",
    "WEIGHTING_SCHEME_INVERSE_VOL",
    "CnAttackParameterError",
    "CnAttackParameters",
]
