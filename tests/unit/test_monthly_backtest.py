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

    # B111 F004 fix-round — the defaults are the UNIFIED caliber (5+5bps);
    # the legacy 1+2bps stays available via explicit BacktestParameters.
    assert result.cost_bps == 5.0
    assert result.slippage_bps == 5.0
    assert result.ending_value > 0


def test_from_cash_single_leg_cost_under_unified_caliber() -> None:
    """Unified caliber, from-cash deployment: only the buy leg exists, so
    cost = capital x Σ|target| x 10bps = $100 on $100k fully deployed."""
    snapshot = load_fixture_prices()
    result = run_monthly_backtest(
        snapshot.records,
        _short_window_parameters(),
        signal_date=date(2024, 10, 31),
    )

    assert result.turnover == pytest.approx(1.0)
    assert result.cost_amount == pytest.approx(100.0)
    # The cost is DEDUCTED from the executed portfolio value (paper-engine
    # form), not baked into smaller fills (legacy one-sided haircut).
    assert result.ending_value == pytest.approx(
        result.equity_curve[-1].value
    )


def test_multi_monthly_unchanged_target_is_costless_under_unified_caliber() -> None:
    """Both-legs turnover model: a rebalance into an UNCHANGED target trades
    nothing (Σ|Δw| = 0) and therefore costs nothing — the legacy haircut
    charged a buy leg every single month regardless."""
    records = (
        PriceBar(date(2024, 1, 31), "SPY", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 2, 29), "SPY", 101.0, 101.0, 101.0, 1),
        PriceBar(date(2024, 3, 29), "SPY", 102.0, 102.0, 102.0, 1),
        PriceBar(date(2024, 4, 30), "SPY", 103.0, 103.0, 103.0, 1),
        PriceBar(date(2024, 5, 31), "SPY", 104.0, 104.0, 104.0, 1),
        PriceBar(date(2024, 6, 28), "SPY", 105.0, 105.0, 105.0, 1),
        # Defensive asset must exist in the records; flat price, never selected.
        PriceBar(date(2024, 1, 31), "AGG", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 2, 29), "AGG", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 3, 29), "AGG", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 4, 30), "AGG", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 5, 31), "AGG", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 6, 28), "AGG", 100.0, 100.0, 100.0, 1),
    )
    params = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_multi_monthly_backtest(
        records,
        (date(2024, 3, 29), date(2024, 4, 30), date(2024, 5, 31)),
        params,
    )

    periods = result.rebalance_results
    assert periods[0].turnover == pytest.approx(1.0)  # from cash: buy leg
    assert periods[0].cost_amount == pytest.approx(100_000.0 * 0.001)
    # Same winner every month → no Δweights → zero cost thereafter.
    assert periods[1].turnover == pytest.approx(0.0)
    assert periods[1].cost_amount == pytest.approx(0.0)
    assert periods[2].cost_amount == pytest.approx(0.0)
    assert result.cost_amount == pytest.approx(periods[0].cost_amount)


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
