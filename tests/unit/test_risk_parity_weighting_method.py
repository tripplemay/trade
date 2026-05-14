"""B016 F001 — weighting_method Literal tightening + __post_init__ validation."""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest

from trade.strategies.risk_parity import (
    VALID_WEIGHTING_METHODS,
    RiskParityConfigError,
    RiskParityParameters,
)


def test_default_weighting_method_is_inverse_volatility() -> None:
    parameters = RiskParityParameters()

    assert parameters.weighting_method == "inverse_volatility"
    assert "inverse_volatility" in VALID_WEIGHTING_METHODS


def test_inverse_volatility_value_is_accepted() -> None:
    parameters = RiskParityParameters(weighting_method="inverse_volatility")

    assert parameters.weighting_method == "inverse_volatility"


def test_hrp_value_is_accepted() -> None:
    parameters = RiskParityParameters(weighting_method="hrp")

    assert parameters.weighting_method == "hrp"


@pytest.mark.parametrize(
    "invalid_value",
    [
        "equal_risk_contribution",
        "min_variance",
        "INVERSE_VOLATILITY",
        "HRP",
        "",
        "hrp ",
        " hrp",
        "inverse-volatility",
    ],
)
def test_invalid_weighting_method_rejected_with_diagnostic(invalid_value: str) -> None:
    with pytest.raises(RiskParityConfigError) as excinfo:
        RiskParityParameters(weighting_method=invalid_value)  # type: ignore[arg-type]

    message = str(excinfo.value)
    assert "weighting_method" in message
    assert "inverse_volatility" in message
    assert "hrp" in message
    assert repr(invalid_value) in message or invalid_value in message


def test_valid_choices_listed_in_error_message() -> None:
    with pytest.raises(RiskParityConfigError) as excinfo:
        RiskParityParameters(weighting_method="bogus")  # type: ignore[arg-type]

    message = str(excinfo.value)
    for choice in VALID_WEIGHTING_METHODS:
        assert choice in message


def test_parameter_hash_distinct_across_valid_weighting_methods() -> None:
    inverse_vol = RiskParityParameters(weighting_method="inverse_volatility")
    hrp = RiskParityParameters(weighting_method="hrp")

    assert inverse_vol.parameter_hash() != hrp.parameter_hash()


def test_parameter_hash_stable_for_repeated_inverse_volatility() -> None:
    first = RiskParityParameters(weighting_method="inverse_volatility")
    second = RiskParityParameters(weighting_method="inverse_volatility")

    assert first.parameter_hash() == second.parameter_hash()


def test_parameter_hash_stable_for_repeated_hrp() -> None:
    first = RiskParityParameters(weighting_method="hrp")
    second = RiskParityParameters(weighting_method="hrp")

    assert first.parameter_hash() == second.parameter_hash()


def test_default_parameter_hash_unchanged_when_only_other_fields_match() -> None:
    # Backwards-compat sanity: the B010 default config (no explicit weighting_method)
    # must still hash identically to an explicit weighting_method='inverse_volatility'
    # config (same field value), so existing B010 fixtures keep producing the same hash.
    implicit = RiskParityParameters()
    explicit = RiskParityParameters(weighting_method="inverse_volatility")

    assert implicit.parameter_hash() == explicit.parameter_hash()


def test_asdict_serialization_round_trip_inverse_volatility() -> None:
    original = RiskParityParameters(weighting_method="inverse_volatility")

    payload = asdict(original)
    payload["universe"] = tuple(payload["universe"])
    payload["supported_lookbacks"] = tuple(payload["supported_lookbacks"])
    restored = RiskParityParameters(**payload)

    assert restored == original
    assert restored.weighting_method == "inverse_volatility"
    assert restored.parameter_hash() == original.parameter_hash()


def test_asdict_serialization_round_trip_hrp() -> None:
    original = RiskParityParameters(weighting_method="hrp")

    payload = asdict(original)
    payload["universe"] = tuple(payload["universe"])
    payload["supported_lookbacks"] = tuple(payload["supported_lookbacks"])
    restored = RiskParityParameters(**payload)

    assert restored == original
    assert restored.weighting_method == "hrp"
    assert restored.parameter_hash() == original.parameter_hash()


def test_json_round_trip_preserves_weighting_method() -> None:
    for method in VALID_WEIGHTING_METHODS:
        original = RiskParityParameters(weighting_method=method)
        payload = asdict(original)
        json_blob = json.dumps(payload)
        decoded = json.loads(json_blob)
        decoded["universe"] = tuple(decoded["universe"])
        decoded["supported_lookbacks"] = tuple(decoded["supported_lookbacks"])
        restored = RiskParityParameters(**decoded)

        assert restored == original
        assert restored.weighting_method == method


def test_replace_to_hrp_preserves_other_fields() -> None:
    original = RiskParityParameters()
    switched = replace(original, weighting_method="hrp")

    assert switched.weighting_method == "hrp"
    assert switched.universe == original.universe
    assert switched.volatility_lookback == original.volatility_lookback
    assert switched.target_volatility == original.target_volatility
    assert switched.parameter_hash() != original.parameter_hash()


def test_replace_to_invalid_value_rejected() -> None:
    original = RiskParityParameters()
    with pytest.raises(RiskParityConfigError) as excinfo:
        replace(original, weighting_method="bogus")  # type: ignore[arg-type]

    assert "weighting_method" in str(excinfo.value)
