"""B082 F002 — unit tests for the single-asset monthly-rebalance backtest engine.

Hand-computed tiny curves pin: T+1 no-look-ahead execution, frictionless buy-hold
tracking, directional-cost drag, 100-share lot flooring (容量 floor), management-fee
decay, the three-tier de-risking, and the metric/drawdown helpers.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
from trade.backtest.cn_dividend_lowvol.engine import (
    compute_metrics,
    cpcv_lite_fold_cagrs,
    simulate_single_asset,
    walk_forward_oos_metrics,
    window_max_drawdown,
)


def _prices(pairs: list[tuple[str, float]]) -> pd.Series:
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx)


def _targets(pairs: list[tuple[str, float]]) -> pd.Series:
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx)


def test_t_plus_1_no_lookahead_and_buy_hold_tracks_price() -> None:
    prices = _prices([("2020-01-01", 10.0), ("2020-01-02", 10.0),
                      ("2020-01-03", 11.0), ("2020-01-06", 12.0)])
    # Signal on 01-01 executes on the NEXT bar (01-02), never 01-01 itself.
    result = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                   initial_capital=1000.0, cost_model=None)
    # Day 0: still all cash (no look-ahead) → equity == initial capital.
    assert result.equity.iloc[0] == pytest.approx(1000.0)
    # Bought 100 units @10 on 01-02; rides 10→12 → ending 1200.
    assert result.equity.iloc[-1] == pytest.approx(1200.0)
    assert result.metrics.total_return == pytest.approx(0.20)
    assert result.n_rebalances == 1


def test_directional_cost_is_a_drag() -> None:
    prices = _prices([("2020-01-01", 10.0), ("2020-01-02", 10.0), ("2020-01-03", 10.0)])
    cost = CnCostModel(stamp_duty_bps=0.0, commission_bps=2.5, slippage_bps=5.0)
    result = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                   initial_capital=1000.0, cost_model=cost)
    # Buy 1000 notional @ (2.5+5)bp = 0.00075 → 0.75 cost; equity = 1000 - 0.75.
    assert result.equity.iloc[-1] == pytest.approx(999.25)


def test_lot_flooring_capacity_floor() -> None:
    # 1000 CNY, price 10.5 → 95.2 units affordable; lot=100 floors to 0 lots → no position.
    prices = _prices([("2020-01-01", 10.5), ("2020-01-02", 10.5), ("2020-01-03", 12.0)])
    result = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                   initial_capital=1000.0, cost_model=None, lot_size=100)
    assert result.n_rebalances == 0
    assert result.equity.iloc[-1] == pytest.approx(1000.0)  # stayed in cash

    # With lot=10, 95.2 → floors to 90 units; rides 10.5→12.
    result2 = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                    initial_capital=1000.0, cost_model=None, lot_size=10)
    assert result2.n_rebalances == 1
    # 90 units bought @10.5 (cash 1000-945=55); at 12 → 90*12 + 55 = 1135.
    assert result2.equity.iloc[-1] == pytest.approx(1135.0)


def test_three_tier_de_risking_reduces_exposure() -> None:
    # Flat price, so exposure differences show purely via the applied weight.
    prices = _prices([(f"2020-01-{d:02d}", 10.0) for d in range(1, 11)])
    # First execution full (1.0), second low (0.25).
    targets = _targets([("2020-01-02", 1.0), ("2020-01-05", 0.25)])
    result = simulate_single_asset(prices, targets, initial_capital=1000.0, cost_model=None)
    # After the second rebalance the applied risky weight drops to ~0.25.
    assert result.weights.iloc[-1] == pytest.approx(0.25, abs=1e-9)
    assert result.n_rebalances == 2


def test_management_fee_decays_holding() -> None:
    prices = _prices([("2020-01-01", 10.0)] + [(f"2020-01-{d:02d}", 10.0) for d in range(2, 6)])
    no_fee = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                   initial_capital=1000.0, cost_model=None)
    with_fee = simulate_single_asset(prices, _targets([("2020-01-01", 1.0)]),
                                     initial_capital=1000.0, cost_model=None, annual_fee=0.05)
    # Flat price: no fee holds 1000; a 5%/yr fee must erode the holding below it.
    assert no_fee.equity.iloc[-1] == pytest.approx(1000.0)
    assert with_fee.equity.iloc[-1] < 1000.0


def test_window_max_drawdown_in_window_only() -> None:
    equity = pd.Series(
        [100.0, 120.0, 60.0, 90.0],
        index=pd.to_datetime(["2022-01-01", "2022-06-01", "2022-09-01", "2023-01-01"]),
    )
    # Within 2022: peak 120 → trough 60 = -50%.
    assert window_max_drawdown(equity, date(2022, 1, 1), date(2022, 12, 31)) == pytest.approx(-0.5)


def test_compute_metrics_basic_shape() -> None:
    equity = pd.Series(
        [100.0, 110.0, 121.0],
        index=pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"]),
    )
    m = compute_metrics(equity)
    assert m.total_return == pytest.approx(0.21)
    assert m.cagr == pytest.approx(0.10, abs=5e-3)  # ~10%/yr over ~2y
    assert m.max_drawdown == pytest.approx(0.0)


def test_cpcv_lite_returns_k_fold_cagrs() -> None:
    prices = _prices([(f"2020-{m:02d}-15", 100.0 + m) for m in range(1, 13)])
    targets = _targets([(f"2020-{m:02d}-15", 1.0) for m in range(1, 12)])
    result = simulate_single_asset(prices, targets, initial_capital=1000.0, cost_model=None)
    folds = cpcv_lite_fold_cagrs(result.equity, targets, k=4)
    assert len(folds) == 4
    assert all(isinstance(c, float) and math.isfinite(c) for c in folds)


def test_walk_forward_oos_is_subwindow() -> None:
    prices = _prices([(f"2020-{m:02d}-15", 100.0 + m) for m in range(1, 13)])
    result = simulate_single_asset(prices, _targets([("2020-01-15", 1.0)]),
                                   initial_capital=1000.0, cost_model=None)
    oos = walk_forward_oos_metrics(result.equity, is_fraction=0.70)
    # The OOS window is the tail 30% — a valid, finite metric bundle.
    assert math.isfinite(oos.cagr)
    assert oos.years < result.metrics.years
