"""BL-B011-S2 F003: Master Portfolio 4/4 integration with implemented
satellite_hk_china.

Combines the core ETF fixture (SPY/VEA/AGG/GLD/SGOV) + the us_quality fixture
+ the hk_china fixture so the Master backtest exercises ALL FOUR sleeves
end-to-end as IMPLEMENTED strategies — the Master is now 4/4 real (no
SATELLITE_STUB). Mirrors the B025 integration harness.
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
from trade.data import hk_china_universe, us_quality_universe
from trade.data.loader import PriceBar
from trade.portfolio.master import SLEEVE_TYPE_IMPLEMENTED, default_master_portfolio_parameters
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters

Q1_2024_END = date(2024, 3, 29)
Q2_2024_END = date(2024, 6, 28)
Q3_2024_END = date(2024, 9, 30)
_HK_TICKERS = ("MCHI", "FXI", "KWEB", "ASHR")


@pytest.fixture(autouse=True)
def _force_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin both satellites to their synthetic fixtures (deterministic, no
    dependence on a local unified CSV)."""

    monkeypatch.setenv("FORCE_FIXTURE_PATH", "1")


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


def _etf_price_records(anchor_dates: tuple[date, ...]) -> list[PriceBar]:
    records: list[PriceBar] = []
    start = min(anchor_dates) - timedelta(days=200)
    end = max(anchor_dates) + timedelta(days=30)
    span_days = (end - start).days + 1
    for symbol_idx, symbol in enumerate(("SPY", "VEA", "AGG", "GLD", "SGOV")):
        base = 100.0 + symbol_idx * 5.0
        for day_offset in range(span_days):
            day = start + timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue
            price = base + (day_offset * 0.1) + symbol_idx
            records.append(
                PriceBar(
                    date=day, symbol=symbol, open=price - 0.10,
                    close=price, adjusted_close=price, volume=1_000_000,
                )
            )
    return records


def _fixture_price_records(df: pd.DataFrame, anchor_dates: tuple[date, ...]) -> list[PriceBar]:
    start = pd.Timestamp(min(anchor_dates) - timedelta(days=30))
    end = pd.Timestamp(max(anchor_dates) + timedelta(days=30))
    df = df[df["date"].between(start, end)]
    return [
        PriceBar(
            date=pd.Timestamp(row["date"]).date(),
            symbol=str(row["ticker"]),
            open=float(row["open"]),
            close=float(row["close"]),
            adjusted_close=float(row["adj_close"]),
            volume=int(row["volume"]),
        )
        for _, row in df.iterrows()
    ]


def _combined_records(anchor_dates: tuple[date, ...]) -> tuple[PriceBar, ...]:
    etf = _etf_price_records(anchor_dates)
    us_quality = _fixture_price_records(us_quality_universe.load_prices(), anchor_dates)
    hk_china = _fixture_price_records(hk_china_universe.load_prices(), anchor_dates)
    return tuple(etf + us_quality + hk_china)


def _run(signal_dates: tuple[date, ...] = (Q3_2024_END,)) -> MasterPortfolioBacktestResult:
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


def _sleeve(result: MasterPortfolioBacktestResult, sleeve_id: str):
    period = result.rebalance_results[0]
    return next(c for c in period.sleeve_contributions if c.sleeve_id == sleeve_id)


def test_hk_china_sleeve_is_implemented() -> None:
    hk = _sleeve(_run(), "satellite_hk_china")
    assert hk.sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert hk.strategy_id == "hk_china_momentum"


def test_hk_china_sleeve_holds_real_tickers() -> None:
    # The fixture's up-trending KWEB/MCHI pass momentum+trend at Q3 2024 →
    # the sleeve holds real HK-China ETFs (not a pure defensive fall-through).
    hk = _sleeve(_run(), "satellite_hk_china")
    assert any(ticker in hk.child_target_weights for ticker in _HK_TICKERS)


def test_hk_china_contribution_within_planning_weight() -> None:
    hk = _sleeve(_run(), "satellite_hk_china")
    total = sum(hk.contribution_weights.values())
    # planning_weight 0.10 × sleeve weights (sum to 1.0) → ≤ 0.10.
    assert 0.0 < total <= 0.10 + 1e-8


def test_master_is_four_by_four_real() -> None:
    """Every Master sleeve is an IMPLEMENTED strategy and contributes — the
    headline BL-B011-S2 outcome: Master 4/4 real."""

    result = _run()
    period = result.rebalance_results[0]
    by_id = {c.sleeve_id: c for c in period.sleeve_contributions}
    expected = {"momentum", "risk_parity", "satellite_us_quality", "satellite_hk_china"}
    assert set(by_id) == expected
    for sleeve_id in expected:
        assert by_id[sleeve_id].sleeve_type == SLEEVE_TYPE_IMPLEMENTED
        assert by_id[sleeve_id].child_target_weights  # non-empty

    # The default Master params now declare zero SATELLITE_STUB sleeves.
    sleeves = default_master_portfolio_parameters().sleeves
    assert all(s.sleeve_type == SLEEVE_TYPE_IMPLEMENTED for s in sleeves)


def test_hk_china_custom_parameters_propagate() -> None:
    custom = HkChinaMomentumParameters(top_n=1)
    records = _combined_records((Q3_2024_END,))
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q3_2024_END,),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
            hk_china_momentum=custom,
        ),
    )
    hk = _sleeve(result, "satellite_hk_china")
    # top_n=1 → at most one real ETF (+ possibly the defensive remainder).
    real = [t for t in hk.child_target_weights if t in _HK_TICKERS]
    assert len(real) <= 1


def test_master_4x4_is_deterministic() -> None:
    a = _run((Q3_2024_END,)).rebalance_results[0]
    b = _run((Q3_2024_END,)).rebalance_results[0]
    assert a.portfolio_target_weights == b.portfolio_target_weights
