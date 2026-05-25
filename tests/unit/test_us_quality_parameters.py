"""Unit tests for the B025 strategy parameter bundle."""

from __future__ import annotations

import pytest

from trade.strategies.us_quality_momentum.parameters import (
    DEFAULT_STRATEGY_ID,
    DEFAULT_TOP_N,
    FactorWeights,
    ParameterValidationError,
    UsQualityMomentumParameters,
)


def test_default_parameters_match_spec_acceptance() -> None:
    params = UsQualityMomentumParameters()
    assert params.strategy_id == DEFAULT_STRATEGY_ID == "us_quality_momentum"
    assert params.top_n == DEFAULT_TOP_N == 15
    assert params.factor_weights.momentum == 0.35
    assert params.factor_weights.quality == 0.30
    assert params.factor_weights.low_vol == 0.15
    assert params.factor_weights.value == 0.10
    assert params.factor_weights.trend == 0.10
    assert params.max_position_weight == 0.07
    assert params.max_sector_weight == 0.30
    assert params.earnings_window_days == 5
    assert params.rebalance_frequency == "monthly"


def test_parameter_hash_is_deterministic_and_64_chars() -> None:
    first = UsQualityMomentumParameters().parameter_hash()
    second = UsQualityMomentumParameters().parameter_hash()
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_parameter_hash_changes_when_any_field_changes() -> None:
    base = UsQualityMomentumParameters().parameter_hash()
    new_top = UsQualityMomentumParameters(top_n=20).parameter_hash()
    # 15 × 0.08 = 1.20 stays above the cap-reachable floor.
    new_cap = UsQualityMomentumParameters(max_position_weight=0.08).parameter_hash()
    new_weights = UsQualityMomentumParameters(
        factor_weights=FactorWeights(
            momentum=0.40, quality=0.25, low_vol=0.15, value=0.10, trend=0.10
        )
    ).parameter_hash()
    distinct = {base, new_top, new_cap, new_weights}
    assert len(distinct) == 4


def test_factor_weights_must_sum_to_one() -> None:
    with pytest.raises(ParameterValidationError, match="sum to 1.0"):
        FactorWeights(momentum=0.5, quality=0.5, low_vol=0.5, value=0.0, trend=0.0)


def test_factor_weights_reject_negative_components() -> None:
    with pytest.raises(ParameterValidationError, match="must be >= 0"):
        FactorWeights(
            momentum=-0.1, quality=0.40, low_vol=0.30, value=0.20, trend=0.20
        )


def test_top_n_must_allow_full_deployment_under_position_cap() -> None:
    # top_n=10 × max_position_weight=0.07 = 0.70 < 1.0 → cash buffer always >0.
    with pytest.raises(ParameterValidationError, match="cap is unreachable"):
        UsQualityMomentumParameters(top_n=10)


def test_invalid_rebalance_frequency_rejected() -> None:
    with pytest.raises(ParameterValidationError, match="rebalance_frequency"):
        UsQualityMomentumParameters(rebalance_frequency="weekly")


def test_invalid_position_cap_rejected() -> None:
    with pytest.raises(ParameterValidationError, match="max_position_weight"):
        UsQualityMomentumParameters(max_position_weight=0.0)
    with pytest.raises(ParameterValidationError, match="max_position_weight"):
        UsQualityMomentumParameters(max_position_weight=1.5)
