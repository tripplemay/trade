"""Unit tests for the B025 backtest metrics module."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trade.backtest.us_quality_momentum.engine import run_backtest
from trade.backtest.us_quality_momentum.metrics import (
    annual_returns,
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    compute_performance_metrics,
    cumulative_return,
    excess_returns_vs_benchmark,
    max_drawdown,
    monthly_return_matrix,
    profit_loss_ratio,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)


@pytest.fixture(autouse=True)
def _force_b025_fixture_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin backtest-metrics tests to the B025 synthetic fixture (B030 F002).

    ``test_fixture_backtest_lands_inside_spec_deterministic_ranges``
    explicitly asserts the B025 deterministic backtest metric ranges;
    without this override F002's unified-first branch would surface
    real SEC EDGAR data and the ranges would not hold.
    """

    monkeypatch.setenv("FORCE_FIXTURE_PATH", "1")


def _flat_growth_curve(days: int, daily_growth: float, starting: float = 100.0) -> pd.DataFrame:
    dates = pd.bdate_range(start="2023-01-02", periods=days)
    equity = starting * np.power(1.0 + daily_growth, np.arange(days))
    return pd.DataFrame({"date": dates, "equity": equity})


def test_annualized_return_for_flat_growth_curve_matches_compounding() -> None:
    curve = _flat_growth_curve(252, 0.0005)  # ~13% annual
    ann = annualized_return(curve)
    assert ann == pytest.approx(0.135, abs=0.02)


def test_annualized_volatility_zero_for_flat_curve() -> None:
    curve = _flat_growth_curve(252, 0.0005)
    daily_returns = curve.set_index("date")["equity"].pct_change().dropna()
    vol = annualized_volatility(daily_returns)
    assert vol == pytest.approx(0.0, abs=1e-9)


def test_sharpe_ratio_zero_for_zero_volatility() -> None:
    curve = _flat_growth_curve(252, 0.0005)
    daily_returns = curve.set_index("date")["equity"].pct_change().dropna()
    assert sharpe_ratio(daily_returns) == pytest.approx(0.0, abs=1e-9)


def test_sortino_ratio_zero_when_no_downside_returns() -> None:
    curve = _flat_growth_curve(252, 0.0005)
    daily_returns = curve.set_index("date")["equity"].pct_change().dropna()
    assert sortino_ratio(daily_returns) == pytest.approx(0.0, abs=1e-9)


def test_max_drawdown_finds_largest_peak_to_trough_loss() -> None:
    # 100 → 110 → 88 → 99 → 105: peak 110, trough 88, drawdown -20%.
    curve = pd.DataFrame(
        {
            "date": pd.bdate_range(start="2023-01-02", periods=5),
            "equity": [100.0, 110.0, 88.0, 99.0, 105.0],
        }
    )
    mdd = max_drawdown(curve)
    assert mdd == pytest.approx(-0.20, abs=1e-6)


def test_calmar_ratio_divides_ann_return_by_abs_mdd() -> None:
    curve = pd.DataFrame(
        {
            "date": pd.bdate_range(start="2020-01-02", periods=1000),
            "equity": 100.0 * np.power(1.0 + 0.0005, np.arange(1000)),
        }
    )
    # Inject a 10% drawdown in the middle.
    curve.loc[500:600, "equity"] *= 0.9
    cal = calmar_ratio(curve)
    assert cal > 0


def test_win_rate_counts_positive_days() -> None:
    returns = pd.Series([0.01, -0.005, 0.002, -0.001, 0.003])
    assert win_rate(returns) == pytest.approx(0.6)


def test_profit_loss_ratio_returns_avg_win_over_avg_loss() -> None:
    returns = pd.Series([0.02, -0.01, 0.04, -0.03])
    plr = profit_loss_ratio(returns)
    # avg_win = 0.03, avg_loss = 0.02 → 1.5
    assert plr == pytest.approx(1.5)


def test_cumulative_return_relative_to_start() -> None:
    curve = pd.DataFrame(
        {"date": pd.bdate_range(start="2024-01-02", periods=3), "equity": [100.0, 110.0, 121.0]}
    )
    assert cumulative_return(curve) == pytest.approx(0.21)


def test_monthly_return_matrix_pivots_year_x_month() -> None:
    dates = pd.date_range(start="2023-01-31", periods=12, freq="ME")
    equity = 100.0 * np.power(1.0 + 0.01, np.arange(12))
    curve = pd.DataFrame({"date": dates, "equity": equity})
    matrix = monthly_return_matrix(curve)
    assert not matrix.empty
    assert matrix.index.tolist() == [2023]
    assert sorted(matrix.columns.tolist()) == list(range(2, 13))


def test_annual_returns_returns_one_value_per_calendar_year() -> None:
    dates = pd.date_range(start="2020-12-31", periods=4, freq="YE")
    equity = pd.Series([100.0, 110.0, 121.0, 133.1])
    curve = pd.DataFrame({"date": dates, "equity": equity})
    annual = annual_returns(curve)
    assert annual.index.tolist() == [2021, 2022, 2023]


def test_excess_returns_vs_benchmark_aligns_on_shared_dates() -> None:
    dates = pd.bdate_range(start="2024-01-02", periods=5)
    strategy = pd.DataFrame({"date": dates, "equity": [100, 102, 101, 103, 105]})
    bench = pd.DataFrame({"date": dates, "equity": [100, 101, 101, 102, 103]})
    excess = excess_returns_vs_benchmark(strategy, bench)
    assert not excess.empty
    assert (excess.abs() < 0.05).all()


# ---------------------------------------------------------------------------
# Fixture-backed end-to-end metric ranges (B025 §F004 acceptance)
# ---------------------------------------------------------------------------


def test_fixture_backtest_lands_inside_spec_deterministic_ranges() -> None:
    """Annualized return ∈ [5%, 25%], Sharpe ∈ [0.3, 1.5], MDD < 50%."""

    result = run_backtest(start=date(2017, 1, 1), end=date(2024, 12, 31))
    total_turnover = sum(period.turnover for period in result.rebalance_periods)
    metrics = compute_performance_metrics(
        result.equity_curve, result.daily_returns, total_turnover
    )
    assert 0.05 <= metrics.annualized_return <= 0.25, metrics.annualized_return
    assert 0.30 <= metrics.sharpe_ratio <= 1.50, metrics.sharpe_ratio
    assert metrics.max_drawdown > -0.50, metrics.max_drawdown
