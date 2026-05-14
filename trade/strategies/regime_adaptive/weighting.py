"""L2 inverse-volatility weighting for the regime-adaptive strategy.

Reuses the B010 risk-parity weight engine to produce inverse-volatility weights for the
assets that survived L1 gating. Capital from gated assets and residual exposure after
target-volatility scaling routes to the defensive sleeve. The artifact is research-only
and never authorizes any paper or production order flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    RegimeAdaptiveConfig,
)
from trade.strategies.regime_adaptive.trend_gating import TrendGatingResult
from trade.strategies.risk_parity import (
    RiskParityDataError,
    RiskParityParameters,
    generate_risk_parity_signal,
)


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveWeightAllocation:
    target_weights: dict[str, float]
    risk_asset_weights: dict[str, float]
    exposure_scale: float
    estimated_portfolio_volatility: float
    passing_symbols: tuple[str, ...]
    gated_symbols: tuple[str, ...]
    defensive_routed_weight: float


def derive_regime_adaptive_weights(
    records: tuple[PriceBar, ...],
    config: RegimeAdaptiveConfig,
    signal_date: date,
    gating_result: TrendGatingResult,
) -> RegimeAdaptiveWeightAllocation:
    defensive_symbol = config.defensive_symbol
    risk_universe = tuple(
        entry.symbol for entry in config.universe if entry.category != ASSET_CATEGORY_DEFENSIVE
    )
    passing_risk_assets = tuple(
        symbol for symbol in risk_universe if gating_result.mask.get(symbol)
    )
    gated_symbols = tuple(
        symbol for symbol in risk_universe if not gating_result.mask.get(symbol)
    )

    if not passing_risk_assets:
        return RegimeAdaptiveWeightAllocation(
            target_weights={defensive_symbol: 1.0},
            risk_asset_weights={},
            exposure_scale=0.0,
            estimated_portfolio_volatility=0.0,
            passing_symbols=(),
            gated_symbols=tuple(sorted(gated_symbols)),
            defensive_routed_weight=1.0,
        )

    rp_universe = (*passing_risk_assets, defensive_symbol)
    rp_parameters = RiskParityParameters(
        universe=rp_universe,
        volatility_lookback=config.vol_lookback_days,
        defensive_asset=defensive_symbol,
        target_volatility=config.target_volatility,
        max_exposure=config.max_exposure,
    )
    try:
        signal = generate_risk_parity_signal(records, rp_parameters, signal_date)
    except RiskParityDataError as exc:
        raise ValueError(
            f"L2 risk-parity weighting failed for passing assets {passing_risk_assets!r}: {exc}"
        ) from exc

    keep_ratio = len(passing_risk_assets) / len(risk_universe)
    base_defensive_weight = signal.target_weights.get(defensive_symbol, 0.0)
    target_weights: dict[str, float] = {entry.symbol: 0.0 for entry in config.universe}
    for symbol in passing_risk_assets:
        target_weights[symbol] = signal.target_weights.get(symbol, 0.0) * keep_ratio
    target_weights[defensive_symbol] = base_defensive_weight + (1.0 - keep_ratio) * (
        1.0 - base_defensive_weight
    )
    risk_asset_weights = {
        symbol: signal.risk_asset_weights.get(symbol, 0.0) * keep_ratio
        for symbol in passing_risk_assets
    }
    return RegimeAdaptiveWeightAllocation(
        target_weights=target_weights,
        risk_asset_weights=risk_asset_weights,
        exposure_scale=signal.exposure_scale * keep_ratio,
        estimated_portfolio_volatility=signal.estimated_portfolio_volatility,
        passing_symbols=tuple(sorted(passing_risk_assets)),
        gated_symbols=tuple(sorted(gated_symbols)),
        defensive_routed_weight=target_weights[defensive_symbol],
    )
