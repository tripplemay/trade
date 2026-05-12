from datetime import date

from trade.backtest.monthly import run_monthly_backtest
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
    assert result.risk_flags == ("missing_t_plus_1_open:SPY:2024-11-29",)


def test_backtest_accepts_tuple_of_price_bars_only() -> None:
    records = (
        PriceBar(date(2024, 1, 31), "SPY", 100.0, 100.0, 100.0, 1),
        PriceBar(date(2024, 2, 29), "SPY", 101.0, 101.0, 101.0, 1),
        PriceBar(date(2024, 3, 29), "SPY", 102.0, 102.0, 102.0, 1),
        PriceBar(date(2024, 4, 30), "SPY", 103.0, 103.0, 103.0, 1),
        PriceBar(date(2024, 5, 31), "AGG", 100.0, 100.0, 100.0, 1),
    )

    assert isinstance(records, tuple)
