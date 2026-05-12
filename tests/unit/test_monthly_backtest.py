from datetime import date

import pytest

from trade.backtest.monthly import (
    BacktestError,
    BacktestParameters,
    run_monthly_backtest,
    run_multi_monthly_backtest,
)
from trade.data.loader import PriceBar, load_fixture_prices
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


def _short_window_parameters() -> MomentumParameters:
    return MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )


def test_monthly_backtest_uses_t_plus_1_open_not_signal_close() -> None:
    snapshot = load_fixture_prices()
    result = run_monthly_backtest(
        snapshot.records,
        _short_window_parameters(),
        signal_date=date(2024, 10, 31),
    )
    fill = result.fills[0]

    assert fill.signal_date == date(2024, 10, 31)
    assert fill.execution_date == date(2024, 11, 29)
    assert fill.execution_price_field == "open"
    assert fill.execution_assumption == "t_plus_1_open"
    assert fill.execution_price != fill.signal_price


def test_monthly_backtest_records_cost_and_slippage_parameters() -> None:
    snapshot = load_fixture_prices()
    result = run_monthly_backtest(
        snapshot.records,
        _short_window_parameters(),
        signal_date=date(2024, 10, 31),
    )

    assert result.cost_bps == 1.0
    assert result.slippage_bps == 2.0
    assert result.ending_value > 0


def test_missing_t_plus_1_open_falls_back_with_risk_flag() -> None:
    snapshot = load_fixture_prices()
    filtered_records = tuple(
        record
        for record in snapshot.records
        if not (record.date == date(2024, 11, 29) and record.symbol == "SPY")
    )
    result = run_monthly_backtest(
        filtered_records,
        _short_window_parameters(),
        signal_date=date(2024, 10, 31),
    )
    fill = result.fills[0]

    assert fill.symbol == "SPY"
    assert fill.execution_price_field == "close"
    assert fill.execution_assumption == "fallback_to_signal_close_due_to_missing_t_plus_1_open"
    assert result.risk_flags == (
        "missing_t_plus_1_open:SPY:2024-11-29",
        "missing_t_plus_1_open_policy:flag_and_fallback_to_signal_close",
    )


def test_missing_t_plus_1_open_can_skip_trade_with_risk_flag() -> None:
    snapshot = load_fixture_prices()
    filtered_records = tuple(
        record
        for record in snapshot.records
        if not (record.date == date(2024, 11, 29) and record.symbol == "SPY")
    )
    result = run_monthly_backtest(
        filtered_records,
        _short_window_parameters(),
        BacktestParameters(missing_t_plus_1_open_policy="skip_trade"),
        signal_date=date(2024, 10, 31),
    )

    assert result.fills[0].execution_price_field == "none"
    assert result.fills[0].execution_assumption == "skip_trade_due_to_missing_t_plus_1_open"
    assert result.ending_value == 0.0
    assert result.risk_flags == (
        "missing_t_plus_1_open:SPY:2024-11-29",
        "missing_t_plus_1_open_policy:skip_trade",
    )


def test_missing_t_plus_1_open_can_fail_closed() -> None:
    snapshot = load_fixture_prices()
    filtered_records = tuple(
        record
        for record in snapshot.records
        if not (record.date == date(2024, 11, 29) and record.symbol == "SPY")
    )

    with pytest.raises(BacktestError, match=r"missing T\+1 open"):
        run_monthly_backtest(
            filtered_records,
            _short_window_parameters(),
            BacktestParameters(missing_t_plus_1_open_policy="fail_closed"),
            signal_date=date(2024, 10, 31),
        )


def test_backtest_accepts_tuple_of_price_bars_only() -> None:
    records = (
        PriceBar(date(2024, 1, 31), "SPY", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 2, 29), "SPY", 101.0, 101.0, 101.0, 1),
        PriceBar(date(2024, 3, 29), "SPY", 102.0, 102.0, 102.0, 1),
        PriceBar(date(2024, 4, 30), "SPY", 103.0, 103.0, 103.0, 1),
        PriceBar(date(2024, 5, 31), "AGG", 100.0, 100.0, 100.0, 1),
    )

    assert isinstance(records, tuple)


def test_multi_monthly_backtest_covers_multiple_signal_and_execution_dates() -> None:
    snapshot = load_fixture_prices()
    result = run_multi_monthly_backtest(
        snapshot.records,
        (date(2024, 9, 30), date(2024, 10, 31), date(2024, 11, 29)),
        _short_window_parameters(),
    )

    assert len(result.rebalance_results) == 3
    assert len(result.equity_curve) == 4
    assert [rebalance.signal.signal_date for rebalance in result.rebalance_results] == [
        date(2024, 9, 30),
        date(2024, 10, 31),
        date(2024, 11, 29),
    ]
    assert [rebalance.fills[0].execution_date for rebalance in result.rebalance_results] == [
        date(2024, 10, 31),
        date(2024, 11, 29),
        date(2024, 12, 31),
    ]
    assert result.ending_value == result.rebalance_results[-1].ending_value
    assert result.equity_curve[-1].value == result.ending_value
    assert result.turnover > 0
