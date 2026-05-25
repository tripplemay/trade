"""Master Portfolio Allocation configuration boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

SLEEVE_TYPE_IMPLEMENTED = "implemented_strategy"
SLEEVE_TYPE_SATELLITE_STUB = "satellite_stub"
VALID_SLEEVE_TYPES: frozenset[str] = frozenset(
    {SLEEVE_TYPE_IMPLEMENTED, SLEEVE_TYPE_SATELLITE_STUB}
)

PLANNING_WEIGHT_SUM_TOLERANCE = 1e-8

REGIME_ADAPTIVE_SLEEVE_ID = "regime_adaptive"
REGIME_ADAPTIVE_STRATEGY_ID = "regime_adaptive_multi_asset"


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
    MasterSleeveConfig(
        sleeve_id="satellite_hk_china",
        sleeve_type=SLEEVE_TYPE_SATELLITE_STUB,
        strategy_id=None,
        planning_weight=0.10,
        role_label="satellite_regional_stub",
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
