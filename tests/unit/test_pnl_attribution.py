"""B018 F001 — unit tests for trade.analysis.pnl_attribution.

Canned backtest snapshots + canned benchmark curves drive each test so the
expected arithmetic is fully deterministic and reviewable.
"""

from __future__ import annotations

from datetime import date

import pytest

from trade.analysis.pnl_attribution import (
    B010_LAYERS,
    B013_LAYERS,
    AttributionInput,
    AttributionReport,
    PeriodAttribution,
    attribution_summary,
    compute_per_asset_contribution,
    compute_per_layer_contribution,
    compute_period_asset_returns,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _approx(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= tol


def _make_two_period_b013_input(
    *,
    risk_returns_period_1: dict[str, float],
    risk_returns_period_2: dict[str, float],
    defensive_return_period_1: float,
    defensive_return_period_2: float,
    weights_period_1: dict[str, float],
    weights_period_2: dict[str, float],
    parked_by_layer_period_1: dict[str, float],
    parked_by_layer_period_2: dict[str, float],
    base_defensive_share: float = 0.0,
    starting_capital: float = 100_000.0,
) -> AttributionInput:
    asset_returns_period_1 = dict(risk_returns_period_1)
    asset_returns_period_1["SGOV"] = defensive_return_period_1
    asset_returns_period_2 = dict(risk_returns_period_2)
    asset_returns_period_2["SGOV"] = defensive_return_period_2
    return AttributionInput(
        strategy="b013",
        starting_capital=starting_capital,
        layer_names=B013_LAYERS,
        periods=(
            PeriodAttribution(
                signal_date=date(2024, 1, 31),
                starting_value=starting_capital,
                target_weights=weights_period_1,
                asset_returns=asset_returns_period_1,
                parked_by_layer=parked_by_layer_period_1,
                base_defensive_share=base_defensive_share,
                defensive_asset="SGOV",
            ),
            PeriodAttribution(
                signal_date=date(2024, 2, 29),
                starting_value=starting_capital,
                target_weights=weights_period_2,
                asset_returns=asset_returns_period_2,
                parked_by_layer=parked_by_layer_period_2,
                base_defensive_share=base_defensive_share,
                defensive_asset="SGOV",
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# Per-asset contribution — sign correctness
# --------------------------------------------------------------------------- #


def test_per_asset_contribution_positive_when_asset_gains() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.5, "AGG": 0.5},
        asset_returns={"SPY": 0.02, "AGG": 0.01},
        defensive_asset=None,
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    assert _approx(contributions["SPY"], 100_000.0 * 0.5 * 0.02)
    assert contributions["SPY"] > 0
    assert _approx(contributions["AGG"], 100_000.0 * 0.5 * 0.01)
    assert contributions["AGG"] > 0


def test_per_asset_contribution_negative_when_asset_loses() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.6, "VWO": 0.4},
        asset_returns={"SPY": 0.015, "VWO": -0.03},
    )
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(period,),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    assert contributions["SPY"] > 0
    assert contributions["VWO"] < 0
    assert _approx(contributions["VWO"], 100_000.0 * 0.4 * -0.03)


def test_per_asset_contribution_aggregates_across_periods() -> None:
    p1 = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.02},
    )
    p2 = PeriodAttribution(
        signal_date=date(2024, 2, 29),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": -0.01},
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(p1, p2),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    expected = 100_000.0 * 1.0 * 0.02 + 100_000.0 * 1.0 * -0.01
    assert _approx(contributions["SPY"], expected)


def test_per_asset_skips_zero_capital_periods() -> None:
    p1 = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=0.0,  # kill switch effective
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.05},
    )
    p2 = PeriodAttribution(
        signal_date=date(2024, 2, 29),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.02},
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(p1, p2),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    assert _approx(contributions["SPY"], 100_000.0 * 1.0 * 0.02)


