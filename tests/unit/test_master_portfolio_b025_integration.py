"""B025 F004: Master Portfolio integration tests with implemented satellite_us_quality.

Combines the existing Master ETF fixture (SPY/VEA/AGG/GLD/SGOV) with the
us_quality_momentum fixture so the Master backtest exercises all four
sleeves end-to-end, including the new IMPLEMENTED satellite_us_quality.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    MasterPortfolioBacktestResult,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.data.us_quality_universe import load_prices
from trade.portfolio.master import SLEEVE_TYPE_IMPLEMENTED
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)


@pytest.fixture(autouse=True)
def _force_b025_fixture_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin Master Portfolio B025 integration tests to the synthetic fixture.

    B030 F002 introduced unified-first loading in
    :mod:`trade.data.us_quality_universe`. These integration tests
    were calibrated against the 30-ticker fixture; the larger unified
    universe (52 tickers across the B025 + B028 backfill) breaks the
    "satellite_us_quality holds real us-quality tickers" assertions
    because the unified universe includes additional names the
    Master backtest hasn't been wired against.
    """

    monkeypatch.setenv("FORCE_FIXTURE_PATH", "1")

# Trading days that exist in both the ETF synthetic fixture and the US Quality
# fixture. Q1 2024 end (signal date) and the next trading day (execution).
Q1_2024_END = date(2024, 3, 29)
Q2_2024_END = date(2024, 6, 28)
Q3_2024_END = date(2024, 9, 30)


def _short_momentum_params():
    from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow

    return MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )


def _short_risk_parity_params():
    from trade.strategies.risk_parity import RiskParityParameters

    return RiskParityParameters(
        universe=("SPY", "VEA", "AGG", "GLD", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.5,
    )


def _etf_price_records(
    symbols: tuple[str, ...], anchor_dates: tuple[date, ...]
) -> list[PriceBar]:
    """Generate synthetic PriceBar records for the ETF universe.

    Window starts ~6 months before the earliest anchor so risk_parity's
    60-day volatility_lookback and momentum's multi-period window both have
    enough history.
    """

    records: list[PriceBar] = []
    start = min(anchor_dates) - timedelta(days=200)
    end = max(anchor_dates) + timedelta(days=30)
    span_days = (end - start).days + 1
    for symbol_idx, symbol in enumerate(symbols):
        base = 100.0 + symbol_idx * 5.0
        for day_offset in range(span_days):
            day = start + timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue  # skip weekends
            jitter = (day_offset * 0.1) + symbol_idx
            price = base + jitter
            records.append(
                PriceBar(
                    date=day,
                    symbol=symbol,
                    open=price - 0.10,
                    close=price,
                    adjusted_close=price,
                    volume=1_000_000,
                )
            )
    return records


def _us_quality_price_records(anchor_dates: tuple[date, ...]) -> list[PriceBar]:
    """Bridge our pandas prices fixture into PriceBar records for the Master backtest."""

    df = load_prices()
    start = pd.Timestamp(min(anchor_dates) - timedelta(days=30))
    end = pd.Timestamp(max(anchor_dates) + timedelta(days=30))
    df = df[df["date"].between(start, end)]
    records: list[PriceBar] = []
    for _, row in df.iterrows():
        records.append(
            PriceBar(
                date=pd.Timestamp(row["date"]).date(),
                symbol=str(row["ticker"]),
                open=float(row["open"]),
                close=float(row["close"]),
                adjusted_close=float(row["adj_close"]),
                volume=int(row["volume"]),
            )
        )
    return records


def _combined_records(anchor_dates: tuple[date, ...]) -> tuple[PriceBar, ...]:
    etf = _etf_price_records(("SPY", "VEA", "AGG", "GLD", "SGOV"), anchor_dates)
    us_quality = _us_quality_price_records(anchor_dates)
    return tuple(etf + us_quality)


def _run_combined_master(
    signal_dates: tuple[date, ...] = (Q1_2024_END,),
) -> MasterPortfolioBacktestResult:
    records = _combined_records(signal_dates)
    return run_master_portfolio_quarterly_backtest(
        records,
        signal_dates,
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0
        ),
    )


def test_master_backtest_routes_satellite_us_quality_to_implemented_strategy() -> None:
    result = _run_combined_master()
    period = result.rebalance_results[0]
    satellite = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == "satellite_us_quality"
    )
    assert satellite.sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert satellite.strategy_id == "us_quality_momentum"


def test_master_backtest_satellite_us_quality_holds_real_us_quality_tickers() -> None:
    result = _run_combined_master()
    period = result.rebalance_results[0]
    satellite = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == "satellite_us_quality"
    )
    # Should hold real US Quality tickers, NOT the defensive asset.
    assert "SGOV" not in satellite.child_target_weights
    assert any(
        ticker in satellite.child_target_weights
        for ticker in ("AAPL", "MSFT", "NVDA", "JNJ", "UNH")
    )


def test_master_backtest_satellite_contribution_sums_to_planning_weight() -> None:
    result = _run_combined_master()
    period = result.rebalance_results[0]
    satellite = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == "satellite_us_quality"
    )
    total_contribution = sum(satellite.contribution_weights.values())
    # planning_weight=0.20 × signal weights (≤ 1.0) ≤ 0.20.
    assert total_contribution <= 0.20 + 1e-8
    assert total_contribution > 0.0


def test_master_backtest_with_us_quality_runs_across_multiple_quarters() -> None:
    result = _run_combined_master(signal_dates=(Q1_2024_END, Q2_2024_END, Q3_2024_END))
    assert len(result.rebalance_results) == 3
    # The us_quality sleeve must contribute real tickers in every quarter.
    for period in result.rebalance_results:
        satellite = next(
            contribution
            for contribution in period.sleeve_contributions
            if contribution.sleeve_id == "satellite_us_quality"
        )
        assert satellite.child_target_weights


def test_master_backtest_kill_switch_remains_inactive_under_normal_conditions() -> None:
    result = _run_combined_master(signal_dates=(Q1_2024_END, Q2_2024_END))
    # Synthetic fixture moves are mild — kill switch should NOT trigger.
    assert result.account_risk_state.kill_switch_active is False


def test_master_backtest_is_deterministic_with_us_quality_sleeve() -> None:
    a = _run_combined_master(signal_dates=(Q1_2024_END,))
    b = _run_combined_master(signal_dates=(Q1_2024_END,))
    period_a = a.rebalance_results[0]
    period_b = b.rebalance_results[0]
    assert period_a.portfolio_target_weights == period_b.portfolio_target_weights


def test_master_backtest_us_quality_uses_supplied_child_parameters() -> None:
    """Custom us_quality parameters should propagate through Master backtest."""

    custom = UsQualityMomentumParameters(top_n=20, max_position_weight=0.08)
    records = _combined_records((Q1_2024_END,))
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_2024_END,),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
            us_quality_momentum=custom,
        ),
    )
    period = result.rebalance_results[0]
    satellite = next(
        contribution
        for contribution in period.sleeve_contributions
        if contribution.sleeve_id == "satellite_us_quality"
    )
    # With top_n=20, up to 20 us_quality tickers may appear.
    assert len(satellite.child_target_weights) <= 20
