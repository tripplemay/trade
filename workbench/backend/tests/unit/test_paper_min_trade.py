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


# --- B111-F006-3 fix-round regression: cash-feasible sizing after min-trade ---


def test_skipped_sells_scale_buy_down_proportionally() -> None:
    """When skipped dust sells leave the buy side unaffordable, the buy legs
    are scaled down proportionally (not clamped): cash lands at ~0, the scale
    factor is surfaced on the plan, and cost is charged on the SCALED trades."""

    # 6 x $10k book + $50 cash; +$105 top-up on S0 vs five $55 dust trims
    # (below the $60 min) → only $50 honestly funds the $105 buy → scale ~0.48.
    investable = 60_050.0 * (1.0 - 0.001) - 60_000.0 * 0.001
    desired_values = [10_105.0] + [9_945.0] * 5
    plan = compute_rebalance(
        cash=50.0,
        current_positions={f"S{i}": (10_000.0, 1.0) for i in range(6)},
        target_weights={
            f"S{i}": desired_value / investable
            for i, desired_value in enumerate(desired_values)
        },
        marks={f"S{i}": 1.0 for i in range(6)},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,  # $60.05 min → the $55 trims are dust
    )
    assert 0.0 < plan.buy_scale_factor < 1.0  # visible scale-down, not a clamp
    assert plan.cash >= 0.0
    assert plan.cash < 1.0  # fully deployed to what is honestly fundable
    held = {p.symbol: p.shares for p in plan.positions}
    # Partial fill: S0 grew, but by less than the full $105 top-up.
    assert 10_000.0 < held["S0"] < 10_105.0
    # The five trimmed names are untouched (dust sells skipped).
    for i in range(1, 6):
        assert held[f"S{i}"] == 10_000.0
    # Cost is charged on the scaled gross traded notional.
    assert plan.cost == plan.traded_notional * 0.001


def test_unfundable_buy_is_dropped_entirely_at_zero_cash() -> None:
    """cash=0 + every sell skipped as dust → the buy scales to 0 and the book
    simply holds; cash stays exactly 0 (no negative, no fabricated funding)."""

    investable = 60_000.0 * (1.0 - 0.001) - 60_000.0 * 0.001
    desired_values = [10_105.0] + [9_945.0] * 5
    plan = compute_rebalance(
        cash=0.0,
        current_positions={f"S{i}": (10_000.0, 1.0) for i in range(6)},
        target_weights={
            f"S{i}": desired_value / investable
            for i, desired_value in enumerate(desired_values)
        },
        marks={f"S{i}": 1.0 for i in range(6)},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,  # $60 min → the $55 trims are dust
    )
    assert plan.cash == 0.0
    assert plan.buy_scale_factor == 0.0
    # Nothing traded: every position is held at its current shares.
    held = {p.symbol: p.shares for p in plan.positions}
    assert held == {f"S{i}": 10_000.0 for i in range(6)}


def test_fully_affordable_rebalance_never_scales() -> None:
    """Zero-regression: when the trades are affordable, no scaling happens
    (scale stays exactly 1.0 and the book reaches full target size)."""

    plan = compute_rebalance(
        cash=10_000.0,
        current_positions={"AAA": (50.0, 100.0)},
        target_weights={"AAA": 0.5, "BBB": 0.5},
        marks={"AAA": 100.0, "BBB": 100.0},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,
    )
    assert plan.buy_scale_factor == 1.0
    assert plan.cash >= 0.0


def test_preexisting_negative_cash_sells_back_to_non_negative() -> None:
    """Production recovery path (B111-F006-3): an account STARTING at the
    bug's −$18.94 with an on-target book (every trim is dust) must still heal
    — dust sells are exempt from min-trade while cash < 0, so the align sells
    the book down to the cash-feasible size and lands cash ≥ 0."""

    # 6 x ~$16,672 positions ≈ on target, cash −18.94 (the production shape):
    # every per-name trim is below the $100 min-trade, yet cash must recover.
    plan = compute_rebalance(
        cash=-18.944156,
        current_positions={f"S{i}": (16_672.0, 1.0) for i in range(6)},
        target_weights={f"S{i}": 1 / 6 for i in range(6)},
        marks={f"S{i}": 1.0 for i in range(6)},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,  # ~$100 min on the ~$100k book
    )
    assert plan.cash >= 0.0
    assert plan.traded_notional > 0.0  # dust sells executed to heal


def test_min_trade_skipped_sells_cannot_fund_executed_buy() -> None:
    """Skipped dust sells must not leave an above-threshold buy unfunded.

    Production reproduced this on 2026-08-01: several sub-threshold sells were
    held while a larger buy executed, moving Master paper cash from $60.25 to
    -$18.94. The six-name fixture is the smallest deterministic shape of that
    failure: one $105 buy executes while five $61 sells are skipped.
    """

    equity = 100_000.0
    current_value = equity / 6.0
    investable = equity * (1.0 - 0.001) - equity * 0.001
    desired_values = [current_value + 105.0] + [current_value - 61.0] * 5

    plan = compute_rebalance(
        cash=0.0,
        current_positions={f"S{i}": (current_value, 1.0) for i in range(6)},
        target_weights={
            f"S{i}": desired_value / investable
            for i, desired_value in enumerate(desired_values)
        },
        marks={f"S{i}": 1.0 for i in range(6)},
        fee_bps=5.0,
        slippage_bps=5.0,
        min_trade_fraction=0.001,
    )

    assert plan.cash >= 0.0
