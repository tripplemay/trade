from datetime import date, timedelta

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    apply_kill_switch_constraint,
    drawdown_against_hwm,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    MasterPortfolioParameters,
    MasterSleeveConfig,
)
from trade.strategies.risk_parity import RiskParityParameters


def test_drawdown_against_hwm_returns_zero_at_high_water_mark() -> None:
    assert drawdown_against_hwm(equity=100.0, high_water_mark=100.0) == 0.0


def test_drawdown_against_hwm_returns_negative_below_hwm() -> None:
    assert drawdown_against_hwm(equity=85.0, high_water_mark=100.0) == pytest.approx(-0.15)


def test_drawdown_against_hwm_handles_non_positive_hwm() -> None:
    assert drawdown_against_hwm(equity=100.0, high_water_mark=0.0) == 0.0


def test_apply_kill_switch_constraint_caps_increases_in_non_defensive_assets() -> None:
    new_weights = {"SPY": 0.6, "AGG": 0.2, "SGOV": 0.2}
    prior_weights = {"SPY": 0.4, "AGG": 0.3, "SGOV": 0.3}

    capped, reductions = apply_kill_switch_constraint(
        new_weights=new_weights,
        prior_weights=prior_weights,
        defensive_asset="SGOV",
    )

    assert capped["SPY"] == pytest.approx(0.4)
    assert reductions == {"SPY": pytest.approx(0.2)}


def test_apply_kill_switch_constraint_routes_excess_to_defensive_asset() -> None:
    new_weights = {"SPY": 0.6, "AGG": 0.4, "SGOV": 0.0}
    prior_weights = {"SPY": 0.4, "AGG": 0.3, "SGOV": 0.3}

    capped, reductions = apply_kill_switch_constraint(
        new_weights=new_weights,
        prior_weights=prior_weights,
        defensive_asset="SGOV",
    )

    assert capped["SPY"] == pytest.approx(0.4)
    assert capped["AGG"] == pytest.approx(0.3)
    assert capped["SGOV"] == pytest.approx(0.3)
    assert round(sum(capped.values()), 8) == 1.0
    assert reductions == {"SPY": pytest.approx(0.2), "AGG": pytest.approx(0.1)}


def test_apply_kill_switch_constraint_preserves_decreases() -> None:
    new_weights = {"SPY": 0.2, "AGG": 0.5, "SGOV": 0.3}
    prior_weights = {"SPY": 0.4, "AGG": 0.3, "SGOV": 0.3}

    capped, reductions = apply_kill_switch_constraint(
        new_weights=new_weights,
        prior_weights=prior_weights,
        defensive_asset="SGOV",
    )

    assert capped["SPY"] == pytest.approx(0.2)
    assert capped["AGG"] == pytest.approx(0.3)
    assert reductions == {"AGG": pytest.approx(0.2)}


def test_apply_kill_switch_constraint_does_not_cap_defensive_asset() -> None:
    new_weights = {"SPY": 0.2, "SGOV": 0.8}
    prior_weights = {"SPY": 0.4, "SGOV": 0.2}

    capped, _ = apply_kill_switch_constraint(
        new_weights=new_weights,
        prior_weights=prior_weights,
        defensive_asset="SGOV",
    )

    assert capped["SGOV"] == pytest.approx(0.8)


def _single_sleeve_master() -> MasterPortfolioParameters:
    return MasterPortfolioParameters(
        sleeves=(
            MasterSleeveConfig(
                sleeve_id="rp",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="risk_parity_vol_target",
                planning_weight=1.0,
                role_label="core",
            ),
        ),
        defensive_asset="SGOV",
    )


def _risk_parity_universe_params() -> RiskParityParameters:
    return RiskParityParameters(
        universe=("SPY", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=2.0,
    )


Q1_END = date(2024, 3, 31)
Q2_END = date(2024, 6, 30)
Q3_END = date(2024, 9, 30)
QUARTER_END_SIGNAL_DATES = (Q1_END, Q2_END, Q3_END)
MULTI_QUARTER_DAYS = 275


def _crashing_history(observations: int = MULTI_QUARTER_DAYS) -> tuple[PriceBar, ...]:
    """SPY rises mildly through Q1, crashes through Q2, then drifts flat with small noise."""

    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    sgov = 100.0
    for index in range(observations):
        if index <= 90:
            base = 100.0 + 0.05 * index
        elif index <= 180:
            base = 104.5 - 0.32 * (index - 90)
        else:
            base = 75.7
        spy = base + (0.1 if index % 2 else -0.1)
        records.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol="SPY",
                open=spy * 0.999,
                close=spy,
                adjusted_close=spy,
                volume=1000,
            )
        )
        records.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol="SGOV",
                open=sgov + (0.001 if index % 2 else -0.001),
                close=sgov + (0.001 if index % 2 else -0.001),
                adjusted_close=sgov + (0.001 if index % 2 else -0.001),
                volume=1000,
            )
        )
    return tuple(records)


