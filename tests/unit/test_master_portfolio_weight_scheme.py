"""B106 F001 — Master 组合层扩展:防守腿 barbell + weight_scheme 参数化。

零回归铁律的守门测试住在这里:默认 4-sleeve / fixed 的 ``parameter_hash`` 被钉死为
pre-B106 的字节级金值。任何回归到默认 Master 的行为改动都会让该断言变红。
"""

from __future__ import annotations

import pytest

from trade.portfolio.master import (
    CN_DIVIDEND_LOWVOL_SLEEVE_ID,
    CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    DEFENSIVE_SLEEVE_ROLE_LABEL,
    SLEEVE_TYPE_IMPLEMENTED,
    WEIGHT_SCHEME_FIXED,
    WEIGHT_SCHEME_HRP,
    WEIGHT_SCHEME_RISK_PARITY,
    MasterPortfolioConfigError,
    MasterPortfolioParameters,
    default_master_portfolio_parameters,
    master_portfolio_parameters_with_defensive_barbell,
    resolve_sleeve_weights,
    validate_master_portfolio_parameters,
)

# ★ Pre-B106 default Master parameter_hash (4 sleeves 40/30/20/10, fixed). Captured
# from the committed code BEFORE the weight_scheme field existed. This is the
# byte-identical backward-compat contract: the default Master must never move.
GOLDEN_DEFAULT_PARAMETER_HASH = (
    "726f9ce6a4acd956dcde72f2bc32a9c1633ba5c23acfc359c7533aea6ea7a644"
)


# --- Synthetic sleeve-return series (deterministic, hand-authored) --------------
# Distinct volatilities so inverse-vol / HRP produce a non-degenerate, checkable
# ordering: hk_china is the loudest, cn_dividend_lowvol the quietest.
_SLEEVE_RETURNS: dict[str, tuple[float, ...]] = {
    "momentum": (0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, 0.0, 0.02, -0.01),
    "risk_parity": (
        0.001, -0.001, 0.002, -0.0015, 0.001, -0.0005, 0.001, 0.0, 0.0008, -0.0007,
    ),
    "satellite_us_quality": (
        0.005, -0.01, 0.008, -0.006, 0.004, -0.009, 0.006, 0.001, 0.007, -0.005,
    ),
    "satellite_hk_china": (
        0.02, -0.03, 0.04, -0.025, 0.03, -0.04, 0.02, 0.005, 0.03, -0.02,
    ),
    "cn_dividend_lowvol": (
        0.002, -0.001, 0.0015, -0.0008, 0.001, -0.0005, 0.0012, 0.0003, 0.001, -0.0006,
    ),
}


# ===== ★ 零回归:默认 Master 字节级不变 ==========================================


def test_default_master_parameter_hash_is_byte_identical_to_pre_b106() -> None:
    """The production default must reproduce its pre-B106 hash exactly."""

    assert default_master_portfolio_parameters().parameter_hash() == (
        GOLDEN_DEFAULT_PARAMETER_HASH
    )


def test_default_master_weight_scheme_is_fixed() -> None:
    assert default_master_portfolio_parameters().weight_scheme == WEIGHT_SCHEME_FIXED


def test_default_master_still_has_exactly_four_sleeves() -> None:
    parameters = default_master_portfolio_parameters()
    assert {sleeve.sleeve_id for sleeve in parameters.sleeves} == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }
    assert CN_DIVIDEND_LOWVOL_SLEEVE_ID not in {
        sleeve.sleeve_id for sleeve in parameters.sleeves
    }


def test_explicit_fixed_scheme_hash_equals_omitted_default() -> None:
    """Setting weight_scheme='fixed' explicitly must not perturb the hash."""

    explicit = MasterPortfolioParameters(weight_scheme=WEIGHT_SCHEME_FIXED)
    assert explicit.parameter_hash() == GOLDEN_DEFAULT_PARAMETER_HASH