def test_per_asset_missing_return_treated_as_zero() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.5, "WHEREAMI": 0.5},
        asset_returns={"SPY": 0.02},  # no entry for WHEREAMI
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    assert _approx(contributions["SPY"], 100_000.0 * 0.5 * 0.02)
    assert _approx(contributions["WHEREAMI"], 0.0)


def test_per_asset_handles_single_asset_universe() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.012},
        defensive_asset=None,
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    contributions = compute_per_asset_contribution(attribution_input)

    assert tuple(contributions.keys()) == ("SPY",)
    assert _approx(contributions["SPY"], 100_000.0 * 1.0 * 0.012)


def test_per_asset_empty_input_returns_empty_dict() -> None:
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(),
    )

    assert compute_per_asset_contribution(attribution_input) == {}


# --------------------------------------------------------------------------- #
# Per-layer contribution
# --------------------------------------------------------------------------- #


def test_per_layer_b010_drag_when_capital_parked_to_defensive() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.8, "SGOV": 0.2},
        asset_returns={"SPY": 0.02, "SGOV": 0.001},
        parked_by_layer={"l2_vol_scaling": 0.2},
        base_defensive_share=0.0,
        defensive_asset="SGOV",
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    # avg_risk_return = 0.02 (only SPY is non-defensive); defensive_return = 0.001;
    # differential = 0.001 - 0.02 = -0.019. l2 attribution = 100_000 * 0.2 * -0.019 = -380.
    assert _approx(layer_contrib["l2_vol_scaling"], 100_000.0 * 0.2 * (0.001 - 0.02))
    assert layer_contrib["l2_vol_scaling"] < 0
    # B010 has no base defensive sleeve; routing layer reports zero.
    assert layer_contrib["defensive_routing"] == 0.0


def test_per_layer_b013_each_layer_signed_independently() -> None:
    risk_returns = {"SPY": 0.02, "AGG": 0.005}
    defensive_return = 0.001
    attribution_input = _make_two_period_b013_input(
        risk_returns_period_1=risk_returns,
        risk_returns_period_2=risk_returns,
        defensive_return_period_1=defensive_return,
        defensive_return_period_2=defensive_return,
        weights_period_1={"SPY": 0.4, "AGG": 0.4, "SGOV": 0.2},
        weights_period_2={"SPY": 0.4, "AGG": 0.4, "SGOV": 0.2},
        parked_by_layer_period_1={
            "l1_gating": 0.05,
            "l2_vol_scaling": 0.10,
            "l3_crisis_cut": 0.00,
        },
        parked_by_layer_period_2={
            "l1_gating": 0.05,
            "l2_vol_scaling": 0.10,
            "l3_crisis_cut": 0.05,
        },
        base_defensive_share=0.0,
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    # avg_risk_return = (0.4*0.02 + 0.4*0.005)/0.8 = 0.0125; diff = 0.001 - 0.0125 = -0.0115.
    diff = 0.001 - 0.0125
    expected_l1 = 100_000.0 * 0.05 * diff + 100_000.0 * 0.05 * diff
    expected_l2 = 100_000.0 * 0.10 * diff + 100_000.0 * 0.10 * diff
    expected_l3 = 100_000.0 * 0.00 * diff + 100_000.0 * 0.05 * diff
    assert _approx(layer_contrib["l1_gating"], expected_l1)
    assert _approx(layer_contrib["l2_vol_scaling"], expected_l2)
    assert _approx(layer_contrib["l3_crisis_cut"], expected_l3)
    assert layer_contrib["l1_gating"] < 0
    assert layer_contrib["l2_vol_scaling"] < layer_contrib["l1_gating"]  # larger drag


def test_per_layer_defensive_routing_uses_base_defensive_share() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.7, "AGG": 0.2, "SGOV": 0.1},
        asset_returns={"SPY": 0.02, "AGG": 0.004, "SGOV": 0.001},
        parked_by_layer={"l1_gating": 0.0, "l2_vol_scaling": 0.0, "l3_crisis_cut": 0.0},
        base_defensive_share=0.1,
        defensive_asset="SGOV",
    )
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(period,),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    # avg_risk_return = (0.7 * 0.02 + 0.2 * 0.004) / 0.9; diff = 0.001 - that.
    risk_total_weight = 0.7 + 0.2
    avg_risk = (0.7 * 0.02 + 0.2 * 0.004) / risk_total_weight
    diff = 0.001 - avg_risk
    assert _approx(layer_contrib["defensive_routing"], 100_000.0 * 0.1 * diff)
    assert layer_contrib["defensive_routing"] < 0
    assert layer_contrib["l1_gating"] == 0.0
    assert layer_contrib["l2_vol_scaling"] == 0.0
    assert layer_contrib["l3_crisis_cut"] == 0.0