def _rising_history(observations: int = MULTI_QUARTER_DAYS) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for index in range(observations):
        spy = 100.0 + 0.1 * index + (0.05 if index % 2 else -0.05)
        records.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol="SPY",
                open=spy * 0.999,
                close=spy,
                adjusted_close=spy,
                volume=1000,
            )
        )
        sgov = 100.0 + (0.001 if index % 2 else -0.001)
        records.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol="SGOV",
                open=sgov,
                close=sgov,
                adjusted_close=sgov,
                volume=1000,
            )
        )
    return tuple(records)


def test_master_kill_switch_inactive_when_equity_grows() -> None:
    """A monotonically rising scenario must never trigger the kill-switch."""

    result = run_master_portfolio_quarterly_backtest(
        _rising_history(),
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
    )

    assert result.account_risk_state.kill_switch_active is False
    assert result.account_risk_state.kill_switch_triggered_at is None
    assert result.kill_switch_events == ()


def test_master_kill_switch_triggers_when_drawdown_breaches_threshold() -> None:
    records = _crashing_history()

    result = run_master_portfolio_quarterly_backtest(
        records,
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
    )

    assert result.account_risk_state.kill_switch_active is True
    assert result.account_risk_state.kill_switch_triggered_at is not None
    assert result.account_risk_state.kill_switch_trigger_drawdown is not None
    assert result.account_risk_state.kill_switch_trigger_drawdown <= -0.15
    assert result.account_risk_state.human_review_required is True
    trigger_events = tuple(
        event for event in result.kill_switch_events if event.event_kind == "triggered"
    )
    assert len(trigger_events) == 1


def test_master_kill_switch_caps_non_defensive_after_trigger() -> None:
    records = _crashing_history()
    result = run_master_portfolio_quarterly_backtest(
        records,
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
    )

    triggered_index = next(
        index
        for index, period in enumerate(result.rebalance_results)
        if period.pre_rebalance_account_risk_state.kill_switch_active
    )
    triggered_period = result.rebalance_results[triggered_index]
    prior_period = result.rebalance_results[triggered_index - 1]

    for asset, weight in triggered_period.portfolio_target_weights.items():
        if asset == result.parameters.defensive_asset:
            continue
        assert weight <= prior_period.portfolio_target_weights.get(asset, 0.0) + 1e-9, (
            f"non-defensive asset {asset} weight increased after kill-switch trigger"
        )


def test_master_kill_switch_clearance_resets_state_for_next_period() -> None:
    records = _crashing_history()
    result = run_master_portfolio_quarterly_backtest(
        records,
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
        kill_switch_clearance_signal_dates=(Q3_END,),
    )

    last_period = result.rebalance_results[-1]
    assert last_period.pre_rebalance_account_risk_state.kill_switch_active is False
    clear_events = tuple(
        event for event in result.kill_switch_events if event.event_kind == "cleared"
    )
    assert len(clear_events) == 1
    assert clear_events[0].signal_date == Q3_END


def test_master_kill_switch_period_records_pre_rebalance_state() -> None:
    records = _crashing_history()
    result = run_master_portfolio_quarterly_backtest(
        records,
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
    )

    first_period = result.rebalance_results[0]
    assert first_period.pre_rebalance_account_risk_state.kill_switch_active is False
    assert first_period.pre_rebalance_account_risk_state.high_water_mark == pytest.approx(
        100_000.0
    )


def test_master_kill_switch_does_not_modify_child_internal_weights() -> None:
    """Account-level kill-switch must not mutate child strategy target_weights."""
    records = _crashing_history()
    result = run_master_portfolio_quarterly_backtest(
        records,
        QUARTER_END_SIGNAL_DATES,
        master_parameters=_single_sleeve_master(),
        child_parameters=MasterChildStrategyParameters(
            risk_parity=_risk_parity_universe_params()
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
    )

    for period in result.rebalance_results:
        for contribution in period.sleeve_contributions:
            assert round(sum(contribution.child_target_weights.values()), 8) == 1.0
