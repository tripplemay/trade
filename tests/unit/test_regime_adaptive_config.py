from dataclasses import replace

import pytest

from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    ASSET_CATEGORY_RISK_CORE,
    ASSET_CATEGORY_STABILIZER,
    VALID_ASSET_CATEGORIES,
    AssetEntry,
    RegimeAdaptiveConfig,
    RegimeAdaptiveConfigError,
    default_regime_adaptive_config,
    validate_regime_adaptive_config,
)


def _default() -> RegimeAdaptiveConfig:
    return default_regime_adaptive_config()


def test_default_regime_adaptive_config_universe_carries_nine_classified_assets() -> None:
    config = _default()
    by_symbol = {entry.symbol: entry for entry in config.universe}

    assert set(by_symbol) == {"SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC", "SGOV"}
    assert {"SPY", "QQQ", "VEA", "VWO"} == {
        entry.symbol
        for entry in config.universe
        if entry.category == ASSET_CATEGORY_RISK_CORE
    }
    assert {"IEF", "TLT", "GLD", "DBC"} == {
        entry.symbol
        for entry in config.universe
        if entry.category == ASSET_CATEGORY_STABILIZER
    }
    assert {"SGOV"} == {
        entry.symbol for entry in config.universe if entry.category == ASSET_CATEGORY_DEFENSIVE
    }


def test_default_regime_adaptive_config_parameter_defaults_match_spec() -> None:
    config = _default()

    assert config.trend_window_days == 200
    assert config.vol_lookback_days == 120
    assert config.target_volatility == pytest.approx(0.08)
    assert config.regime_fast_vol_window_days == 20
    assert config.regime_slow_vol_window_days == 120
    assert config.regime_crisis_ratio == pytest.approx(1.5)
    assert config.regime_spy_symbol == "SPY"
    assert config.regime_crisis_exposure_scale == pytest.approx(0.5)
    assert config.tolerance_band == pytest.approx(0.03)
    assert config.account_drawdown_threshold == pytest.approx(0.15)
    assert config.max_exposure == pytest.approx(1.0)
    assert config.defensive_symbol == "SGOV"


def test_default_regime_adaptive_config_parameter_hash_is_deterministic_64_chars() -> None:
    first = _default().parameter_hash()
    second = _default().parameter_hash()

    assert first == second
    assert len(first) == 64


def test_valid_asset_categories_constant_matches_spec() -> None:
    expected = frozenset(
        {ASSET_CATEGORY_RISK_CORE, ASSET_CATEGORY_STABILIZER, ASSET_CATEGORY_DEFENSIVE}
    )
    assert expected == VALID_ASSET_CATEGORIES


def test_validate_regime_adaptive_config_rejects_leverage() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="leverage"):
        validate_regime_adaptive_config(replace(_default(), max_exposure=1.5))


def test_validate_regime_adaptive_config_rejects_non_positive_max_exposure() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="max_exposure"):
        validate_regime_adaptive_config(replace(_default(), max_exposure=0.0))


def test_validate_regime_adaptive_config_rejects_universe_without_risk_core() -> None:
    config = replace(
        _default(),
        universe=(
            AssetEntry(symbol="SGOV", category=ASSET_CATEGORY_DEFENSIVE),
            AssetEntry(symbol="IEF", category=ASSET_CATEGORY_STABILIZER),
        ),
    )
    with pytest.raises(RegimeAdaptiveConfigError, match="risk_core"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_universe_without_defensive() -> None:
    config = replace(
        _default(),
        universe=(
            AssetEntry(symbol="SPY", category=ASSET_CATEGORY_RISK_CORE),
            AssetEntry(symbol="IEF", category=ASSET_CATEGORY_STABILIZER),
        ),
    )
    with pytest.raises(RegimeAdaptiveConfigError, match="defensive"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_unknown_category() -> None:
    config = replace(
        _default(),
        universe=(
            AssetEntry(symbol="SPY", category="exotic"),
            AssetEntry(symbol="SGOV", category=ASSET_CATEGORY_DEFENSIVE),
        ),
    )
    with pytest.raises(RegimeAdaptiveConfigError, match="category"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_duplicate_symbols_in_universe() -> None:
    config = replace(
        _default(),
        universe=(
            AssetEntry(symbol="SPY", category=ASSET_CATEGORY_RISK_CORE),
            AssetEntry(symbol="SPY", category=ASSET_CATEGORY_RISK_CORE),
            AssetEntry(symbol="SGOV", category=ASSET_CATEGORY_DEFENSIVE),
        ),
    )
    with pytest.raises(RegimeAdaptiveConfigError, match="duplicate"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_defensive_symbol_missing_from_universe() -> None:
    config = replace(_default(), defensive_symbol="NOPE")
    with pytest.raises(RegimeAdaptiveConfigError, match="defensive_symbol"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_defensive_symbol_with_wrong_category() -> None:
    config = replace(_default(), defensive_symbol="SPY")
    with pytest.raises(RegimeAdaptiveConfigError, match="defensive"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_spy_symbol_missing_from_universe() -> None:
    config = replace(_default(), regime_spy_symbol="NOPE")
    with pytest.raises(RegimeAdaptiveConfigError, match="regime_spy_symbol"):
        validate_regime_adaptive_config(config)


def test_validate_regime_adaptive_config_rejects_non_positive_windows() -> None:
    for field_name, bad_value in (
        ("trend_window_days", 0),
        ("vol_lookback_days", -10),
        ("regime_fast_vol_window_days", 0),
        ("regime_slow_vol_window_days", -1),
    ):
        with pytest.raises(RegimeAdaptiveConfigError, match=field_name):
            validate_regime_adaptive_config(replace(_default(), **{field_name: bad_value}))


def test_validate_regime_adaptive_config_rejects_regime_crisis_ratio_at_or_below_one() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="regime_crisis_ratio"):
        validate_regime_adaptive_config(replace(_default(), regime_crisis_ratio=1.0))


def test_validate_regime_adaptive_config_rejects_tolerance_band_out_of_range() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="tolerance_band"):
        validate_regime_adaptive_config(replace(_default(), tolerance_band=1.01))
    with pytest.raises(RegimeAdaptiveConfigError, match="tolerance_band"):
        validate_regime_adaptive_config(replace(_default(), tolerance_band=-0.01))


def test_validate_regime_adaptive_config_rejects_crisis_exposure_scale_out_of_range() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="crisis_exposure_scale"):
        validate_regime_adaptive_config(
            replace(_default(), regime_crisis_exposure_scale=1.5)
        )
    with pytest.raises(RegimeAdaptiveConfigError, match="crisis_exposure_scale"):
        validate_regime_adaptive_config(
            replace(_default(), regime_crisis_exposure_scale=-0.1)
        )


def test_validate_regime_adaptive_config_rejects_drawdown_threshold_out_of_unit_interval() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="drawdown"):
        validate_regime_adaptive_config(replace(_default(), account_drawdown_threshold=0.0))
    with pytest.raises(RegimeAdaptiveConfigError, match="drawdown"):
        validate_regime_adaptive_config(replace(_default(), account_drawdown_threshold=1.5))


def test_validate_regime_adaptive_config_rejects_target_volatility_non_positive() -> None:
    with pytest.raises(RegimeAdaptiveConfigError, match="target_volatility"):
        validate_regime_adaptive_config(replace(_default(), target_volatility=0.0))


def test_default_regime_adaptive_config_strategy_id_is_research_only_label() -> None:
    config = _default()

    assert config.strategy_id == "regime_adaptive_multi_asset"