def test_per_layer_sum_approximately_matches_total_gap_in_canned_aligned_case() -> None:
    # Construct a canned case where benchmark return per period matches the
    # strategy's avg-risk return at full exposure (so the "risk picking" gap
    # is zero by construction), and benchmark vs strategy starting capital
    # match. Then the per-layer sum should exactly equal total_gap.
    risk_returns = {"SPY": 0.02, "AGG": 0.005}
    starting_capital = 100_000.0
    weights_post_routing = {"SPY": 0.4, "AGG": 0.4, "SGOV": 0.2}
    parked_layers = {"l1_gating": 0.0, "l2_vol_scaling": 0.2, "l3_crisis_cut": 0.0}

    attribution_input = _make_two_period_b013_input(
        risk_returns_period_1=risk_returns,
        risk_returns_period_2=risk_returns,
        defensive_return_period_1=0.001,
        defensive_return_period_2=0.001,
        weights_period_1=weights_post_routing,
        weights_period_2=weights_post_routing,
        parked_by_layer_period_1=parked_layers,
        parked_by_layer_period_2=parked_layers,
        base_defensive_share=0.0,
        starting_capital=starting_capital,
    )

    # Avg risk return at full exposure = (1.0 * 0.02 + 1.0 * 0.005) / 2 if equal-weight; but
    # in our weights the pre-park risk allocation is (0.4 + 0.4 + 0.2 parked) = full risk
    # universe of SPY+AGG. We compute that explicitly here for the benchmark curve.
    avg_risk_at_full = (0.5 * 0.02 + 0.5 * 0.005)  # equal-weight at full exposure
    # Build a benchmark equity curve that earns exactly avg_risk_at_full each period.
    benchmark_curve: tuple[tuple[date, float], ...] = (
        (date(2024, 1, 31), 100_000.0),
        (date(2024, 2, 29), 100_000.0 * (1 + avg_risk_at_full) ** 2),
    )

    report = attribution_summary(attribution_input, benchmark_curve)
    per_layer_sum = sum(report.per_layer_contribution.values())

    # The two layers' contributions should aggregate to (roughly) the drag in
    # the strategy's parked allocation vs the benchmark. Approximate equality
    # within $50 on a 100K base is well within the linear-vs-compounding gap.
    assert abs(per_layer_sum - report.total_gap) <= max(50.0, abs(report.total_gap) * 0.10)


def test_per_layer_empty_input_returns_zero_for_each_layer() -> None:
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    assert set(layer_contrib.keys()) == set(B013_LAYERS)
    for value in layer_contrib.values():
        assert value == 0.0


