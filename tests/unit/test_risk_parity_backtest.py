from datetime import date, timedelta

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import PriceBar
from trade.strategies.risk_parity import RiskParityParameters


def test_risk_parity_monthly_backtest_records_execution_trace() -> None:
    records = _multi_asset_history(("SPY", "AGG", "SGOV"), 90)
    parameters = RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.5,
    )

    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        parameters,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    assert result.starting_capital == 100_000.0
    assert result.ending_value > 0
    assert len(result.rebalance_results) == 2
    assert len(result.equity_curve) == 3
    assert result.turnover > 0
    assert result.cost_amount > 0
    first = result.rebalance_results[0]
    assert first.signal.signal_date == date(2024, 3, 10)
    assert first.fills[0].execution_date == date(2024, 3, 11)
    assert {fill.execution_price_field for fill in first.fills} == {"open"}
    assert round(sum(first.signal.target_weights.values()), 8) == 1.0


def test_risk_parity_backtest_records_defensive_allocation_when_scaled_down() -> None:
    records = _multi_asset_history(("SPY", "AGG", "SGOV"), 90)
    parameters = RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.01,
    )

    result = run_risk_parity_monthly_backtest(records, (date(2024, 3, 10),), parameters)

    signal = result.rebalance_results[0].signal
    assert 0 < signal.exposure_scale < 1.0
    assert signal.target_weights["SGOV"] > 0.0
    assert round(result.rebalance_results[0].turnover, 8) == 1.0


def _multi_asset_history(symbols: tuple[str, ...], observations: int) -> tuple[PriceBar, ...]:
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
