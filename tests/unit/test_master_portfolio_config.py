import pytest

from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    SLEEVE_TYPE_SATELLITE_STUB,
    MasterPortfolioConfigError,
    MasterPortfolioParameters,
    MasterSleeveConfig,
    default_master_portfolio_parameters,
    validate_master_portfolio_parameters,
)


def test_default_master_portfolio_combines_two_core_sleeves_and_two_satellite_stubs() -> None:
    parameters = default_master_portfolio_parameters()
    sleeves_by_id = {sleeve.sleeve_id: sleeve for sleeve in parameters.sleeves}

    assert set(sleeves_by_id) == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }
    assert sleeves_by_id["momentum"].sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert sleeves_by_id["momentum"].strategy_id == "global_etf_momentum"
    assert sleeves_by_id["risk_parity"].sleeve_type == SLEEVE_TYPE_IMPLEMENTED
    assert sleeves_by_id["risk_parity"].strategy_id == "risk_parity_vol_target"
    assert sleeves_by_id["satellite_us_quality"].sleeve_type == SLEEVE_TYPE_SATELLITE_STUB
    assert sleeves_by_id["satellite_us_quality"].strategy_id is None
    assert sleeves_by_id["satellite_hk_china"].sleeve_type == SLEEVE_TYPE_SATELLITE_STUB
    assert sleeves_by_id["satellite_hk_china"].strategy_id is None


def test_default_master_portfolio_planning_weights_match_strategy_doc() -> None:
    parameters = default_master_portfolio_parameters()
    weights = {sleeve.sleeve_id: sleeve.planning_weight for sleeve in parameters.sleeves}

    assert weights == {
        "momentum": 0.40,
        "risk_parity": 0.30,
        "satellite_us_quality": 0.20,
        "satellite_hk_china": 0.10,
    }
    assert round(sum(weights.values()), 8) == 1.0


def test_default_master_portfolio_uses_quarterly_rebalance_and_15pct_drawdown() -> None:
    parameters = default_master_portfolio_parameters()

    assert parameters.rebalance_frequency == "quarterly"
    assert parameters.drawdown_threshold == 0.15
    assert parameters.human_review_required_on_trigger is True


def test_default_master_portfolio_forbids_leverage() -> None:
    parameters = default_master_portfolio_parameters()

    assert parameters.max_exposure == 1.0


def test_default_master_portfolio_defensive_asset_matches_risk_parity_default() -> None:
    parameters = default_master_portfolio_parameters()

    assert parameters.defensive_asset == "SGOV"


def test_default_master_portfolio_parameter_hash_is_deterministic_and_64_chars() -> None:
    first = default_master_portfolio_parameters().parameter_hash()
    second = default_master_portfolio_parameters().parameter_hash()

    assert first == second
    assert len(first) == 64


def test_master_portfolio_rejects_leverage_above_one() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="leverage"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(max_exposure=1.5))


def test_master_portfolio_rejects_non_positive_max_exposure() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="max_exposure"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(max_exposure=0.0))


def test_master_portfolio_rejects_non_quarterly_rebalance() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="quarterly"):
        validate_master_portfolio_parameters(
            MasterPortfolioParameters(rebalance_frequency="monthly")
        )


def test_master_portfolio_rejects_weights_not_summing_to_one() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="momentum",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="global_etf_momentum",
            planning_weight=0.5,
            role_label="core_trend_engine",
        ),
        MasterSleeveConfig(
            sleeve_id="risk_parity",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="risk_parity_vol_target",
            planning_weight=0.3,
            role_label="core_stabilizer",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="sum to 1.0"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))


def test_master_portfolio_rejects_unknown_sleeve_type() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="foo",
            sleeve_type="exotic_type",
            strategy_id=None,
            planning_weight=1.0,
            role_label="role",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="sleeve_type"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))


def test_master_portfolio_rejects_implemented_sleeve_without_strategy_id() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="solo",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id=None,
            planning_weight=1.0,
            role_label="role",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="strategy_id"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))


def test_master_portfolio_rejects_satellite_stub_with_strategy_id() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="stub",
            sleeve_type=SLEEVE_TYPE_SATELLITE_STUB,
            strategy_id="some_strategy",
            planning_weight=1.0,
            role_label="role",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="satellite_stub"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))


def test_master_portfolio_rejects_negative_drawdown_threshold() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="drawdown_threshold"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(drawdown_threshold=-0.05))


def test_master_portfolio_rejects_drawdown_threshold_above_one() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="drawdown_threshold"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(drawdown_threshold=1.5))


def test_master_portfolio_rejects_empty_sleeves() -> None:
    with pytest.raises(MasterPortfolioConfigError, match="sleeves"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=()))


def test_master_portfolio_rejects_duplicate_sleeve_ids() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="dup",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="global_etf_momentum",
            planning_weight=0.5,
            role_label="role",
        ),
        MasterSleeveConfig(
            sleeve_id="dup",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="risk_parity_vol_target",
            planning_weight=0.5,
            role_label="role",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="duplicate"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))


def test_master_portfolio_rejects_negative_planning_weight() -> None:
    bad_sleeves = (
        MasterSleeveConfig(
            sleeve_id="momentum",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="global_etf_momentum",
            planning_weight=-0.1,
            role_label="role",
        ),
        MasterSleeveConfig(
            sleeve_id="risk_parity",
            sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
            strategy_id="risk_parity_vol_target",
            planning_weight=1.1,
            role_label="role",
        ),
    )
    with pytest.raises(MasterPortfolioConfigError, match="planning_weight"):
        validate_master_portfolio_parameters(MasterPortfolioParameters(sleeves=bad_sleeves))
