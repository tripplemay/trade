"""B111 F004 — backtest-vs-paper cost caliber reconciliation number."""

from __future__ import annotations

import pytest

from trade.backtest.cost_reconciliation import (
    cost_caliber_comparison,
    rebalance_cost,
)


def test_backtest_is_one_sided_three_bps() -> None:
    # Full swap (turnover 2.0), $100k: buy leg only at 3bps → 3bps of NAV = $30.
    cost = rebalance_cost(100_000.0, 2.0, rate_bps=3.0, both_legs=False)
    assert cost == pytest.approx(30.0)


def test_paper_is_both_legs_ten_bps() -> None:
    # Full swap, $100k: both legs at 10bps → 20bps of NAV = $200.
    cost = rebalance_cost(100_000.0, 2.0, rate_bps=10.0, both_legs=True)
    assert cost == pytest.approx(200.0)


def test_comparison_quantifies_the_full_swap_gap() -> None:
    c = cost_caliber_comparison(100_000.0, 2.0)
    assert c.backtest_cost == pytest.approx(30.0)
    assert c.paper_cost == pytest.approx(200.0)
    assert c.difference == pytest.approx(170.0)
    # The headline: paper cost is ~6.7x the backtest on a full rebalance.
    assert c.ratio == pytest.approx(200.0 / 30.0)
    assert c.backtest_bps_of_nav == pytest.approx(3.0)
    assert c.paper_bps_of_nav == pytest.approx(20.0)


def test_comparison_matches_observed_paper_cost() -> None:
    """The diagnosis measured $419 over 5 weeks / 9 rebalances ≈ $46.6/rebalance
    on a ~$100k book. At paper caliber that implies an average per-rebalance
    turnover well under a full swap — the comparison reproduces the order of
    magnitude the live book actually paid (0.42% NAV over 5 weeks)."""

    per_rebalance = cost_caliber_comparison(100_000.0, 0.47)
    # ~$47 paper cost per rebalance at turnover 0.47 → 9 rebalances ≈ $420.
    assert per_rebalance.paper_cost == pytest.approx(47.0, abs=2.0)
    assert per_rebalance.paper_cost > per_rebalance.backtest_cost


def test_zero_turnover_is_costless_both_calibers() -> None:
    c = cost_caliber_comparison(100_000.0, 0.0)
    assert c.backtest_cost == 0.0 and c.paper_cost == 0.0
    assert c.ratio is None
