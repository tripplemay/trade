"""B082 F002 — unit tests for CnDividendLowvolParameters (frozen, spec-先验 thresholds)."""

from __future__ import annotations

import dataclasses

import pytest

from trade.strategies.cn_dividend_lowvol.parameters import (
    FULL_WEIGHT,
    HALF_SPREAD_PCT,
    HALF_WEIGHT,
    LOW_WEIGHT,
    SATURATED_SPREAD_PCT,
    CnDividendLowvolParameterError,
    CnDividendLowvolParameters,
)


def test_defaults_are_spec_prior_thresholds() -> None:
    params = CnDividendLowvolParameters()
    # ★ The焊死 three-tier rule (spec §0/§3): 2.5% / 1.5% thresholds, 100/50/25% weights.
    assert params.saturated_spread_pct == 2.5 == SATURATED_SPREAD_PCT
    assert params.half_spread_pct == 1.5 == HALF_SPREAD_PCT
    assert params.full_weight == 1.0 == FULL_WEIGHT
    assert params.half_weight == 0.5 == HALF_WEIGHT
    assert params.low_weight == 0.25 == LOW_WEIGHT
    assert params.dividend_yield_lookback_days == 252


def test_parameters_are_frozen_immutable() -> None:
    params = CnDividendLowvolParameters()
    # Immutability invariant: thresholds cannot be mutated in place.
    with pytest.raises(dataclasses.FrozenInstanceError):
        params.saturated_spread_pct = 3.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("spread", "expected"),
    [
        (8.0, 1.0),      # very wide → 满配
        (2.5, 1.0),      # exact saturated boundary → 满配 (>=)
        (2.49, 0.5),     # just below saturated → 半配
        (2.0, 0.5),      # mid band → 半配
        (1.5, 0.5),      # exact half boundary → 半配 (>=)
        (1.49, 0.25),    # just below half → 低配
        (-3.0, 0.25),    # negative spread → 低配
    ],
)
def test_three_tier_boundaries_are_exact(spread: float, expected: float) -> None:
    params = CnDividendLowvolParameters()
    assert params.target_weight_for_spread(spread) == expected


def test_nan_spread_maps_to_low_tier_not_full() -> None:
    params = CnDividendLowvolParameters()
    # Insufficient history → conservative LOW default, never a silent full allocation.
    assert params.target_weight_for_spread(float("nan")) == params.low_weight


def test_inverted_thresholds_rejected() -> None:
    with pytest.raises(CnDividendLowvolParameterError):
        CnDividendLowvolParameters(saturated_spread_pct=1.0, half_spread_pct=1.5)


def test_non_monotone_weights_rejected() -> None:
    with pytest.raises(CnDividendLowvolParameterError):
        # low > half violates the "wider spread never maps to a smaller allocation" ladder.
        CnDividendLowvolParameters(low_weight=0.9, half_weight=0.5)


def test_parameter_hash_is_deterministic_and_changes_with_config() -> None:
    base = CnDividendLowvolParameters()
    assert base.parameter_hash() == CnDividendLowvolParameters().parameter_hash()
    assert len(base.parameter_hash()) == 64
    # A different (hypothetical) bundle hashes differently — the identifier is faithful.
    other = CnDividendLowvolParameters(low_weight=0.30)
    assert other.parameter_hash() != base.parameter_hash()
