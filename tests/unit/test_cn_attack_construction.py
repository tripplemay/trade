"""B066 F001 — unit tests for CN attack portfolio construction + variant A/B."""

from __future__ import annotations

import pandas as pd
import pytest

from trade.strategies.cn_attack_momentum_quality.construction import (
    CnConstructionError,
    build_cn_portfolio,
)
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    WEIGHTING_SCHEME_INVERSE_VOL,
    CnAttackParameters,
)

# 6 candidates. T6 has the HIGHEST momentum but NO quality data (NaN), so it is
# kept by pure_momentum and dropped by quality_momentum — the A/B fork.
_ELIGIBLE = ("T1", "T2", "T3", "T4", "T5", "T6")
_MOMENTUM = pd.Series(
    {"T1": 0.90, "T2": 0.80, "T3": 0.70, "T4": 0.60, "T5": 0.50, "T6": 0.95}
)
_QUALITY = pd.Series(
    {"T1": 0.10, "T2": 0.90, "T3": 0.80, "T4": 0.70, "T5": 0.60}  # T6 absent → NaN
)


def _scores(*, with_quality: bool) -> dict[str, pd.Series]:
    scores = {"momentum": _MOMENTUM.copy()}
    if with_quality:
        scores["quality"] = _QUALITY.copy()
    return scores


def test_pure_momentum_keeps_top_momentum_including_no_quality_name() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    portfolio = build_cn_portfolio(_scores(with_quality=False), _ELIGIBLE, params)
    # ranked by momentum: T6(.95), T1(.90), T2(.80)
    assert set(portfolio.tickers()) == {"T6", "T1", "T2"}


def test_quality_momentum_drops_no_quality_name() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        top_n=3,
        max_position_weight=0.5,
        momentum_weight=0.5,
        quality_weight=0.5,
    )
    portfolio = build_cn_portfolio(_scores(with_quality=True), _ELIGIBLE, params)
    # T6 (NaN quality) is filtered out by the quality requirement.
    assert "T6" not in portfolio.tickers()


def test_variants_select_different_baskets() -> None:
    pure = build_cn_portfolio(
        _scores(with_quality=False),
        _ELIGIBLE,
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
        ),
    )
    blended = build_cn_portfolio(
        _scores(with_quality=True),
        _ELIGIBLE,
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
            top_n=3,
            max_position_weight=0.5,
            momentum_weight=0.5,
            quality_weight=0.5,
        ),
    )
    # The whole point of the A/B test: the two variants pick different names.
    assert set(pure.tickers()) != set(blended.tickers())


def test_equal_weight_sums_to_one_when_cap_not_binding() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=5, max_position_weight=0.5
    )
    portfolio = build_cn_portfolio(_scores(with_quality=False), _ELIGIBLE, params)
    assert len(portfolio.tickers()) == 5
    assert portfolio.total_invested() == pytest.approx(1.0, abs=1e-9)
    assert portfolio.cash_buffer == pytest.approx(0.0, abs=1e-9)
    weights = list(portfolio.as_dict().values())
    assert all(w == pytest.approx(0.2) for w in weights)


def test_position_cap_binds_and_leaves_cash_when_few_candidates() -> None:
    # top_n large, but only 3 candidates have data → equal weight 1/3 > 8% cap.
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=25, max_position_weight=0.08
    )
    scores = {"momentum": pd.Series({"T1": 0.9, "T2": 0.8, "T3": 0.7})}
    portfolio = build_cn_portfolio(scores, ("T1", "T2", "T3"), params)
    assert len(portfolio.tickers()) == 3
    assert all(w == pytest.approx(0.08) for w in portfolio.as_dict().values())
    assert portfolio.total_invested() == pytest.approx(0.24, abs=1e-9)
    assert portfolio.cash_buffer == pytest.approx(0.76, abs=1e-9)


def test_restricts_to_eligible_universe() -> None:
    # A high-momentum name outside the eligible universe must never be selected.
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    scores = {"momentum": pd.Series({"T1": 0.9, "OUTSIDER": 0.99, "T2": 0.8, "T3": 0.7})}
    portfolio = build_cn_portfolio(scores, ("T1", "T2", "T3"), params)
    assert "OUTSIDER" not in portfolio.tickers()
    assert set(portfolio.tickers()) == {"T1", "T2", "T3"}


def test_out_of_universe_name_does_not_shift_in_universe_weights() -> None:
    # Rank invariance: an out-of-universe name in the factor frame must not change
    # the in-universe selection OR its weights — the cross-sectional rank
    # denominator is the universe (construction restricts before ranking).
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    base = build_cn_portfolio(
        {"momentum": pd.Series({"T1": 0.9, "T2": 0.8, "T3": 0.7})},
        ("T1", "T2", "T3"),
        params,
    )
    polluted = build_cn_portfolio(
        {"momentum": pd.Series({"T1": 0.9, "OUTSIDER": 0.99, "T2": 0.8, "T3": 0.7})},
        ("T1", "T2", "T3"),
        params,
    )
    assert base.as_dict() == polluted.as_dict()


def test_top_n_truncates() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=2, max_position_weight=0.6
    )
    portfolio = build_cn_portfolio(_scores(with_quality=False), _ELIGIBLE, params)
    assert len(portfolio.tickers()) == 2
    assert set(portfolio.tickers()) == {"T6", "T1"}  # two highest momentum


