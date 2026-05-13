"""Risk Parity / Volatility Target strategy configuration boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from math import sqrt

from trade.data.loader import PriceBar


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


class RiskParityDataError(ValueError):
    """Raised when return or volatility estimation cannot use supplied data."""


@dataclass(frozen=True, slots=True)
class ReturnObservation:
    date: date
    symbol: str
    value: float


@dataclass(frozen=True, slots=True)
class VolatilityEstimate:
    symbol: str
    lookback: int
    annualized_volatility: float
    observations: int
    end_date: date


@dataclass(frozen=True, slots=True)
class RiskParitySignal:
    signal_date: date
    target_weights: dict[str, float]
    risk_asset_weights: dict[str, float]
    excluded_symbols: tuple[str, ...]
    exposure_scale: float
    estimated_portfolio_volatility: float
    defensive_asset: str
    defensive_weight: float
    parameter_hash: str
    parameters: RiskParityParameters


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


def daily_returns(
    records: tuple[PriceBar, ...], symbol: str, end_date: date | None = None
) -> tuple[ReturnObservation, ...]:
    prices = _history_for_symbol(records, symbol, end_date)
    if len(prices) < 2:
        raise RiskParityDataError(f"not enough prices to compute returns for {symbol}")
    returns: list[ReturnObservation] = []
    for previous, current in zip(prices, prices[1:], strict=False):
        if previous.adjusted_close <= 0 or current.adjusted_close <= 0:
            raise RiskParityDataError(f"invalid adjusted_close for {symbol}")
        returns.append(
            ReturnObservation(
                date=current.date,
                symbol=symbol,
                value=current.adjusted_close / previous.adjusted_close - 1.0,
            )
        )
    return tuple(returns)


def estimate_annualized_volatility(
    records: tuple[PriceBar, ...], symbol: str, lookback: int, end_date: date | None = None
) -> VolatilityEstimate:
    if lookback not in (60, 120, 252):
        raise RiskParityDataError("lookback must be one of 60, 120, or 252")
    returns = daily_returns(records, symbol, end_date)
    if len(returns) < lookback:
        raise RiskParityDataError(
            f"insufficient returns for {symbol}: need {lookback}, got {len(returns)}"
        )
    window = returns[-lookback:]
    mean = sum(item.value for item in window) / lookback
    variance = sum((item.value - mean) ** 2 for item in window) / (lookback - 1)
    volatility = sqrt(variance) * sqrt(252.0)
    if volatility <= 0:
        raise RiskParityDataError(f"invalid volatility for {symbol}")
    return VolatilityEstimate(
        symbol=symbol,
        lookback=lookback,
        annualized_volatility=volatility,
        observations=lookback,
        end_date=window[-1].date,
    )


def estimate_universe_volatility(
    records: tuple[PriceBar, ...], parameters: RiskParityParameters, end_date: date | None = None
) -> tuple[VolatilityEstimate, ...]:
    validate_risk_parity_parameters(parameters)
    return tuple(
        estimate_annualized_volatility(records, symbol, parameters.volatility_lookback, end_date)
        for symbol in parameters.universe
    )


def generate_risk_parity_signal(
    records: tuple[PriceBar, ...],
    parameters: RiskParityParameters | None = None,
    signal_date: date | None = None,
) -> RiskParitySignal:
    if parameters is None:
        parameters = default_risk_parity_parameters()
    validate_risk_parity_parameters(parameters)
    estimates: list[VolatilityEstimate] = []
    excluded: list[str] = []
    for symbol in parameters.universe:
        if symbol == parameters.defensive_asset:
            continue
        try:
            estimates.append(
                estimate_annualized_volatility(
                    records, symbol, parameters.volatility_lookback, signal_date
                )
            )
        except RiskParityDataError:
            excluded.append(symbol)
    if not estimates:
        raise RiskParityDataError("no valid volatility estimates for risk assets")

    base_weights = _inverse_volatility_weights(estimates)
    capped_weights = _cap_and_normalize_weights(base_weights, parameters.max_asset_weight)
    estimated_portfolio_volatility = _weighted_average_volatility(capped_weights, estimates)
    exposure_scale = min(parameters.target_volatility / estimated_portfolio_volatility, 1.0)
    risk_asset_weights = {
        symbol: weight * exposure_scale for symbol, weight in capped_weights.items()
    }
    defensive_weight = 1.0 - sum(risk_asset_weights.values())
    target_weights = dict(risk_asset_weights)
    target_weights[parameters.defensive_asset] = target_weights.get(
        parameters.defensive_asset, 0.0
    ) + defensive_weight
    effective_signal_date = signal_date or max(estimate.end_date for estimate in estimates)
    return RiskParitySignal(
        signal_date=effective_signal_date,
        target_weights=_round_weights(target_weights),
        risk_asset_weights=_round_weights(risk_asset_weights),
        excluded_symbols=tuple(sorted(excluded)),
        exposure_scale=exposure_scale,
        estimated_portfolio_volatility=estimated_portfolio_volatility,
        defensive_asset=parameters.defensive_asset,
        defensive_weight=defensive_weight,
        parameter_hash=parameters.parameter_hash(),
        parameters=parameters,
    )


def _inverse_volatility_weights(
    estimates: tuple[VolatilityEstimate, ...] | list[VolatilityEstimate],
) -> dict[str, float]:
    valid = tuple(estimate for estimate in estimates if estimate.annualized_volatility > 0)
    if not valid:
        raise RiskParityDataError("no valid positive volatility estimates")
    raw = {estimate.symbol: 1.0 / estimate.annualized_volatility for estimate in valid}
    raw_sum = sum(raw.values())
    return {symbol: value / raw_sum for symbol, value in raw.items()}


def _cap_and_normalize_weights(weights: dict[str, float], max_weight: float) -> dict[str, float]:
    if max_weight >= 1.0:
        return _normalize(weights)
    capped: dict[str, float] = {}
    uncapped = dict(weights)
    remaining_weight = 1.0
    while uncapped:
        normalized = _normalize(uncapped)
        breaches = {
            symbol: weight
            for symbol, weight in normalized.items()
            if weight * remaining_weight > max_weight
        }
        if not breaches:
            capped.update(
                {symbol: weight * remaining_weight for symbol, weight in normalized.items()}
            )
            return _normalize(capped)
        for symbol in breaches:
            capped[symbol] = max_weight
            uncapped.pop(symbol)
            remaining_weight -= max_weight
        if remaining_weight <= 0:
            return _normalize(capped)
    return _normalize(capped)


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise RiskParityDataError("weights must sum to a positive value")
    return {symbol: weight / total for symbol, weight in weights.items()}


def _weighted_average_volatility(
    weights: dict[str, float], estimates: tuple[VolatilityEstimate, ...] | list[VolatilityEstimate]
) -> float:
    by_symbol = {estimate.symbol: estimate.annualized_volatility for estimate in estimates}
    volatility = sum(weights[symbol] * by_symbol[symbol] for symbol in weights)
    if volatility <= 0:
        raise RiskParityDataError("estimated portfolio volatility must be positive")
    return volatility


def _round_weights(weights: dict[str, float]) -> dict[str, float]:
    return {symbol: round(weight, 10) for symbol, weight in sorted(weights.items())}


def _history_for_symbol(
    records: tuple[PriceBar, ...], symbol: str, end_date: date | None
) -> tuple[PriceBar, ...]:
    prices = tuple(
        sorted(
            (
                record
                for record in records
                if record.symbol == symbol and (end_date is None or record.date <= end_date)
            ),
            key=lambda item: item.date,
        )
    )
    if not prices:
        raise RiskParityDataError(f"missing price history for {symbol}")
    return prices
