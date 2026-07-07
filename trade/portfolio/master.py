"""Master Portfolio Allocation configuration boundary."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt

from trade.strategies.risk_parity import (
    VolatilityEstimate,
    _inverse_volatility_weights,
)
from trade.strategies.risk_parity_hrp import compute_hrp_weights

SLEEVE_TYPE_IMPLEMENTED = "implemented_strategy"
SLEEVE_TYPE_SATELLITE_STUB = "satellite_stub"
VALID_SLEEVE_TYPES: frozenset[str] = frozenset(
    {SLEEVE_TYPE_IMPLEMENTED, SLEEVE_TYPE_SATELLITE_STUB}
)

PLANNING_WEIGHT_SUM_TOLERANCE = 1e-8

REGIME_ADAPTIVE_SLEEVE_ID = "regime_adaptive"
REGIME_ADAPTIVE_STRATEGY_ID = "regime_adaptive_multi_asset"

# B106 F001 — sleeve-layer weight schemes. ``fixed`` is the production default and
# MUST stay a pure passthrough of planning_weight (byte-identical Master). The two
# risk-aware schemes are opt-in 对照 that reuse the existing strategy primitives.
WEIGHT_SCHEME_FIXED = "fixed"
WEIGHT_SCHEME_RISK_PARITY = "risk_parity"
WEIGHT_SCHEME_HRP = "hrp"
VALID_WEIGHT_SCHEMES: frozenset[str] = frozenset(
    {WEIGHT_SCHEME_FIXED, WEIGHT_SCHEME_RISK_PARITY, WEIGHT_SCHEME_HRP}
)

# Annualisation scalar mirrored from
# ``trade.strategies.risk_parity.estimate_annualized_volatility``. It is a common
# multiplier across every sleeve, so it cancels inside the inverse-volatility (and
# HRP) weight ratios; applied only to keep the reused VolatilityEstimate honest.
_TRADING_DAYS_PER_YEAR = 252.0

# Placeholder date carried by sleeve-level VolatilityEstimate objects. The reused
# ``_inverse_volatility_weights`` primitive only reads ``.symbol`` and
# ``.annualized_volatility``; ``end_date`` is structurally required but never read.
_UNUSED_ESTIMATE_DATE = date(1970, 1, 1)

# B106 F001 — cn_dividend_lowvol (红利低波) defensive sleeve: the B082-validated
# 削回撤 leg, negatively correlated with the momentum family in A股. strategy_id
# mirrors ``trade.strategies.cn_dividend_lowvol.parameters.DEFAULT_STRATEGY_ID``,
# kept as a literal here to match how every other sleeve records its strategy_id.
CN_DIVIDEND_LOWVOL_SLEEVE_ID = "cn_dividend_lowvol"
CN_DIVIDEND_LOWVOL_STRATEGY_ID = "cn_dividend_lowvol"
DEFENSIVE_SLEEVE_ROLE_LABEL = "defensive_sleeve"
DEFENSIVE_SLEEVE_DEFAULT_WEIGHT = 0.20


@dataclass(frozen=True, slots=True)
class MasterSleeveConfig:
    """Single child sleeve under the Master Portfolio.

    A sleeve is either an implemented child strategy (with a `strategy_id` reference) or a
    reserved satellite interface stub whose weight falls through to the defensive placeholder.
    """

    sleeve_id: str
    sleeve_type: str
    strategy_id: str | None
    planning_weight: float
    role_label: str


_DEFAULT_SLEEVES: tuple[MasterSleeveConfig, ...] = (
    MasterSleeveConfig(
        sleeve_id="momentum",
        sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
        strategy_id="global_etf_momentum",
        planning_weight=0.40,
        role_label="core_trend_engine",
    ),
    MasterSleeveConfig(
        sleeve_id="risk_parity",
        sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
        strategy_id="risk_parity_vol_target",
        planning_weight=0.30,
        role_label="core_stabilizer",
    ),
    MasterSleeveConfig(
        sleeve_id="satellite_us_quality",
        sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
        strategy_id="us_quality_momentum",
        planning_weight=0.20,
        role_label="satellite_alpha",
    ),
    # BL-B011-S2: the HK-China satellite is now an implemented strategy
    # (was a reserved SATELLITE_STUB). planning_weight is unchanged (0.10);
    # only the type + strategy_id flip, so the Master is 4/4 real.
    MasterSleeveConfig(
        sleeve_id="satellite_hk_china",
        sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
        strategy_id="hk_china_momentum",
        planning_weight=0.10,
        role_label="satellite_regional",
    ),
)


@dataclass(frozen=True, slots=True)
class MasterPortfolioParameters:
    """Research-only Master Portfolio configuration boundary."""

    portfolio_id: str = "master_portfolio_mvp"
    sleeves: tuple[MasterSleeveConfig, ...] = _DEFAULT_SLEEVES
    defensive_asset: str = "SGOV"
    rebalance_frequency: str = "quarterly"
    drawdown_threshold: float = 0.15
    max_exposure: float = 1.0
    kill_switch_clearance_parameter: str = "kill_switch_clearance"
    human_review_required_on_trigger: bool = True
    weight_scheme: str = WEIGHT_SCHEME_FIXED

    def parameter_hash(self) -> str:
        payload = {
            "defensive_asset": self.defensive_asset,
            "drawdown_threshold": self.drawdown_threshold,
            "human_review_required_on_trigger": self.human_review_required_on_trigger,
            "kill_switch_clearance_parameter": self.kill_switch_clearance_parameter,
            "max_exposure": self.max_exposure,
            "portfolio_id": self.portfolio_id,
            "rebalance_frequency": self.rebalance_frequency,
            "sleeves": [
                {
                    "planning_weight": sleeve.planning_weight,
                    "role_label": sleeve.role_label,
                    "sleeve_id": sleeve.sleeve_id,
                    "sleeve_type": sleeve.sleeve_type,
                    "strategy_id": sleeve.strategy_id,
                }
                for sleeve in self.sleeves
            ],
        }
        # ★ Byte-identical backward-compat: the default ``fixed`` scheme is OMITTED
        # from the hash payload, so a default (4-sleeve / fixed) Master reproduces
        # its pre-B106 parameter_hash exactly. Only opt-in non-fixed schemes are
        # recorded (they must hash differently to be distinguishable in registries).
        if self.weight_scheme != WEIGHT_SCHEME_FIXED:
            payload["weight_scheme"] = self.weight_scheme
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class MasterPortfolioConfigError(ValueError):
    """Raised when Master Portfolio parameters violate the B011 research boundary."""


def validate_master_portfolio_parameters(parameters: MasterPortfolioParameters) -> None:
    if parameters.max_exposure > 1.0:
        raise MasterPortfolioConfigError(
            "leverage is not allowed; max_exposure must be <= 1.0"
        )
    if parameters.max_exposure <= 0:
        raise MasterPortfolioConfigError("max_exposure must be positive")
    if parameters.rebalance_frequency != "quarterly":
        raise MasterPortfolioConfigError("B011 supports quarterly rebalancing only")
    if parameters.drawdown_threshold <= 0 or parameters.drawdown_threshold >= 1:
        raise MasterPortfolioConfigError("drawdown_threshold must be within (0, 1)")
    if parameters.weight_scheme not in VALID_WEIGHT_SCHEMES:
        raise MasterPortfolioConfigError(
            f"unknown weight_scheme: {parameters.weight_scheme!r}; "
            f"valid: {sorted(VALID_WEIGHT_SCHEMES)}"
        )
    if not parameters.sleeves:
        raise MasterPortfolioConfigError("sleeves must not be empty")

    seen_ids: set[str] = set()
    for sleeve in parameters.sleeves:
        if sleeve.sleeve_id in seen_ids:
            raise MasterPortfolioConfigError(
                f"duplicate sleeve_id: {sleeve.sleeve_id}"
            )
        seen_ids.add(sleeve.sleeve_id)
        if sleeve.sleeve_type not in VALID_SLEEVE_TYPES:
            raise MasterPortfolioConfigError(
                f"unknown sleeve_type: {sleeve.sleeve_type}"
            )
        if sleeve.planning_weight < 0:
            raise MasterPortfolioConfigError(
                f"planning_weight must be non-negative for {sleeve.sleeve_id}"
            )
        if sleeve.sleeve_type == SLEEVE_TYPE_IMPLEMENTED and not sleeve.strategy_id:
            raise MasterPortfolioConfigError(
                f"implemented sleeve {sleeve.sleeve_id} must declare a strategy_id"
            )
        if sleeve.sleeve_type == SLEEVE_TYPE_SATELLITE_STUB and sleeve.strategy_id is not None:
            raise MasterPortfolioConfigError(
                f"satellite_stub sleeve {sleeve.sleeve_id} must not declare a strategy_id"
            )

    total = sum(sleeve.planning_weight for sleeve in parameters.sleeves)
    if abs(total - 1.0) > PLANNING_WEIGHT_SUM_TOLERANCE:
        raise MasterPortfolioConfigError(
            f"sleeve planning_weight values must sum to 1.0 (got {total})"
        )


def default_master_portfolio_parameters() -> MasterPortfolioParameters:
    parameters = MasterPortfolioParameters()
    validate_master_portfolio_parameters(parameters)
    return parameters


_REGIME_ADAPTIVE_SLEEVE = MasterSleeveConfig(
    sleeve_id=REGIME_ADAPTIVE_SLEEVE_ID,
    sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
    strategy_id=REGIME_ADAPTIVE_STRATEGY_ID,
    planning_weight=0.0,
    role_label="regime_defensive_overlay",
)


def default_master_portfolio_parameters_with_regime_adaptive() -> MasterPortfolioParameters:
    """Return defaults augmented with the B013 regime-adaptive sleeve at planning_weight=0.0.

    The Master backtest path treats zero-weight implemented sleeves as loadable-but-
    uninvoked, so this helper preserves the B011 sum-to-1.0 planning weight invariant
    without changing any other sleeve. Existing B011 callers that import
    ``default_master_portfolio_parameters`` continue to receive the four-sleeve default.
    """

    parameters = MasterPortfolioParameters(
        sleeves=(*_DEFAULT_SLEEVES, _REGIME_ADAPTIVE_SLEEVE)
    )
    validate_master_portfolio_parameters(parameters)
    return parameters


def resolve_sleeve_weights(
    scheme: str,
    sleeves: Sequence[MasterSleeveConfig],
    returns: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, float]:
    """Resolve the per-sleeve allocation weights under a chosen weighting scheme.

    - ``fixed`` (default, byte-identical path): a pure passthrough of each sleeve's
      ``planning_weight`` — no return data required. This is the production Master
      behaviour and MUST stay a passthrough so the default config is unchanged.
    - ``risk_parity``: sleeve-layer generalisation of ``risk_parity_vol_target`` —
      inverse-volatility weights over each sleeve's daily-return series (reuses
      :func:`trade.strategies.risk_parity._inverse_volatility_weights`).
    - ``hrp``: Hierarchical Risk Parity over the same sleeve-return series (reuses
      :func:`trade.strategies.risk_parity_hrp.compute_hrp_weights`).

    ``returns`` maps ``sleeve_id -> daily-return series`` and is REQUIRED for the
    two non-fixed schemes (fail-loud when missing). The returned weights always sum
    to 1.0. Weights are keyed by ``sleeve_id`` in the order the sleeves are supplied.
    """

    if scheme not in VALID_WEIGHT_SCHEMES:
        raise MasterPortfolioConfigError(
            f"unknown weight_scheme: {scheme!r}; valid: {sorted(VALID_WEIGHT_SCHEMES)}"
        )
    if not sleeves:
        raise MasterPortfolioConfigError("sleeves must not be empty")

    sleeve_ids = [sleeve.sleeve_id for sleeve in sleeves]
    if len(set(sleeve_ids)) != len(sleeve_ids):
        raise MasterPortfolioConfigError("duplicate sleeve_id in sleeves")

    if scheme == WEIGHT_SCHEME_FIXED:
        # Passthrough: identical to the pre-B106 fixed planning weights.
        return {sleeve.sleeve_id: sleeve.planning_weight for sleeve in sleeves}

    if returns is None:
        raise MasterPortfolioConfigError(
            f"weight_scheme {scheme!r} requires a per-sleeve return series"
        )
    series = _ordered_sleeve_returns(sleeve_ids, returns)

    if scheme == WEIGHT_SCHEME_RISK_PARITY:
        weights = _risk_parity_sleeve_weights(sleeve_ids, series)
    else:  # WEIGHT_SCHEME_HRP
        weights = _hrp_sleeve_weights(sleeve_ids, series)
    return _normalize_resolved_weights(weights)


def _ordered_sleeve_returns(
    sleeve_ids: Sequence[str], returns: Mapping[str, Sequence[float]]
) -> list[tuple[float, ...]]:
    series: list[tuple[float, ...]] = []
    for sleeve_id in sleeve_ids:
        if sleeve_id not in returns:
            raise MasterPortfolioConfigError(
                f"missing return series for sleeve {sleeve_id!r}"
            )
        values = tuple(returns[sleeve_id])
        if len(values) < 2:
            raise MasterPortfolioConfigError(
                f"sleeve {sleeve_id!r} needs >= 2 return observations; got {len(values)}"
            )
        series.append(values)
    return series


def _risk_parity_sleeve_weights(
    sleeve_ids: Sequence[str], series: Sequence[tuple[float, ...]]
) -> dict[str, float]:
    """Inverse-volatility sleeve weights, reusing the risk_parity primitive."""

    estimates = [
        VolatilityEstimate(
            symbol=sleeve_id,
            lookback=len(values),
            annualized_volatility=statistics.stdev(values) * sqrt(_TRADING_DAYS_PER_YEAR),
            observations=len(values),
            end_date=_UNUSED_ESTIMATE_DATE,
        )
        for sleeve_id, values in zip(sleeve_ids, series, strict=True)
    ]
    # Fail loud on a flat sleeve: ``_inverse_volatility_weights`` would otherwise
    # silently drop a zero-vol sleeve and renormalise over the remainder.
    for estimate in estimates:
        if estimate.annualized_volatility <= 0:
            raise MasterPortfolioConfigError(
                f"sleeve {estimate.symbol!r} has non-positive volatility; cannot risk-weight"
            )
    return _inverse_volatility_weights(estimates)


def _hrp_sleeve_weights(
    sleeve_ids: Sequence[str], series: Sequence[tuple[float, ...]]
) -> dict[str, float]:
    """Hierarchical Risk Parity sleeve weights, reusing the HRP primitive."""

    try:
        return compute_hrp_weights(list(series), list(sleeve_ids))
    except ValueError as exc:
        raise MasterPortfolioConfigError(f"HRP sleeve weighting failed: {exc}") from exc


def _normalize_resolved_weights(weights: Mapping[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise MasterPortfolioConfigError(
            "resolved sleeve weights must sum to a positive value"
        )
    return {sleeve_id: weight / total for sleeve_id, weight in weights.items()}


def _defensive_barbell_sleeve(planning_weight: float) -> MasterSleeveConfig:
    return MasterSleeveConfig(
        sleeve_id=CN_DIVIDEND_LOWVOL_SLEEVE_ID,
        sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
        strategy_id=CN_DIVIDEND_LOWVOL_STRATEGY_ID,
        planning_weight=planning_weight,
        role_label=DEFENSIVE_SLEEVE_ROLE_LABEL,
    )


def master_portfolio_parameters_with_defensive_barbell(
    defensive_weight: float = DEFENSIVE_SLEEVE_DEFAULT_WEIGHT,
    weight_scheme: str = WEIGHT_SCHEME_FIXED,
) -> MasterPortfolioParameters:
    """Opt-in '进攻(动量族) + 防守(红利低波)' barbell — NOT the production default.

    The four production attack sleeves are scaled by ``(1 - defensive_weight)`` and
    the cn_dividend_lowvol defensive sleeve is appended at ``defensive_weight``, so
    planning weights still sum to 1.0 while the attack sleeves keep their relative
    proportions (40/30/20/10). ``weight_scheme`` selects how the ACTUAL allocation is
    derived at run time via :func:`resolve_sleeve_weights`; the planning weights are
    the fixed-scheme baseline (and the value validated to sum to 1.0).

    ★ Backward-compat: this is a SEPARATE constructor. The production default
    (:func:`default_master_portfolio_parameters` — 4 sleeves / fixed / byte-identical
    hash) is untouched. This barbell is the research / F002 AB opt-in 对照 only; no
    production paper path wires it in.
    """

    if not 0.0 < defensive_weight < 1.0:
        raise MasterPortfolioConfigError(
            f"defensive_weight must be within (0, 1); got {defensive_weight}"
        )
    attack_scale = 1.0 - defensive_weight
    attack_sleeves = tuple(
        MasterSleeveConfig(
            sleeve_id=sleeve.sleeve_id,
            sleeve_type=sleeve.sleeve_type,
            strategy_id=sleeve.strategy_id,
            planning_weight=round(sleeve.planning_weight * attack_scale, 10),
            role_label=sleeve.role_label,
        )
        for sleeve in _DEFAULT_SLEEVES
    )
    parameters = MasterPortfolioParameters(
        sleeves=(*attack_sleeves, _defensive_barbell_sleeve(round(defensive_weight, 10))),
        weight_scheme=weight_scheme,
    )
    validate_master_portfolio_parameters(parameters)
    return parameters
