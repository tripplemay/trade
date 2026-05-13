from datetime import date, timedelta

import pytest

from trade.data.loader import PriceBar
from trade.strategies.risk_parity import (
    RiskParityConfigError,
    RiskParityDataError,
    RiskParityParameters,
    daily_returns,
    default_risk_parity_parameters,
    estimate_annualized_volatility,
    estimate_universe_volatility,
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


def test_daily_returns_use_adjusted_close() -> None:
    records = _price_history("SPY", 3)

    returns = daily_returns(records, "SPY")

    assert len(returns) == 2
    assert returns[0].date == date(2024, 1, 2)
    assert round(returns[0].value, 6) == round(101.0 / 100.0 - 1.0, 6)


@pytest.mark.parametrize("lookback", [60, 120, 252])
def test_annualized_volatility_supports_required_lookbacks(lookback: int) -> None:
    records = _oscillating_price_history("SPY", lookback + 1)

    estimate = estimate_annualized_volatility(records, "SPY", lookback)

    assert estimate.symbol == "SPY"
    assert estimate.lookback == lookback
    assert estimate.observations == lookback
    assert estimate.annualized_volatility > 0


def test_annualized_volatility_fails_on_insufficient_data() -> None:
    records = _price_history("SPY", 60)

    with pytest.raises(RiskParityDataError, match="insufficient returns"):
        estimate_annualized_volatility(records, "SPY", 60)


def test_returns_fail_on_invalid_adjusted_close() -> None:
    records = (
        PriceBar(date(2024, 1, 1), "SPY", 100.0, 100.0, 100.0, 1000),
        PriceBar(date(2024, 1, 2), "SPY", 101.0, 101.0, 0.0, 1000),
    )

    with pytest.raises(RiskParityDataError, match="invalid adjusted_close"):
        daily_returns(records, "SPY")


def test_universe_volatility_uses_parameter_lookback_and_universe() -> None:
    parameters = RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
    )
    records = (
        _oscillating_price_history("SPY", 61)
        + _oscillating_price_history("AGG", 61)
        + _oscillating_price_history("SGOV", 61)
    )

    estimates = estimate_universe_volatility(records, parameters)

    assert tuple(estimate.symbol for estimate in estimates) == ("SPY", "AGG", "SGOV")
    assert all(estimate.lookback == 60 for estimate in estimates)


def _price_history(symbol: str, observations: int) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    return tuple(
        PriceBar(
            date=start + timedelta(days=index),
            symbol=symbol,
            open=100.0 + index,
            close=100.0 + index,
            adjusted_close=100.0 + index,
            volume=1000,
        )
        for index in range(observations)
    )


def _oscillating_price_history(symbol: str, observations: int) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    price = 100.0
    records: list[PriceBar] = []
    for index in range(observations):
        if index:
            price *= 1.01 if index % 2 else 0.99
        records.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol=symbol,
                open=price,
                close=price,
                adjusted_close=price,
                volume=1000,
            )
        )
    return tuple(records)
