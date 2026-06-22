"""B066 F001 — unit tests for CnAttackParameters validation + variant mapping."""

from __future__ import annotations

import hashlib
import json

import pytest

from trade.strategies.cn_attack_momentum_quality.parameters import (
    DEFAULT_SIZE_TILT_WEIGHT,
    DEFAULT_WEIGHTING_SCHEME,
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    SIZE_FACTOR_KEY,
    WEIGHTING_SCHEME_EQUAL,
    WEIGHTING_SCHEME_INVERSE_VOL,
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


# --------------------------------------------------------------------------- #
# B068 F002 — weighting_scheme (the second A/B dimension)
# --------------------------------------------------------------------------- #


def test_weighting_scheme_defaults_to_equal() -> None:
    # B066/B067 backward compatibility: the default must be equal (1/N).
    assert CnAttackParameters().weighting_scheme == WEIGHTING_SCHEME_EQUAL
    assert DEFAULT_WEIGHTING_SCHEME == WEIGHTING_SCHEME_EQUAL


def test_inverse_vol_weighting_scheme_accepted() -> None:
    params = CnAttackParameters(weighting_scheme=WEIGHTING_SCHEME_INVERSE_VOL)
    assert params.weighting_scheme == "inverse_vol"


def test_unknown_weighting_scheme_rejected() -> None:
    with pytest.raises(CnAttackParameterError, match="weighting_scheme"):
        CnAttackParameters(weighting_scheme="risk_parity")


def test_equal_default_hash_is_byte_identical_to_pre_b068() -> None:
    # Zero-regression proof: the equal-default hash equals the hash of the
    # pre-B068 payload (which had NO weighting_scheme key). The conditional payload
    # in parameter_hash() guarantees B066/B067's recorded identifier never churns.
    params = CnAttackParameters()
    pre_b068_payload = {
        "factor_variant": params.factor_variant,
        "max_position_weight": params.max_position_weight,
        "momentum_weight": params.momentum_weight,
        "quality_weight": params.quality_weight,
        "rebalance_frequency": params.rebalance_frequency,
        "strategy_id": params.strategy_id,
        "top_n": params.top_n,
    }
    canonical = json.dumps(pre_b068_payload, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert params.parameter_hash() == expected


def test_parameter_hash_is_weighting_scheme_sensitive() -> None:
    equal = CnAttackParameters(weighting_scheme=WEIGHTING_SCHEME_EQUAL)
    inv = CnAttackParameters(weighting_scheme=WEIGHTING_SCHEME_INVERSE_VOL)
    # Explicit equal == default (so the default path's identifier is stable)...
    assert equal.parameter_hash() == CnAttackParameters().parameter_hash()
    # ...but inverse_vol gets its own identifier.
    assert inv.parameter_hash() != equal.parameter_hash()
    assert len(inv.parameter_hash()) == 64


# --------------------------------------------------------------------------- #
# B076 F001 — size_tilt_weight (the third A/B dimension; small-cap tilt)
# --------------------------------------------------------------------------- #


def test_size_tilt_defaults_to_zero() -> None:
    # Zero-regression: the production default must be 0 (no size factor at all).
    assert CnAttackParameters().size_tilt_weight == 0.0
    assert DEFAULT_SIZE_TILT_WEIGHT == 0.0


def test_size_tilt_zero_mapping_has_no_size_factor() -> None:
    # weight 0 → the mapping is byte-identical to the pre-B076 mapping (no "size" key),
    # so the production default never scores / loads market cap.
    qm = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        momentum_weight=0.5,
        quality_weight=0.5,
    )
    assert qm.factor_weight_mapping() == {"momentum": 0.5, "quality": 0.5}
    pure = CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM)
    assert pure.factor_weight_mapping() == {"momentum": 1.0}


def test_size_tilt_renormalizes_quality_momentum_and_sums_to_one() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        momentum_weight=0.5,
        quality_weight=0.5,
        size_tilt_weight=0.2,
    )
    mapping = params.factor_weight_mapping()
    # base weights scaled by (1 - 0.2)=0.8 + size=0.2 → still sums to 1.0.
    assert mapping == pytest.approx({"momentum": 0.4, "quality": 0.4, SIZE_FACTOR_KEY: 0.2})
    assert sum(mapping.values()) == pytest.approx(1.0)


def test_size_tilt_renormalizes_pure_momentum_and_sums_to_one() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, size_tilt_weight=0.3
    )
    mapping = params.factor_weight_mapping()
    assert mapping == pytest.approx({"momentum": 0.7, SIZE_FACTOR_KEY: 0.3})
    assert sum(mapping.values()) == pytest.approx(1.0)


def test_size_tilt_out_of_range_rejected() -> None:
    with pytest.raises(CnAttackParameterError, match="size_tilt_weight"):
        CnAttackParameters(size_tilt_weight=1.0)  # pure size is degenerate
    with pytest.raises(CnAttackParameterError, match="size_tilt_weight"):
        CnAttackParameters(size_tilt_weight=-0.1)


def test_size_tilt_zero_hash_is_byte_identical_to_default() -> None:
    # Explicit 0 == default (the recorded identifier never churns when the knob is off).
    assert (
        CnAttackParameters(size_tilt_weight=0.0).parameter_hash()
        == CnAttackParameters().parameter_hash()
    )


def test_parameter_hash_is_size_tilt_sensitive() -> None:
    tilted = CnAttackParameters(size_tilt_weight=0.2)
    assert tilted.parameter_hash() != CnAttackParameters().parameter_hash()
    assert len(tilted.parameter_hash()) == 64
    # Two different tilt levels get two different identifiers.
    assert (
        CnAttackParameters(size_tilt_weight=0.2).parameter_hash()
        != CnAttackParameters(size_tilt_weight=0.4).parameter_hash()
    )