def test_per_layer_zero_capital_periods_contribute_nothing() -> None:
    p_dead = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=0.0,
        target_weights={"SPY": 0.5, "SGOV": 0.5},
        asset_returns={"SPY": 0.05, "SGOV": 0.0},
        parked_by_layer={"l2_vol_scaling": 0.5},
        defensive_asset="SGOV",
    )
    p_live = PeriodAttribution(
        signal_date=date(2024, 2, 29),
        starting_value=100_000.0,
        target_weights={"SPY": 0.8, "SGOV": 0.2},
        asset_returns={"SPY": 0.02, "SGOV": 0.001},
        parked_by_layer={"l2_vol_scaling": 0.2},
        defensive_asset="SGOV",
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(p_dead, p_live),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    expected = 100_000.0 * 0.2 * (0.001 - 0.02)
    assert _approx(layer_contrib["l2_vol_scaling"], expected)


# --------------------------------------------------------------------------- #
# attribution_summary
# --------------------------------------------------------------------------- #


def test_attribution_summary_reports_total_gap_strategy_minus_benchmark() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.05},
        defensive_asset=None,
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )
    benchmark_curve: tuple[tuple[date, float], ...] = (
        (date(2024, 1, 31), 100_000.0),
        (date(2024, 2, 1), 110_000.0),
    )

    report = attribution_summary(attribution_input, benchmark_curve)

    assert isinstance(report, AttributionReport)
    # Strategy compounds 100_000 by 1 period of 5% return → 105_000.
    assert _approx(report.strategy_ending, 105_000.0)
    # Benchmark is flat between period start and end (single observation at
    # signal_date); benchmark_ending equals starting_capital scaled by 0
    # since end is the same date.
    expected_gap = report.strategy_ending - report.benchmark_ending
    assert _approx(report.total_gap, expected_gap)


def test_attribution_summary_handles_missing_benchmark_dates() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.02},
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    # Empty benchmark curve — should fall back to starting_capital.
    report = attribution_summary(attribution_input, benchmark_curve=())

    assert _approx(report.benchmark_ending, 100_000.0)
    # Strategy still computed normally.
    assert _approx(report.strategy_ending, 102_000.0)


def test_attribution_summary_with_no_periods_returns_starting_capital_for_strategy() -> None:
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(),
    )

    report = attribution_summary(attribution_input, benchmark_curve=())

    assert _approx(report.strategy_ending, 100_000.0)
    assert _approx(report.benchmark_ending, 100_000.0)
    assert _approx(report.total_gap, 0.0)
    assert report.per_asset_contribution == {}
    assert set(report.per_layer_contribution.keys()) == set(B013_LAYERS)


def test_attribution_summary_carries_strategy_label_through() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.01},
    )
    attribution_input = AttributionInput(
        strategy="b013",
        starting_capital=100_000.0,
        layer_names=B013_LAYERS,
        periods=(period,),
    )

    report = attribution_summary(attribution_input, benchmark_curve=())

    assert report.strategy == "b013"
    assert report.starting_capital == 100_000.0


# --------------------------------------------------------------------------- #
# compute_period_asset_returns helper
# --------------------------------------------------------------------------- #


def test_compute_period_asset_returns_uses_at_or_before_observation() -> None:
    prices: dict[str, list[tuple[date, float]]] = {
        "SPY": [
            (date(2024, 1, 31), 100.0),
            (date(2024, 2, 29), 105.0),
            (date(2024, 3, 31), 110.0),
        ],
        "AGG": [
            (date(2024, 1, 31), 100.0),
            (date(2024, 2, 29), 101.0),
            (date(2024, 3, 31), 100.5),
        ],
    }
    boundaries = [
        (date(2024, 1, 31), date(2024, 2, 29)),
        (date(2024, 2, 29), date(2024, 3, 31)),
    ]

    returns = compute_period_asset_returns(prices, boundaries)

    assert len(returns) == 2
    assert _approx(returns[0]["SPY"], 0.05)
    assert _approx(returns[0]["AGG"], 0.01)
    assert _approx(returns[1]["SPY"], 110.0 / 105.0 - 1.0)
    assert _approx(returns[1]["AGG"], 100.5 / 101.0 - 1.0)


