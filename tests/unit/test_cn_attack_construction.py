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
