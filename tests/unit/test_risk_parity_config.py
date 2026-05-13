import pytest

from trade.strategies.risk_parity import (
    RiskParityConfigError,
    RiskParityParameters,
    default_risk_parity_parameters,
    validate_risk_parity_parameters,
)


def test_default_risk_parity_parameters_define_research_boundary() -> None:
    parameters = default_risk_parity_parameters()

    assert parameters.strategy_id == "risk_parity_vol_target"
    assert parameters.weighting_method == "inverse_volatility"
    assert parameters.supported_lookbacks == (60, 120, 252)
    assert parameters.volatility_lookback == 120
    assert parameters.target_volatility == 0.08
    assert parameters.max_exposure == 1.0
    assert parameters.defensive_asset == "SGOV"
    assert parameters.defensive_asset in parameters.universe
    assert parameters.cash_allocation_label == "defensive_asset_or_cash_placeholder"
    assert len(parameters.parameter_hash()) == 64


def test_risk_parity_rejects_non_inverse_vol_weighting() -> None:
    with pytest.raises(RiskParityConfigError, match="inverse_volatility"):
        validate_risk_parity_parameters(
            RiskParityParameters(weighting_method="equal_risk_contribution")
        )


def test_risk_parity_rejects_leverage() -> None:
    with pytest.raises(RiskParityConfigError, match="leverage"):
        validate_risk_parity_parameters(RiskParityParameters(max_exposure=1.25))


def test_risk_parity_requires_defensive_asset_in_universe() -> None:
    with pytest.raises(RiskParityConfigError, match="defensive_asset"):
        validate_risk_parity_parameters(
            RiskParityParameters(universe=("SPY", "VEA", "AGG"), defensive_asset="SGOV")
        )


def test_risk_parity_supports_only_declared_lookbacks() -> None:
    with pytest.raises(RiskParityConfigError, match="60, 120, or 252"):
        validate_risk_parity_parameters(RiskParityParameters(volatility_lookback=90))