def test_compute_period_asset_returns_omits_assets_with_missing_observations() -> None:
    prices: dict[str, list[tuple[date, float]]] = {
        "SPY": [
            (date(2024, 1, 31), 100.0),
            (date(2024, 2, 29), 105.0),
        ],
        # Empty AGG history — must not appear in the returns dict.
        "AGG": [],
    }
    boundaries = [(date(2024, 1, 31), date(2024, 2, 29))]

    returns = compute_period_asset_returns(prices, boundaries)

    assert returns == [{"SPY": pytest.approx(0.05)}]


def test_compute_period_asset_returns_handles_pre_history_target_dates() -> None:
    """Asking for a boundary before the price history start uses the earliest
    observation as both endpoints, yielding a flat 0% return."""

    prices: dict[str, list[tuple[date, float]]] = {
        "SPY": [
            (date(2024, 6, 1), 100.0),
            (date(2024, 7, 1), 110.0),
        ],
    }
    boundaries = [(date(2024, 1, 1), date(2024, 5, 1))]

    returns = compute_period_asset_returns(prices, boundaries)

    assert _approx(returns[0]["SPY"], 0.0)


# --------------------------------------------------------------------------- #
# Defensive-asset filtering in _avg_risk_return through public surface
# --------------------------------------------------------------------------- #


def test_per_layer_attribution_filters_defensive_asset_from_avg_risk() -> None:
    """When defensive asset is named, the avg_risk_return computation must
    exclude it. Without exclusion, a heavy SGOV weight would dilute the
    risk-side baseline and flip the sign of the layer attribution."""

    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.4, "AGG": 0.4, "SGOV": 0.2},
        asset_returns={"SPY": 0.02, "AGG": 0.005, "SGOV": 0.001},
        parked_by_layer={"l2_vol_scaling": 0.2},
        defensive_asset="SGOV",
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    # avg_risk should be (0.4*0.02 + 0.4*0.005)/(0.4+0.4) = 0.0125. Not influenced by SGOV.
    expected = 100_000.0 * 0.2 * (0.001 - 0.0125)
    # Sanity: had we accidentally included SGOV in avg_risk, the differential
    # would have been (0.001 - 0.0103) instead of (0.001 - 0.0125), yielding
    # ~$214 instead of ~$230 — distinguishable.
    assert _approx(layer_contrib["l2_vol_scaling"], expected)


# --------------------------------------------------------------------------- #
# Period without defensive asset — graceful fallback
# --------------------------------------------------------------------------- #


def test_period_with_no_defensive_asset_uses_zero_defensive_return() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 1.0},
        asset_returns={"SPY": 0.02},
        parked_by_layer={"l2_vol_scaling": 0.1},
        defensive_asset=None,
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    layer_contrib = compute_per_layer_contribution(attribution_input, benchmark_curve=())

    # With no defensive asset, defensive_return defaults to 0.0; avg_risk = 0.02;
    # diff = 0.0 - 0.02 = -0.02; cost = 100_000 * 0.1 * -0.02 = -200.
    assert _approx(layer_contrib["l2_vol_scaling"], -200.0)


# --------------------------------------------------------------------------- #
# Single-period sanity: total per-asset roughly equals strategy_ending - capital
# --------------------------------------------------------------------------- #


def test_per_asset_sum_matches_strategy_return_in_single_period_case() -> None:
    period = PeriodAttribution(
        signal_date=date(2024, 1, 31),
        starting_value=100_000.0,
        target_weights={"SPY": 0.5, "AGG": 0.3, "SGOV": 0.2},
        asset_returns={"SPY": 0.02, "AGG": 0.005, "SGOV": 0.001},
        defensive_asset="SGOV",
    )
    attribution_input = AttributionInput(
        strategy="b010",
        starting_capital=100_000.0,
        layer_names=B010_LAYERS,
        periods=(period,),
    )

    contributions = compute_per_asset_contribution(attribution_input)
    report = attribution_summary(attribution_input, benchmark_curve=())

    total_contribution = sum(contributions.values())
    strategy_dollar_return = report.strategy_ending - report.starting_capital
    assert _approx(total_contribution, strategy_dollar_return)
