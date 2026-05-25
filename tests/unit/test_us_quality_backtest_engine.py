"""Unit tests for the B025 single-sleeve backtest engine."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.us_quality_momentum.engine import (
    BacktestConfig,
    BacktestError,
    monthly_signal_dates,
    run_backtest,
)
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)

BACKTEST_START = date(2017, 1, 1)
BACKTEST_END = date(2024, 12, 31)


@pytest.fixture(scope="module")
def fixture_backtest_result():
    """Run a backtest once per module to amortize the ~5s compute cost."""

    return run_backtest(start=BACKTEST_START, end=BACKTEST_END)


def test_monthly_signal_dates_returns_last_trading_day_per_month() -> None:
    trading = pd.bdate_range(start="2023-01-01", end="2023-12-31")
    signals = monthly_signal_dates(trading, date(2023, 1, 1), date(2023, 12, 31))
    assert len(signals) == 12
    assert signals[0] == date(2023, 1, 31)
    assert signals[-1] == date(2023, 12, 29)


def test_monthly_signal_dates_rejects_empty_input() -> None:
    with pytest.raises(BacktestError, match="empty"):
        monthly_signal_dates([], date(2023, 1, 1), date(2023, 12, 31))


def test_monthly_signal_dates_rejects_window_without_trading_days() -> None:
    trading = pd.bdate_range(start="2020-01-01", end="2020-12-31")
    with pytest.raises(BacktestError, match="no trading dates"):
        monthly_signal_dates(trading, date(2025, 1, 1), date(2025, 12, 31))


def test_run_backtest_produces_periods_for_multi_year_window(fixture_backtest_result) -> None:
    result = fixture_backtest_result
    assert len(result.rebalance_periods) >= 60  # ~12 × 8 years
    assert result.ending_value > 0


def test_run_backtest_equity_curve_is_daily_and_monotone_in_dates(fixture_backtest_result) -> None:
    result = fixture_backtest_result
    curve = result.equity_curve
    assert not curve.empty
    assert (curve["date"].diff().dropna() >= pd.Timedelta(0)).all()
    # Daily mark-to-market = at least 200 rows per year of window.
    assert len(curve) > 200 * 6


def test_run_backtest_is_deterministic_for_same_inputs() -> None:
    a = run_backtest(start=BACKTEST_START, end=date(2020, 12, 31))
    b = run_backtest(start=BACKTEST_START, end=date(2020, 12, 31))
    assert a.starting_capital == b.starting_capital
    assert pytest.approx(a.ending_value, abs=1e-6) == b.ending_value
    assert len(a.rebalance_periods) == len(b.rebalance_periods)
    for pa, pb in zip(a.rebalance_periods, b.rebalance_periods, strict=True):
        assert pa.signal_date == pb.signal_date
        assert pa.target_weights == pb.target_weights


def test_run_backtest_rejects_non_positive_starting_capital() -> None:
    with pytest.raises(BacktestError, match="starting_capital"):
        run_backtest(config=BacktestConfig(starting_capital=0.0))


def test_run_backtest_requires_at_least_two_signal_dates() -> None:
    with pytest.raises(BacktestError, match=">= 2 monthly"):
        run_backtest(start=date(2024, 1, 1), end=date(2024, 1, 15))


def test_run_backtest_period_weights_match_strategy_parameters(
    fixture_backtest_result,
) -> None:
    result = fixture_backtest_result
    params = result.parameters
    for period in result.rebalance_periods:
        if period.target_weights:
            assert max(period.target_weights.values()) <= params.max_position_weight + 1e-9
            assert (
                sum(period.target_weights.values()) <= 1.0 + 1e-8
            )


def test_run_backtest_sector_exposure_respects_cap(fixture_backtest_result) -> None:
    result = fixture_backtest_result
    params = result.parameters
    for period in result.rebalance_periods:
        if period.sector_exposure:
            assert max(period.sector_exposure.values()) <= params.max_sector_weight + 1e-8


def test_run_backtest_supports_custom_parameters() -> None:
    custom = UsQualityMomentumParameters(top_n=20, max_position_weight=0.08)
    result = run_backtest(parameters=custom, start=BACKTEST_START, end=date(2019, 12, 31))
    for period in result.rebalance_periods:
        if period.target_weights:
            assert len(period.target_weights) <= 20
