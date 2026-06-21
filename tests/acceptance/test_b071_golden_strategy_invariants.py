"""B071 F004 — permanent acceptance invariants (pure-engine, golden-backed).

"验收即代码": the recurring real-data behaviour invariants the evaluator used to
re-verify by hand each batch, frozen here as permanent CI regressions on the
committed golden fixture. Each invariant has teeth (F005 mutation-checks it:
break the invariant → this test must go red).

Pure-engine invariants (no DB) live here; the DB / recommendation-chain
invariants live in ``workbench/backend/tests/acceptance/``. The golden strategy
harness comes from the ``tests/`` root conftest (shared with F003).

Invariants covered here:
  ① ★ N strategies, same window, pairwise-distinct (B050 recurring reversal)
  ② target weights + cash buffer sum to 1 (master + us_quality, every period)
  ⑤ Master backwards-compat: canonical 4-sleeve composition + regime default
"""

from __future__ import annotations

import itertools


# ── ① N strategies pairwise-distinct ─────────────────────────────────────────
def test_n_strategies_pairwise_distinct_on_golden(
    golden_strategy_results, golden_strategy_names
) -> None:
    """B050: N strategies over the same golden window must be pairwise
    different. Mutation check: feed any two engines the same data/params and
    this goes red."""
    endings = {name: res.ending_value for name, res in golden_strategy_results.items()}
    for left, right in itertools.combinations(golden_strategy_names, 2):
        assert endings[left] != endings[right], (
            f"{left} == {right} ending_value {endings[left]} — strategies not distinct"
        )


# ── ② weights (+ cash buffer) sum to 1 ───────────────────────────────────────
def test_us_quality_weights_plus_cash_sum_to_one_every_period(
    golden_strategy_results,
) -> None:
    result = golden_strategy_results["us_quality"]
    assert result.rebalance_periods, "us_quality produced no rebalance periods on golden"
    for period in result.rebalance_periods:
        total = sum(period.target_weights.values()) + period.cash_buffer
        assert abs(total - 1.0) < 1e-6, (
            f"us_quality {period.signal_date}: weights+cash={total} != 1.0"
        )


def test_master_portfolio_target_weights_sum_to_one_every_period(
    golden_strategy_results,
) -> None:
    result = golden_strategy_results["master"]
    assert result.rebalance_results, "master produced no rebalance results on golden"
    for period in result.rebalance_results:
        total = sum(period.portfolio_target_weights.values())
        # The master target is a fully-invested (or defensive) book; allow the
        # tiny rounding the per-sleeve aggregation introduces.
        assert abs(total - 1.0) < 1e-3, (
            f"master {period.signal_date}: portfolio weights sum {total} != 1.0"
        )


# ── ⑤ Master backwards-compat ────────────────────────────────────────────────
_CANONICAL_SLEEVE_PLANNING_WEIGHTS = {
    "momentum": 0.40,
    "risk_parity": 0.30,
    "satellite_us_quality": 0.20,
    "satellite_hk_china": 0.10,
}


def test_master_keeps_canonical_four_sleeve_composition(golden_strategy_results) -> None:
    """The documented Master composition (4 sleeves, planning weights
    0.4/0.3/0.2/0.1) must not drift — golden master reproduces it every
    period. Mutation check: change any planning weight → red."""
    result = golden_strategy_results["master"]
    for period in result.rebalance_results:
        planning = {
            contribution.sleeve_id: round(contribution.planning_weight, 10)
            for contribution in period.sleeve_contributions
        }
        assert planning == _CANONICAL_SLEEVE_PLANNING_WEIGHTS, (
            f"master {period.signal_date}: sleeve composition drifted to {planning}"
        )
        assert abs(sum(planning.values()) - 1.0) < 1e-9


def test_regime_adaptive_default_policy_stays_always_on() -> None:
    """B015 backwards-compat: the regime-adaptive default activation policy
    must stay ALWAYS_ON so existing Master backtests are unchanged by the
    regime layer. Mutation check: flip the default → red."""
    from trade.strategies.regime_adaptive.config import (
        POLICY_ALWAYS_ON,
        default_regime_adaptive_config,
    )

    assert default_regime_adaptive_config().regime_activation_policy == POLICY_ALWAYS_ON
