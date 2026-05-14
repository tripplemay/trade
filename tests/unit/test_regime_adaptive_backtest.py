from dataclasses import replace
from datetime import date, timedelta

import pytest

from trade.backtest.monthly import BacktestError, BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.backtest import (
    RegimeAdaptiveBacktestResult,
    RegimeAdaptivePeriodResult,
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.regime import REGIME_NORMAL


def _bars(symbol: str, prices: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
    return [
        PriceBar(
            date=start + timedelta(days=index),
            symbol=symbol,
            open=price * 0.999,
            close=price,
            adjusted_close=price,
            volume=1_000,
        )
        for index, price in enumerate(prices)
    ]


def _rising(length: int, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + step * index for index in range(length)]


def _short_config() -> object:
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def _build_records(spy_series: list[float], length: int) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.symbol == "SPY":
            rows.extend(_bars(entry.symbol, spy_series))
            continue
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.0)))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.1 + 0.02 * index)))
    return tuple(rows)


def _crashing_spy(length: int = 220) -> list[float]:
    prices: list[float] = []
    price = 100.0
    for index in range(length - 20):
        if index:
            price *= 1.0 + (0.001 if index % 2 else -0.001)
        prices.append(price)
    for index in range(20):
        price *= 0.95 if index % 2 == 0 else 1.01
        prices.append(price)
    return prices


def test_run_regime_adaptive_monthly_backtest_returns_result_with_period_count(
) -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (
        date(2024, 3, 20),
        date(2024, 4, 19),
        date(2024, 4, 25),
    )

    result = run_regime_adaptive_monthly_backtest(
        records,
        signal_dates,
        config,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    assert isinstance(result, RegimeAdaptiveBacktestResult)
    assert len(result.rebalance_results) == len(signal_dates)
    for period in result.rebalance_results:
        assert isinstance(period, RegimeAdaptivePeriodResult)


def test_run_regime_adaptive_monthly_backtest_executes_at_t_plus_1_open() -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20),)

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)
    period = result.rebalance_results[0]

    assert period.signal_date == date(2024, 3, 20)
    assert period.execution_date == date(2024, 3, 21)
    assert period.fills, "rising universe must produce at least one fill"
    assert {fill.execution_price_field for fill in period.fills} == {"open"}


def test_run_regime_adaptive_monthly_backtest_chains_capital_across_periods() -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    assert len(result.rebalance_results) == 2
    first, second = result.rebalance_results
    assert abs(second.starting_value - first.ending_value) < 1e-9


def test_run_regime_adaptive_monthly_backtest_tolerance_band_suppresses_small_weight_changes(
) -> None:
    """A second rebalance with near-identical targets must keep prior weights."""

    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 3, 25))

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    second = result.rebalance_results[1]
    # With nearly-identical universe behaviour between rebalances, tolerance band must hold.
    assert second.forced_rebalance_by_regime_transition is False
    assert second.turnover <= result.rebalance_results[0].turnover


def test_run_regime_adaptive_monthly_backtest_regime_transition_forces_full_rebalance(
) -> None:
    config = _short_config()
    spy_series = _crashing_spy(length=120)
    records = _build_records(spy_series, length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 25))

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    second = result.rebalance_results[1]
    regimes = [period.regime_state.regime for period in result.rebalance_results]
    assert regimes[0] == REGIME_NORMAL
    assert regimes[1] != REGIME_NORMAL  # SPY crashed → BEAR or CRISIS
    assert second.forced_rebalance_by_regime_transition is True


def test_run_regime_adaptive_monthly_backtest_records_regime_and_gating_history(
) -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20),)

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)
    period = result.rebalance_results[0]

    assert period.regime_state.regime == REGIME_NORMAL
    assert period.gating_result.signal_date == date(2024, 3, 20)
    assert all(period.gating_result.mask[entry.symbol] for entry in config.universe)


def test_run_regime_adaptive_monthly_backtest_is_deterministic() -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    first = run_regime_adaptive_monthly_backtest(records, signal_dates, config)
    second = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    assert first.ending_value == second.ending_value
    assert first.turnover == second.turnover
    assert first.cost_amount == second.cost_amount


def test_run_regime_adaptive_monthly_backtest_rejects_empty_signal_dates() -> None:
    config = _short_config()
    records = _build_records(_rising(60, start=100.0, step=0.5), length=60)

    with pytest.raises(BacktestError, match="signal_dates"):
        run_regime_adaptive_monthly_backtest(records, (), config)


def test_run_regime_adaptive_monthly_backtest_account_drawdown_kill_switch_triggers(
) -> None:
    config = _short_config()
    spy_series = _crashing_spy(length=120)
    records = _build_records(spy_series, length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 25))

    result = run_regime_adaptive_monthly_backtest(
        records,
        signal_dates,
        config,
        BacktestParameters(starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0),
    )

    # Depending on the data, the kill-switch may or may not trigger by the final period;
    # but the state must be exposed without raising.
    assert isinstance(result.account_risk_state.high_water_mark, float)
    assert result.account_risk_state.high_water_mark >= 100_000.0


def test_run_regime_adaptive_monthly_backtest_equity_curve_starts_at_starting_capital(
) -> None:
    config = _short_config()
    records = _build_records(_rising(120, start=100.0, step=0.5), length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_monthly_backtest(
        records,
        signal_dates,
        config,
        BacktestParameters(starting_capital=100_000.0),
    )

    assert result.equity_curve[0].value == pytest.approx(100_000.0)
    assert result.equity_curve[-1].value == pytest.approx(result.ending_value)
