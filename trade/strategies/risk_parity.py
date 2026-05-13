"""Risk Parity / Volatility Target strategy configuration boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskParityParameters:
    """Minimal research-only inverse volatility risk parity parameters."""

    strategy_id: str = "risk_parity_vol_target"
    universe: tuple[str, ...] = ("SPY", "VEA", "AGG", "GLD", "SGOV")
    volatility_lookback: int = 120
    supported_lookbacks: tuple[int, ...] = (60, 120, 252)
    target_volatility: float = 0.08
    defensive_asset: str = "SGOV"
    rebalance_frequency: str = "monthly"
    weighting_method: str = "inverse_volatility"
    max_exposure: float = 1.0
    max_asset_weight: float = 0.35
    cash_allocation_label: str = "defensive_asset_or_cash_placeholder"

    def parameter_hash(self) -> str:
        payload = {
            "cash_allocation_label": self.cash_allocation_label,
            "defensive_asset": self.defensive_asset,
            "max_asset_weight": self.max_asset_weight,
            "max_exposure": self.max_exposure,
            "rebalance_frequency": self.rebalance_frequency,
            "strategy_id": self.strategy_id,
            "supported_lookbacks": list(self.supported_lookbacks),
            "target_volatility": self.target_volatility,
            "universe": list(self.universe),
            "volatility_lookback": self.volatility_lookback,
            "weighting_method": self.weighting_method,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class RiskParityConfigError(ValueError):
    """Raised when risk parity parameters violate the B010 research boundary."""


def validate_risk_parity_parameters(parameters: RiskParityParameters) -> None:
    if parameters.strategy_id != "risk_parity_vol_target":
        raise RiskParityConfigError("strategy_id must be risk_parity_vol_target")
    if parameters.weighting_method != "inverse_volatility":
        raise RiskParityConfigError("B010 supports inverse_volatility weighting only")
    if parameters.max_exposure > 1.0:
        raise RiskParityConfigError("leverage is not allowed; max_exposure must be <= 1.0")
    if parameters.max_exposure <= 0:
        raise RiskParityConfigError("max_exposure must be positive")
    if parameters.volatility_lookback not in parameters.supported_lookbacks:
        raise RiskParityConfigError("volatility_lookback must be one of 60, 120, or 252")
    if not parameters.universe:
        raise RiskParityConfigError("universe must not be empty")
    if parameters.defensive_asset not in parameters.universe:
        raise RiskParityConfigError("defensive_asset must be included in universe")
    if parameters.target_volatility <= 0:
        raise RiskParityConfigError("target_volatility must be positive")
    if parameters.max_asset_weight <= 0 or parameters.max_asset_weight > 1.0:
        raise RiskParityConfigError("max_asset_weight must be in (0, 1]")
    if parameters.rebalance_frequency != "monthly":
        raise RiskParityConfigError("B010 supports monthly rebalancing only")


def default_risk_parity_parameters() -> RiskParityParameters:
    parameters = RiskParityParameters()
    validate_risk_parity_parameters(parameters)
    return parameters