def test_non_fixed_scheme_changes_hash_but_not_the_default() -> None:
    rp = MasterPortfolioParameters(weight_scheme=WEIGHT_SCHEME_RISK_PARITY)
    hrp = MasterPortfolioParameters(weight_scheme=WEIGHT_SCHEME_HRP)

    assert rp.parameter_hash() != GOLDEN_DEFAULT_PARAMETER_HASH
    assert hrp.parameter_hash() != GOLDEN_DEFAULT_PARAMETER_HASH
    assert rp.parameter_hash() != hrp.parameter_hash()
    # ...and the default helper is still pinned to the golden hash.
    assert default_master_portfolio_parameters().parameter_hash() == (
        GOLDEN_DEFAULT_PARAMETER_HASH
    )


# ===== weight_scheme 校验 ========================================================


def test_validate_rejects_unknown_weight_scheme() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="weight_scheme"):
        validate_master_portfolio_parameters(
            MasterPortfolioParameters(weight_scheme="momentum_tilt")
        )


def test_default_and_barbell_pass_validation() -> None:
    validate_master_portfolio_parameters(default_master_portfolio_parameters())
    validate_master_portfolio_parameters(
        master_portfolio_parameters_with_defensive_barbell()
    )


# ===== 防守腿 barbell 并入 =======================================================


def test_barbell_appends_cn_dividend_lowvol_defensive_sleeve() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    by_id = {sleeve.sleeve_id: sleeve for sleeve in parameters.sleeves}

    assert CN_DIVIDEND_LOWVOL_SLEEVE_ID in by_id
    defensive = by_id[CN_DIVIDEND_LOWVOL_SLEEVE_ID]
    assert defensive.sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert defensive.strategy_id == CN_DIVIDEND_LOWVOL_STRATEGY_ID
    assert defensive.role_label == DEFENSIVE_SLEEVE_ROLE_LABEL


def test_barbell_default_weights_scale_attack_and_sum_to_one() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell(defensive_weight=0.20)
    weights = {sleeve.sleeve_id: sleeve.planning_weight for sleeve in parameters.sleeves}

    # 40/30/20/10 scaled by (1 - 0.20) = 0.80, plus 0.20 defensive.
    assert weights == {
        "momentum": 0.32,
        "risk_parity": 0.24,
        "satellite_us_quality": 0.16,
        "satellite_hk_china": 0.08,
        CN_DIVIDEND_LOWVOL_SLEEVE_ID: 0.20,
    }
    assert round(sum(weights.values()), 10) == 1.0


def test_barbell_preserves_attack_sleeve_relative_proportions() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell(defensive_weight=0.30)
    weights = {sleeve.sleeve_id: sleeve.planning_weight for sleeve in parameters.sleeves}

    assert round(sum(weights.values()), 10) == 1.0
    assert weights[CN_DIVIDEND_LOWVOL_SLEEVE_ID] == 0.30
    # 40:30:20:10 preserved among the attack sleeves after scaling.
    assert weights["momentum"] / weights["satellite_hk_china"] == pytest.approx(4.0)
    assert weights["risk_parity"] / weights["satellite_hk_china"] == pytest.approx(3.0)


def test_barbell_rejects_out_of_range_defensive_weight() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="defensive_weight"):
        master_portfolio_parameters_with_defensive_barbell(defensive_weight=0.0)
    with pytest.raises(MasterPortfolioConfigError, match="defensive_weight"):
        master_portfolio_parameters_with_defensive_barbell(defensive_weight=1.0)


def test_barbell_can_carry_a_non_fixed_scheme() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell(
        weight_scheme=WEIGHT_SCHEME_HRP
    )
    assert parameters.weight_scheme == WEIGHT_SCHEME_HRP


# ===== resolve_sleeve_weights ====================================================


def test_resolve_fixed_is_planning_weight_passthrough() -> None:
    parameters = default_master_portfolio_parameters()
    resolved = resolve_sleeve_weights(WEIGHT_SCHEME_FIXED, parameters.sleeves)

    assert resolved == {
        sleeve.sleeve_id: sleeve.planning_weight for sleeve in parameters.sleeves
    }
    assert round(sum(resolved.values()), 10) == 1.0


def test_resolve_fixed_needs_no_returns() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    # No returns argument at all — fixed must never require price/return data.
    resolved = resolve_sleeve_weights(WEIGHT_SCHEME_FIXED, parameters.sleeves)
    assert round(sum(resolved.values()), 10) == 1.0