def test_empty_eligible_raises() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    with pytest.raises(CnConstructionError, match="at least one ticker"):
        build_cn_portfolio(_scores(with_quality=False), (), params)


def test_missing_factor_score_raises() -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        top_n=3,
        max_position_weight=0.5,
        momentum_weight=0.5,
        quality_weight=0.5,
    )
    # quality_momentum needs a "quality" series; omitting it is a wiring error.
    with pytest.raises(CnConstructionError, match="missing required keys"):
        build_cn_portfolio({"momentum": _MOMENTUM.copy()}, _ELIGIBLE, params)


# --------------------------------------------------------------------------- #
# B068 F002 — inverse-volatility weighting (the spec's 2nd A/B dimension)
# --------------------------------------------------------------------------- #

# pure_momentum top_n=3 selects {T6(.95), T1(.90), T2(.80)}. T2 has the LOWEST σ
# → the highest 1/σ weight; T6 the highest σ → the lowest weight.
_VOLS = pd.Series({"T6": 0.40, "T1": 0.20, "T2": 0.10})


def _inv_vol_params(*, max_position_weight: float = 0.6) -> CnAttackParameters:
    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
        top_n=3,
        max_position_weight=max_position_weight,
        weighting_scheme=WEIGHTING_SCHEME_INVERSE_VOL,
    )


def test_inverse_vol_weights_favor_low_volatility_names() -> None:
    portfolio = build_cn_portfolio(
        _scores(with_quality=False), _ELIGIBLE, _inv_vol_params(), volatilities=_VOLS
    )
    w = portfolio.as_dict()
    assert set(portfolio.tickers()) == {"T6", "T1", "T2"}
    # 1/σ ordering: lowest-σ T2 > T1 > highest-σ T6.
    assert w["T2"] > w["T1"] > w["T6"]
    # Quantitative: weights ∝ 1/σ = {T6:2.5, T1:5, T2:10}, total 17.5.
    assert w["T2"] == pytest.approx(10.0 / 17.5, abs=1e-6)
    assert w["T1"] == pytest.approx(5.0 / 17.5, abs=1e-6)
    assert w["T6"] == pytest.approx(2.5 / 17.5, abs=1e-6)
    assert portfolio.total_invested() == pytest.approx(1.0, abs=1e-9)


def test_inverse_vol_same_basket_as_equal_only_weights_differ() -> None:
    # Q2 isolation: inverse_vol must pick the SAME names as equal so the comparison
    # measures the weighting effect, not a composition change.
    common = dict(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.6
    )
    equal = build_cn_portfolio(
        _scores(with_quality=False), _ELIGIBLE, CnAttackParameters(**common)
    )
    inv = build_cn_portfolio(
        _scores(with_quality=False),
        _ELIGIBLE,
        CnAttackParameters(**common, weighting_scheme=WEIGHTING_SCHEME_INVERSE_VOL),
        volatilities=_VOLS,
    )
    assert set(equal.tickers()) == set(inv.tickers())
    assert equal.as_dict() != inv.as_dict()
    # equal is 1/3 each; inverse_vol is tilted.
    assert all(v == pytest.approx(1.0 / 3.0) for v in equal.as_dict().values())


def test_inverse_vol_imputes_median_sigma_for_missing_name() -> None:
    # T1 has no σ → imputed the cross-sectional median of {T6:0.40, T2:0.10}=0.25;
    # the name is KEPT (composition matches equal), not dropped.
    vols = pd.Series({"T6": 0.40, "T2": 0.10})
    portfolio = build_cn_portfolio(
        _scores(with_quality=False),
        _ELIGIBLE,
        _inv_vol_params(max_position_weight=0.8),  # loose cap → imputed weight visible
        volatilities=vols,
    )
    w = portfolio.as_dict()
    assert set(portfolio.tickers()) == {"T6", "T1", "T2"}
    # T1 imputed σ=0.25 → 1/σ=4; T6=2.5, T2=10 → total 16.5.
    assert w["T1"] == pytest.approx(4.0 / 16.5, abs=1e-6)
    assert w["T2"] == pytest.approx(10.0 / 16.5, abs=1e-6)


def test_inverse_vol_degrades_to_equal_when_no_usable_sigma() -> None:
    params = _inv_vol_params()
    none_port = build_cn_portfolio(
        _scores(with_quality=False), _ELIGIBLE, params, volatilities=None
    )
    invalid = pd.Series({"T6": float("nan"), "T1": 0.0, "T2": -1.0})
    nan_port = build_cn_portfolio(
        _scores(with_quality=False), _ELIGIBLE, params, volatilities=invalid
    )
    for portfolio in (none_port, nan_port):
        assert all(v == pytest.approx(1.0 / 3.0) for v in portfolio.as_dict().values())


def test_inverse_vol_cap_binds_and_leaves_cash() -> None:
    # An ultra-low-σ name's 1/σ weight exceeds the cap → capped, excess → cash
    # (same post-processing as equal weighting).
    vols = pd.Series({"T6": 1.0, "T1": 1.0, "T2": 0.01})
    portfolio = build_cn_portfolio(
        _scores(with_quality=False),
        _ELIGIBLE,
        _inv_vol_params(max_position_weight=0.5),
        volatilities=vols,
    )
    w = portfolio.as_dict()
    # T2 pre-cap ≈ 100/102 ≈ 0.98 > 0.5 cap → capped to 0.5; excess → cash buffer.
    assert w["T2"] == pytest.approx(0.5)
    assert portfolio.cash_buffer > 0.0
