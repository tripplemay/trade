from datetime import date, timedelta

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestError, BacktestParameters
from trade.data.loader import PriceBar
from trade.portfolio.master import (
    REGIME_ADAPTIVE_SLEEVE_ID,
    REGIME_ADAPTIVE_STRATEGY_ID,
    SLEEVE_TYPE_IMPLEMENTED,
    MasterPortfolioParameters,
    MasterSleeveConfig,
    default_master_portfolio_parameters,
    default_master_portfolio_parameters_with_regime_adaptive,
)
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow
from trade.strategies.risk_parity import RiskParityParameters


def _short_momentum_params() -> MomentumParameters:
    return MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )


def _short_risk_parity_params() -> RiskParityParameters:
    return RiskParityParameters(
        universe=("SPY", "VEA", "AGG", "GLD", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.5,
    )


def _synthetic_universe(length: int = 275) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    symbols = ("SPY", "VEA", "AGG", "GLD", "SGOV")
    rows: list[PriceBar] = []
    for index, symbol in enumerate(symbols):
        price = 100.0 + index * 10.0
        for offset in range(length):
            if offset:
                price *= 1.0 + (0.003 * (index + 1) if offset % 2 else -0.002)
            rows.append(
                PriceBar(
                    date=start + timedelta(days=offset),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1_000,
                )
            )
    return tuple(rows)


def test_default_master_portfolio_parameters_still_has_four_sleeves() -> None:
    """Existing B011 contract must remain unchanged for the legacy default."""

    parameters = default_master_portfolio_parameters()
    assert {sleeve.sleeve_id for sleeve in parameters.sleeves} == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }


def test_default_master_portfolio_parameters_with_regime_adaptive_has_five_sleeves() -> None:
    parameters = default_master_portfolio_parameters_with_regime_adaptive()
    sleeve_ids = [sleeve.sleeve_id for sleeve in parameters.sleeves]

    assert REGIME_ADAPTIVE_SLEEVE_ID in sleeve_ids
    assert len(sleeve_ids) == 5


def test_regime_adaptive_sleeve_default_planning_weight_is_zero() -> None:
    parameters = default_master_portfolio_parameters_with_regime_adaptive()
    sleeves_by_id = {sleeve.sleeve_id: sleeve for sleeve in parameters.sleeves}

    sleeve = sleeves_by_id[REGIME_ADAPTIVE_SLEEVE_ID]
    assert sleeve.sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert sleeve.strategy_id == REGIME_ADAPTIVE_STRATEGY_ID
    assert sleeve.planning_weight == 0.0


def test_default_master_portfolio_parameters_with_regime_adaptive_weights_sum_to_one() -> None:
    parameters = default_master_portfolio_parameters_with_regime_adaptive()
    total = sum(sleeve.planning_weight for sleeve in parameters.sleeves)

    assert round(total, 8) == 1.0


def test_master_backtest_short_circuits_zero_weight_implemented_sleeves() -> None:
    """A zero-weight implemented sleeve must not invoke the child backtest."""

    records = _synthetic_universe()
    parameters = default_master_portfolio_parameters_with_regime_adaptive()
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 31),),
        master_parameters=parameters,
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
    )

    period = result.rebalance_results[0]
    regime_sleeve = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == REGIME_ADAPTIVE_SLEEVE_ID
    )
    assert regime_sleeve.planning_weight == 0.0
    assert regime_sleeve.contribution_weights == {}


def test_master_backtest_rejects_implemented_sleeve_with_unknown_strategy_id() -> None:
    """Unknown strategy_id must fail closed regardless of planning_weight."""

    records = _synthetic_universe()
    custom = MasterPortfolioParameters(
        sleeves=(
            MasterSleeveConfig(
                sleeve_id="momentum",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="global_etf_momentum",
                planning_weight=0.5,
                role_label="core",
            ),
            MasterSleeveConfig(
                sleeve_id="exotic",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="unknown_strategy",
                planning_weight=0.5,
                role_label="core",
            ),
        ),
        defensive_asset="AGG",
    )
    with pytest.raises(BacktestError, match="strategy_id"):
        run_master_portfolio_quarterly_backtest(
            records,
            (date(2024, 3, 31),),
            master_parameters=custom,
            child_parameters=MasterChildStrategyParameters(momentum=_short_momentum_params()),
        )


def test_master_backtest_zero_weight_unknown_strategy_id_still_fails_closed() -> None:
    """Loadability check must reject unknown strategy_id even at planning_weight 0."""

    records = _synthetic_universe()
    custom = MasterPortfolioParameters(
        sleeves=(
            MasterSleeveConfig(
                sleeve_id="momentum",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="global_etf_momentum",
                planning_weight=1.0,
                role_label="core",
            ),
            MasterSleeveConfig(
                sleeve_id="exotic",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="unknown_strategy",
                planning_weight=0.0,
                role_label="core",
            ),
        ),
        defensive_asset="AGG",
    )

    with pytest.raises(BacktestError, match="strategy_id"):
        run_master_portfolio_quarterly_backtest(
            records,
            (date(2024, 3, 31),),
            master_parameters=custom,
            child_parameters=MasterChildStrategyParameters(momentum=_short_momentum_params()),
        )


def test_master_backtest_planning_weights_invariant_remains_one_with_regime_adaptive() -> None:
    """Adding the regime-adaptive sleeve at 0 weight must not break the sum-to-1.0 invariant."""

    records = _synthetic_universe()
    parameters = default_master_portfolio_parameters_with_regime_adaptive()
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30)),
        master_parameters=parameters,
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    for period in result.rebalance_results:
        assert round(sum(period.portfolio_target_weights.values()), 8) == 1.0