@pytest.mark.parametrize("scheme", [WEIGHT_SCHEME_RISK_PARITY, WEIGHT_SCHEME_HRP])
def test_resolve_risk_schemes_sum_to_one_and_cover_all_sleeves(scheme: str) -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    resolved = resolve_sleeve_weights(scheme, parameters.sleeves, _SLEEVE_RETURNS)

    assert set(resolved) == {sleeve.sleeve_id for sleeve in parameters.sleeves}
    assert round(sum(resolved.values()), 10) == 1.0
    assert all(weight >= 0.0 for weight in resolved.values())


def test_resolve_risk_parity_favours_low_volatility_sleeves() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    resolved = resolve_sleeve_weights(
        WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves, _SLEEVE_RETURNS
    )

    # cn_dividend_lowvol / risk_parity are the quietest series → largest weights;
    # satellite_hk_china is the loudest → smallest weight. This is the inverse-vol
    # contract inherited from risk_parity_vol_target.
    assert resolved["satellite_hk_china"] == min(resolved.values())
    assert resolved[CN_DIVIDEND_LOWVOL_SLEEVE_ID] > resolved["satellite_hk_china"]


def test_resolve_risk_parity_matches_reused_inverse_vol_primitive() -> None:
    """Pin the sleeve-layer weights to the reused risk_parity primitive so the two
    can never silently diverge."""

    import statistics
    from math import sqrt

    from trade.strategies.risk_parity import (
        VolatilityEstimate,
        _inverse_volatility_weights,
    )

    parameters = master_portfolio_parameters_with_defensive_barbell()
    resolved = resolve_sleeve_weights(
        WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves, _SLEEVE_RETURNS
    )

    estimates = [
        VolatilityEstimate(
            symbol=sleeve.sleeve_id,
            lookback=len(_SLEEVE_RETURNS[sleeve.sleeve_id]),
            annualized_volatility=statistics.stdev(_SLEEVE_RETURNS[sleeve.sleeve_id])
            * sqrt(252.0),
            observations=len(_SLEEVE_RETURNS[sleeve.sleeve_id]),
            end_date=__import__("datetime").date(1970, 1, 1),
        )
        for sleeve in parameters.sleeves
    ]
    expected = _inverse_volatility_weights(estimates)
    for sleeve_id, weight in expected.items():
        assert resolved[sleeve_id] == pytest.approx(weight)


def test_resolve_unknown_scheme_raises() -> None:
    parameters = default_master_portfolio_parameters()
    with pytest.raises(MasterPortfolioConfigError, match="weight_scheme"):
        resolve_sleeve_weights("sharpe_max", parameters.sleeves)


def test_resolve_non_fixed_without_returns_fails_loud() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    with pytest.raises(MasterPortfolioConfigError, match="return series"):
        resolve_sleeve_weights(WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves)


def test_resolve_missing_sleeve_return_series_fails_loud() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    partial = dict(_SLEEVE_RETURNS)
    partial.pop(CN_DIVIDEND_LOWVOL_SLEEVE_ID)
    with pytest.raises(MasterPortfolioConfigError, match="missing return series"):
        resolve_sleeve_weights(WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves, partial)


def test_resolve_risk_parity_rejects_flat_sleeve() -> None:
    parameters = master_portfolio_parameters_with_defensive_barbell()
    flat = dict(_SLEEVE_RETURNS)
    flat[CN_DIVIDEND_LOWVOL_SLEEVE_ID] = (0.0,) * 10  # zero variance
    with pytest.raises(MasterPortfolioConfigError, match="non-positive volatility"):
        resolve_sleeve_weights(WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves, flat)


def test_resolve_too_short_series_fails_loud() -> None:
    parameters = default_master_portfolio_parameters()
    short = {sleeve.sleeve_id: (0.01,) for sleeve in parameters.sleeves}
    with pytest.raises(MasterPortfolioConfigError, match=">= 2 return observations"):
        resolve_sleeve_weights(WEIGHT_SCHEME_RISK_PARITY, parameters.sleeves, short)
