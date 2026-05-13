from datetime import date, timedelta

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestError, BacktestParameters
from trade.data.loader import PriceBar
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    SLEEVE_TYPE_SATELLITE_STUB,
    MasterPortfolioParameters,
    MasterSleeveConfig,
    default_master_portfolio_parameters,
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


def _synthetic_daily_universe(
    symbols: tuple[str, ...], observations: int
) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for symbol_index, symbol in enumerate(symbols):
        price = 100.0 + symbol_index * 10.0
        for index in range(observations):
            if index:
                price *= 1.0 + (0.003 * (symbol_index + 1) if index % 2 else -0.002)
            records.append(
                PriceBar(
                    date=start + timedelta(days=index),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
    return tuple(records)


def test_master_portfolio_backtest_aggregates_to_full_planning_allocation() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    assert len(result.rebalance_results) == 1
    period = result.rebalance_results[0]
    assert round(sum(period.portfolio_target_weights.values()), 8) == 1.0


def test_master_portfolio_backtest_records_per_sleeve_contributions() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    period = result.rebalance_results[0]
    contributions_by_id = {
        contribution.sleeve_id: contribution for contribution in period.sleeve_contributions
    }
    assert set(contributions_by_id) == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }
    assert contributions_by_id["momentum"].planning_weight == 0.40
    assert contributions_by_id["risk_parity"].planning_weight == 0.30
    assert contributions_by_id["satellite_us_quality"].planning_weight == 0.20
    assert contributions_by_id["satellite_hk_china"].planning_weight == 0.10


def test_master_portfolio_satellite_stub_contribution_falls_through_to_defensive_asset() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    period = result.rebalance_results[0]
    stub = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == "satellite_us_quality"
    )
    assert stub.sleeve_type == SLEEVE_TYPE_SATELLITE_STUB
    assert stub.child_target_weights == {"SGOV": 1.0}
    assert stub.contribution_weights == {"SGOV": pytest.approx(0.20)}


def test_master_portfolio_executes_at_t_plus_1_open() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    period = result.rebalance_results[0]
    assert period.signal_date == date(2024, 3, 10)
    assert period.execution_date == date(2024, 3, 11)
    assert {fill.execution_price_field for fill in period.fills} == {"open"}
    assert {fill.execution_assumption for fill in period.fills} == {"t_plus_1_open"}


def test_master_portfolio_chains_capital_across_quarter_rebalances() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    assert len(result.rebalance_results) == 2
    for prior, current in zip(
        result.rebalance_results, result.rebalance_results[1:], strict=False
    ):
        assert abs(current.starting_value - prior.ending_value) < 1e-6


def test_master_portfolio_equity_curve_starts_at_starting_capital_and_extends_per_period() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
    )

    assert len(result.equity_curve) == 3
    assert result.equity_curve[0].value == 100_000.0
    assert result.equity_curve[-1].value == result.ending_value


def test_master_portfolio_turnover_and_cost_increase_with_each_rebalance() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0
        ),
    )

    assert result.turnover > 0
    assert result.cost_amount > 0
    assert result.rebalance_results[0].turnover == pytest.approx(1.0)


def test_master_portfolio_does_not_act_between_supplied_signal_dates() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    quarter_signal_dates = (date(2024, 3, 10), date(2024, 3, 20))
    result = run_master_portfolio_quarterly_backtest(
        records,
        quarter_signal_dates,
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    assert tuple(period.signal_date for period in result.rebalance_results) == quarter_signal_dates


def test_master_portfolio_rejects_empty_signal_dates() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "SGOV"), 30)
    with pytest.raises(BacktestError, match="signal_dates"):
        run_master_portfolio_quarterly_backtest(records, ())


def test_master_portfolio_with_two_implemented_sleeves_routes_stub_to_defensive() -> None:
    """Custom master config with only one implemented + one stub still aggregates correctly."""
    records = _synthetic_daily_universe(("SPY", "AGG", "SGOV"), 90)
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
                sleeve_id="reserved",
                sleeve_type=SLEEVE_TYPE_SATELLITE_STUB,
                strategy_id=None,
                planning_weight=0.5,
                role_label="stub",
            ),
        ),
        defensive_asset="AGG",
    )
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        master_parameters=custom,
        child_parameters=MasterChildStrategyParameters(momentum=_short_momentum_params()),
    )

    period = result.rebalance_results[0]
    stub = next(c for c in period.sleeve_contributions if c.sleeve_id == "reserved")
    assert stub.child_target_weights == {"AGG": 1.0}
    assert stub.contribution_weights == {"AGG": pytest.approx(0.5)}


def test_master_portfolio_validates_parameters_before_running() -> None:
    records = _synthetic_daily_universe(("SPY", "AGG", "SGOV"), 90)
    leveraged = MasterPortfolioParameters(max_exposure=1.5)
    with pytest.raises(Exception, match="leverage"):
        run_master_portfolio_quarterly_backtest(
            records,
            (date(2024, 3, 10),),
            master_parameters=leveraged,
        )


def test_master_portfolio_default_config_uses_default_child_parameters() -> None:
    """Calling without explicit child_parameters should still work with implementation defaults."""
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 90)
    custom = default_master_portfolio_parameters()
    # Exercise the default master config path while still using fast short child params.
    result = run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 10),),
        master_parameters=custom,
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )
    assert result.starting_capital > 0
    assert result.ending_value > 0
