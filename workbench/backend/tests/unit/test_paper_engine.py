"""B056 F001 — pure virtual-rebalance engine.

Exact-arithmetic tests of ``compute_rebalance``: activation from all cash,
rebalance with existing holdings, real cost application, avg-cost blending,
sell-to-zero, and the graceful no-ops (unmarkable target / no target / no equity).
"""

from __future__ import annotations

import pytest

from workbench_api.paper.engine import compute_rebalance


def test_activation_from_all_cash_exact_shares_cost_and_cash() -> None:
    plan = compute_rebalance(
        cash=100_000.0,
        current_positions={},
        target_weights={"AAA": 0.6, "BBB": 0.4},
        marks={"AAA": 100.0, "BBB": 50.0},
        fee_bps=5.0,
        slippage_bps=5.0,
    )
    # cost_rate = 0.001; investable = 100000 * 0.999 = 99900.
    # AAA: 0.6*99900/100 = 599.4 sh; BBB: 0.4*99900/50 = 799.2 sh.
    by = {p.symbol: p for p in plan.positions}
    assert by["AAA"].shares == pytest.approx(599.4)
    assert by["BBB"].shares == pytest.approx(799.2)
    # avg_cost == fill close on a fresh buy.
    assert by["AAA"].avg_cost == pytest.approx(100.0)
    assert by["BBB"].avg_cost == pytest.approx(50.0)
    # gross traded = 99900 → cost = 99.9; cash residual = 0.1.
    assert plan.traded_notional == pytest.approx(99_900.0)
    assert plan.cost == pytest.approx(99.9)
    assert plan.cash == pytest.approx(0.1)
    assert plan.traded is True
    assert plan.skipped_symbols == ()


def test_unmarkable_target_is_skipped_weight_falls_to_cash() -> None:
    plan = compute_rebalance(
        cash=100_000.0,
        current_positions={},
        target_weights={"AAA": 0.5, "NOPRICE": 0.5},
        marks={"AAA": 100.0},  # NOPRICE has no mark
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    by = {p.symbol: p for p in plan.positions}
    # Only AAA bought (0.5 weight); NOPRICE's half stays as cash.
    assert set(by) == {"AAA"}
    assert by["AAA"].shares == pytest.approx(500.0)  # 0.5*100000/100
    assert plan.cash == pytest.approx(50_000.0)
    assert plan.skipped_symbols == ("NOPRICE",)


def test_no_targets_is_graceful_noop_keeps_book() -> None:
    plan = compute_rebalance(
        cash=1_000.0,
        current_positions={"AAA": (10.0, 90.0)},
        target_weights={},
        marks={"AAA": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
    )
    assert plan.traded is False
    assert plan.cost == 0.0
    assert plan.cash == 1_000.0
    by = {p.symbol: p for p in plan.positions}
    assert by["AAA"].shares == 10.0 and by["AAA"].avg_cost == 90.0


def test_zero_equity_is_graceful_noop() -> None:
    plan = compute_rebalance(
        cash=0.0,
        current_positions={},
        target_weights={"AAA": 1.0},
        marks={"AAA": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
    )
    assert plan.traded is False
    assert plan.positions == ()
    assert plan.cash == 0.0


def test_rebalance_sells_dropped_symbol_to_zero_and_preserves_avg_cost() -> None:
    # Held AAA(appreciated) + BBB; new target is 100% AAA → BBB sold to zero.
    plan = compute_rebalance(
        cash=0.0,
        current_positions={"AAA": (100.0, 80.0), "BBB": (50.0, 40.0)},
        target_weights={"AAA": 1.0},
        marks={"AAA": 100.0, "BBB": 40.0},
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    by = {p.symbol: p for p in plan.positions}
    assert set(by) == {"AAA"}  # BBB dropped
    # equity = 100*100 + 50*40 = 12000; investable = 12000 (no cost).
    # desired AAA = 12000/100 = 120 sh; was 100 → buy 20 @100.
    assert by["AAA"].shares == pytest.approx(120.0)
    # avg_cost blended: (100*80 + 20*100)/120 = (8000+2000)/120 = 83.333...
    assert by["AAA"].avg_cost == pytest.approx(10_000.0 / 120.0)


def test_cost_is_charged_on_gross_traded_notional() -> None:
    # Pure sell of half a single holding; cost applies to traded notional only.
    plan = compute_rebalance(
        cash=0.0,
        current_positions={"AAA": (100.0, 50.0)},
        target_weights={"AAA": 1.0},
        marks={"AAA": 100.0},
        fee_bps=10.0,
        slippage_bps=0.0,
    )
    # equity = 10000; investable = 10000*(1-0.001)=9990; desired=99.9 sh.
    # delta = -0.1 sh → gross traded = 0.1*100 = 10 → cost = 10*0.001 = 0.01.
    assert plan.traded_notional == pytest.approx(10.0)
    assert plan.cost == pytest.approx(0.01)
