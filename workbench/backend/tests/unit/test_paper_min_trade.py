"""B111 F004 regression: the paper engine's minimum-trade threshold.

Diagnosis §1.4/§6 F5: the live master book churned $17-level dust orders on
tiny drift. ``compute_rebalance`` now skips a per-name trade smaller than
``equity × min_trade_fraction`` (holding the position at its current level),
while still executing real changes and full closes. Default ``0.0`` is a no-op,
so activation and every existing caller are unchanged.
"""

from __future__ import annotations

from workbench_api.paper.engine import compute_rebalance


def test_min_trade_zero_is_noop_full_realignment() -> None:
    """Default (0.0) still fully re-aligns to target — backward compatible."""

    plan = compute_rebalance(
        cash=0.0,
        current_positions={"AAA": (100.0, 100.0), "BBB": (100.0, 100.0)},
        target_weights={"AAA": 0.5, "BBB": 0.5},
        marks={"AAA": 100.0, "BBB": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
    )
    # Cost reservation drives desired slightly below current → a tiny trade fires.
    assert plan.traded_notional > 0.0


def test_min_trade_skips_dust_drift() -> None:
    """A near-target rebalance whose per-name trades are below the threshold is
    skipped entirely — the positions are held, no cost, no churn."""

    plan = compute_rebalance(
        cash=0.0,
        current_positions={"AAA": (100.0, 100.0), "BBB": (100.0, 100.0)},
        target_weights={"AAA": 0.5, "BBB": 0.5},
        marks={"AAA": 100.0, "BBB": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.02,  # $400 min on a $20k book — the ~$20 drift is dust
    )
    held = {p.symbol: p.shares for p in plan.positions}
    assert held == {"AAA": 100.0, "BBB": 100.0}
    assert plan.traded_notional == 0.0
    assert plan.cost == 0.0
    assert plan.cash == 0.0


def test_min_trade_exempts_full_close_of_small_position() -> None:
    """A stale name the target dropped still exits even if the closing trade is
    below the threshold — only DUST rebalancing is suppressed, not exits."""

    plan = compute_rebalance(
        cash=0.0,
        current_positions={"AAA": (100.0, 100.0), "BBB": (2.0, 100.0)},
        target_weights={"AAA": 1.0},  # BBB dropped
        marks={"AAA": 100.0, "BBB": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.05,  # $510 min — both the AAA top-up and BBB close are < that
    )
    held = {p.symbol: p.shares for p in plan.positions}
    assert "BBB" not in held  # small close is exempt → BBB exits
    assert held["AAA"] == 100.0  # the sub-threshold AAA top-up is skipped


def test_min_trade_still_executes_real_change() -> None:
    """A genuine, above-threshold reallocation still trades in full."""

    plan = compute_rebalance(
        cash=10_000.0,
        current_positions={"AAA": (50.0, 100.0)},
        target_weights={"AAA": 0.5, "BBB": 0.5},
        marks={"AAA": 100.0, "BBB": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,  # $15 min on a ~$15k book
    )
    held = {p.symbol: p.shares for p in plan.positions}
    assert "BBB" in held and held["BBB"] > 0  # the large BBB buy executes
    assert plan.traded_notional > 0.0
    assert plan.cash >= 0.0


def test_min_trade_never_overdraws_cash() -> None:
    """Skipping small trades must never drive cash negative (B078 invariant)."""

    plan = compute_rebalance(
        cash=100.0,
        current_positions={f"S{i}": (100.0, 100.0) for i in range(15)},
        target_weights={f"S{i}": 1 / 15 for i in range(15)},
        marks={f"S{i}": 100.0 for i in range(15)},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.01,
    )
    assert plan.cash >= 0.0
