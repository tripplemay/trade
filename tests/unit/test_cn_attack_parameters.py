"""B066 F001 — unit tests for CnAttackParameters validation + variant mapping."""

from __future__ import annotations

import pytest

from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    CnAttackParameterError,
    CnAttackParameters,
)


def test_defaults_are_attack_spec_shaped() -> None:
    params = CnAttackParameters()
    assert params.factor_variant == FACTOR_VARIANT_QUALITY_MOMENTUM
    assert params.top_n == 25  # spec "top 20-30"
    assert params.max_position_weight == 0.08  # spec single-name cap


def test_quality_momentum_mapping_blends_both_factors() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        momentum_weight=0.6,
        quality_weight=0.4,
    )
    assert params.factor_weight_mapping() == {"momentum": 0.6, "quality": 0.4}


def test_pure_momentum_mapping_is_momentum_only() -> None:
    params = CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM)
    # quality_weight is ignored — the mapping forces momentum=1.0 and omits quality
    # so names without fundamentals stay eligible.
    assert params.factor_weight_mapping() == {"momentum": 1.0}


def test_pure_momentum_ignores_weight_sum() -> None:
    # weights need not sum to 1.0 for pure_momentum (they are unused).
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
        momentum_weight=0.2,
        quality_weight=0.2,
    )
    assert params.factor_weight_mapping() == {"momentum": 1.0}


def test_quality_momentum_weights_must_sum_to_one() -> None:
    with pytest.raises(CnAttackParameterError, match="sum to 1.0"):
        CnAttackParameters(momentum_weight=0.6, quality_weight=0.6)


def test_unknown_variant_rejected() -> None:
    with pytest.raises(CnAttackParameterError, match="factor_variant"):
        CnAttackParameters(factor_variant="value_tilt")


def test_unreachable_cap_rejected() -> None:
    # top_n * max_position_weight < 1.0 → post-cap weights can never sum to one.
    with pytest.raises(CnAttackParameterError, match="cap is unreachable"):
        CnAttackParameters(top_n=5, max_position_weight=0.08)


def test_max_position_weight_bounds() -> None:
    with pytest.raises(CnAttackParameterError, match="max_position_weight"):
        CnAttackParameters(max_position_weight=0.0)
    with pytest.raises(CnAttackParameterError, match="max_position_weight"):
        CnAttackParameters(max_position_weight=1.5)


def test_parameter_hash_is_deterministic_and_variant_sensitive() -> None:
    a = CnAttackParameters(factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM)
    b = CnAttackParameters(factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM)
    c = CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM)
    assert a.parameter_hash() == b.parameter_hash()
    assert len(a.parameter_hash()) == 64
    assert a.parameter_hash() != c.parameter_hash()
