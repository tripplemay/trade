from dataclasses import replace
from datetime import date, timedelta

import pytest

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.trend_gating import apply_trend_gating
from trade.strategies.regime_adaptive.weighting import (
    RegimeAdaptiveWeightAllocation,
    derive_regime_adaptive_weights,
)


def _records_for_symbol(
    symbol: str,
    length: int,
    start: date = date(2024, 1, 1),
    pattern: tuple[float, float] = (0.003, -0.002),
) -> list[PriceBar]:
    rows: list[PriceBar] = []
    price = 100.0
    for index in range(length):
        if index:
            price *= 1.0 + pattern[index % len(pattern)]
        rows.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol=symbol,
                open=price * 0.999,
                close=price,
                adjusted_close=price,
                volume=1_000,
            )
        )
    return rows


def _build_universe_records(length: int = 220) -> list[PriceBar]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        pattern = (0.002 + 0.001 * index, -0.0015 - 0.0005 * index)
        rows.extend(_records_for_symbol(entry.symbol, length, pattern=pattern))
    return rows


def test_derive_regime_adaptive_weights_returns_allocation_dataclass() -> None:
    config = replace(default_regime_adaptive_config(), trend_window_days=20, vol_lookback_days=60)
    records = tuple(_build_universe_records(150))
    signal_date = records[-1].date
    gating = apply_trend_gating(records, config, signal_date)

    allocation = derive_regime_adaptive_weights(records, config, signal_date, gating)

    assert isinstance(allocation, RegimeAdaptiveWeightAllocation)
    assert round(sum(allocation.target_weights.values()), 8) == 1.0
    assert allocation.target_weights[config.defensive_symbol] >= 0.0


def test_derive_regime_adaptive_weights_routes_gated_capital_to_defensive() -> None:
    """When all risk assets are gated, the defensive sleeve receives 100% of the weight."""

    config = replace(default_regime_adaptive_config(), trend_window_days=20, vol_lookback_days=60)
    rows: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_records_for_symbol(entry.symbol, 150, pattern=(0.0001, 0.0001)))
            continue
        # Falling adjusted close so SMA20 gates everything off.
        start = 200.0
        records_for_symbol: list[PriceBar] = []
        current_price = start
        for index in range(150):
            if index:
                current_price *= 0.99
            records_for_symbol.append(
                PriceBar(
                    date=date(2024, 1, 1) + timedelta(days=index),
                    symbol=entry.symbol,
                    open=current_price * 0.999,
                    close=current_price,
                    adjusted_close=current_price,
                    volume=1_000,
                )
            )
        rows.extend(records_for_symbol)
    records = tuple(rows)
    signal_date = records[-1].date
    gating = apply_trend_gating(records, config, signal_date)

    allocation = derive_regime_adaptive_weights(records, config, signal_date, gating)

    assert allocation.target_weights[config.defensive_symbol] == pytest.approx(1.0)
    for entry in config.universe:
        if entry.category != ASSET_CATEGORY_DEFENSIVE:
            assert allocation.target_weights.get(entry.symbol, 0.0) == 0.0
    assert allocation.exposure_scale == pytest.approx(0.0)
    assert allocation.defensive_routed_weight == pytest.approx(1.0)


def test_derive_regime_adaptive_weights_only_weights_passing_assets() -> None:
    """Gated assets receive zero L2 weight; defensive picks up the slack."""

    config = replace(default_regime_adaptive_config(), trend_window_days=20, vol_lookback_days=60)
    rows: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_records_for_symbol(entry.symbol, 150, pattern=(0.0001, 0.0001)))
            continue
        if entry.symbol == "QQQ":
            # falling -> gated
            current_price = 200.0
            records_for_symbol: list[PriceBar] = []
            for index in range(150):
                if index:
                    current_price *= 0.99
                records_for_symbol.append(
                    PriceBar(
                        date=date(2024, 1, 1) + timedelta(days=index),
                        symbol=entry.symbol,
                        open=current_price * 0.999,
                        close=current_price,
                        adjusted_close=current_price,
                        volume=1_000,
                    )
                )
            rows.extend(records_for_symbol)
            continue
        rows.extend(_records_for_symbol(entry.symbol, 150, pattern=(0.003, -0.002)))
    records = tuple(rows)
    signal_date = records[-1].date
    gating = apply_trend_gating(records, config, signal_date)

    allocation = derive_regime_adaptive_weights(records, config, signal_date, gating)

    assert allocation.target_weights.get("QQQ", 0.0) == 0.0
    assert allocation.target_weights[config.defensive_symbol] > 0.0


def test_derive_regime_adaptive_weights_uses_target_volatility_to_scale_exposure() -> None:
    """A lower target volatility must reduce the exposure_scale (more defensive routing)."""

    base_config = replace(
        default_regime_adaptive_config(), trend_window_days=20, vol_lookback_days=60
    )
    records = tuple(_build_universe_records(150))
    signal_date = records[-1].date
    gating = apply_trend_gating(records, base_config, signal_date)

    high_vol_target = derive_regime_adaptive_weights(records, base_config, signal_date, gating)
    low_vol_target = derive_regime_adaptive_weights(
        records, replace(base_config, target_volatility=0.001), signal_date, gating
    )

    assert low_vol_target.exposure_scale < high_vol_target.exposure_scale


def test_derive_regime_adaptive_weights_caps_exposure_scale_at_one() -> None:
    config = replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        target_volatility=10.0,
    )
    records = tuple(_build_universe_records(150))
    signal_date = records[-1].date
    gating = apply_trend_gating(records, config, signal_date)

    allocation = derive_regime_adaptive_weights(records, config, signal_date, gating)

    assert allocation.exposure_scale == pytest.approx(1.0)


def test_derive_regime_adaptive_weights_returns_deterministic_output() -> None:
    config = replace(default_regime_adaptive_config(), trend_window_days=20, vol_lookback_days=60)
    records = tuple(_build_universe_records(150))
    signal_date = records[-1].date
    gating = apply_trend_gating(records, config, signal_date)

    first = derive_regime_adaptive_weights(records, config, signal_date, gating)
    second = derive_regime_adaptive_weights(records, config, signal_date, gating)

    assert first.target_weights == second.target_weights
    assert first.exposure_scale == second.exposure_scale
