from dataclasses import replace
from datetime import date, timedelta

import pytest

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    ASSET_CATEGORY_RISK_CORE,
    AssetEntry,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.trend_gating import (
    GATE_REASON_BELOW_SMA,
    GATE_REASON_DEFENSIVE_PASS,
    GATE_REASON_INSUFFICIENT_HISTORY,
    GATE_REASON_PASS,
    AssetTrendSignal,
    TrendGatingResult,
    apply_trend_gating,
)


def _records(symbol: str, prices: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
    rows: list[PriceBar] = []
    for index, price in enumerate(prices):
        rows.append(
            PriceBar(
                date=start + timedelta(days=index),
                symbol=symbol,
                open=price,
                close=price,
                adjusted_close=price,
                volume=1_000,
            )
        )
    return rows


def _rising_series(length: int, start: float = 100.0, step: float = 0.1) -> list[float]:
    return [start + step * index for index in range(length)]


def _falling_series(length: int, start: float = 200.0, step: float = 0.1) -> list[float]:
    return [start - step * index for index in range(length)]


def _flat_series(length: int, value: float = 100.0) -> list[float]:
    return [value] * length


def test_apply_trend_gating_passes_when_close_is_above_sma() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        records.extend(_records(entry.symbol, _rising_series(220)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    assert isinstance(result, TrendGatingResult)
    risk_assets = [
        entry.symbol
        for entry in config.universe
        if entry.category != ASSET_CATEGORY_DEFENSIVE
    ]
    for symbol in risk_assets:
        assert result.mask[symbol] is True
    by_symbol = {signal.symbol: signal for signal in result.details}
    for symbol in risk_assets:
        assert by_symbol[symbol].reason == GATE_REASON_PASS


def test_apply_trend_gating_gates_when_close_is_below_sma() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            records.extend(_records(entry.symbol, _flat_series(220, value=100.0)))
            continue
        records.extend(_records(entry.symbol, _falling_series(220, start=200.0, step=0.5)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    risk_assets = [
        entry.symbol
        for entry in config.universe
        if entry.category != ASSET_CATEGORY_DEFENSIVE
    ]
    by_symbol = {signal.symbol: signal for signal in result.details}
    for symbol in risk_assets:
        assert result.mask[symbol] is False
        assert by_symbol[symbol].reason == GATE_REASON_BELOW_SMA


def test_apply_trend_gating_gates_when_history_is_insufficient() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.symbol == "QQQ":
            records.extend(_records(entry.symbol, _rising_series(50)))
        else:
            records.extend(_records(entry.symbol, _rising_series(220)))
    signal_date = max(record.date for record in records)

    result = apply_trend_gating(tuple(records), config, signal_date)
    by_symbol = {signal.symbol: signal for signal in result.details}

    assert result.mask["QQQ"] is False
    assert by_symbol["QQQ"].reason == GATE_REASON_INSUFFICIENT_HISTORY
    assert by_symbol["QQQ"].observations < config.trend_window_days


def test_apply_trend_gating_never_gates_defensive_symbol() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            # Defensive history is intentionally short and falling; must still pass.
            records.extend(_records(entry.symbol, _falling_series(10, start=110.0, step=0.5)))
            continue
        records.extend(_records(entry.symbol, _rising_series(220)))
    signal_date = max(record.date for record in records)

    result = apply_trend_gating(tuple(records), config, signal_date)
    by_symbol = {signal.symbol: signal for signal in result.details}

    assert result.mask[config.defensive_symbol] is True
    assert by_symbol[config.defensive_symbol].reason == GATE_REASON_DEFENSIVE_PASS


def test_apply_trend_gating_uses_adjusted_close_not_close() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            records.extend(_records(entry.symbol, _flat_series(220, value=100.0)))
            continue
        rising_adjusted = _rising_series(220, start=100.0, step=0.1)
        rows = []
        start = date(2024, 1, 1)
        for index, adjusted in enumerate(rising_adjusted):
            rows.append(
                PriceBar(
                    date=start + timedelta(days=index),
                    symbol=entry.symbol,
                    open=adjusted,
                    close=10.0,  # nonsense unadjusted close to ensure adjusted_close is the source
                    adjusted_close=adjusted,
                    volume=1_000,
                )
            )
        records.extend(rows)
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            continue
        assert result.mask[entry.symbol] is True


def test_apply_trend_gating_records_sma_and_latest_close_values() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        records.extend(_records(entry.symbol, _rising_series(220)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)
    spy_signal = next(signal for signal in result.details if signal.symbol == "SPY")

    assert spy_signal.latest_adjusted_close > spy_signal.moving_average
    assert spy_signal.observations == config.trend_window_days


def test_apply_trend_gating_gated_capital_routes_to_defensive_in_summary() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            records.extend(_records(entry.symbol, _flat_series(220, value=100.0)))
            continue
        records.extend(_records(entry.symbol, _falling_series(220, start=200.0, step=0.5)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    assert result.gated_symbols == tuple(
        sorted(
            entry.symbol
            for entry in config.universe
            if entry.category != ASSET_CATEGORY_DEFENSIVE
        )
    )
    assert result.defensive_routing_symbol == config.defensive_symbol


def test_apply_trend_gating_rejects_missing_required_asset_history() -> None:
    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.symbol == "TLT":
            continue
        records.extend(_records(entry.symbol, _rising_series(220)))
    signal_date = records[-1].date

    with pytest.raises(ValueError, match="TLT"):
        apply_trend_gating(tuple(records), config, signal_date)


def test_apply_trend_gating_can_pass_with_custom_smaller_trend_window() -> None:
    config = replace(default_regime_adaptive_config(), trend_window_days=20)
    records: list[PriceBar] = []
    for entry in config.universe:
        records.extend(_records(entry.symbol, _rising_series(30)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            assert result.mask[entry.symbol] is True
            continue
        assert result.mask[entry.symbol] is True
    spy_signal = next(signal for signal in result.details if signal.symbol == "SPY")
    assert spy_signal.observations == 20


def test_asset_trend_signal_carries_symbol_and_reason() -> None:
    signal = AssetTrendSignal(
        symbol="SPY",
        category=ASSET_CATEGORY_RISK_CORE,
        passes=True,
        reason=GATE_REASON_PASS,
        latest_adjusted_close=120.0,
        moving_average=110.0,
        observations=200,
    )

    assert signal.symbol == "SPY"
    assert signal.reason == GATE_REASON_PASS


def test_apply_trend_gating_works_with_extra_assets_not_in_universe() -> None:
    """Extra symbols outside the universe must be silently ignored without erroring."""

    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        records.extend(_records(entry.symbol, _rising_series(220)))
    records.extend(
        _records("XLB", _rising_series(220))  # not in universe
    )
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)

    assert "XLB" not in result.mask


def test_apply_trend_gating_threshold_transition_when_close_equals_sma() -> None:
    """At close == SMA, the asset must be gated off (strict greater-than)."""

    config = default_regime_adaptive_config()
    records: list[PriceBar] = []
    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            records.extend(_records(entry.symbol, _flat_series(220, value=100.0)))
            continue
        # Flat series guarantees latest_close == sma.
        records.extend(_records(entry.symbol, _flat_series(220, value=100.0)))
    signal_date = records[-1].date

    result = apply_trend_gating(tuple(records), config, signal_date)
    by_symbol = {signal.symbol: signal for signal in result.details}

    for entry in config.universe:
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            continue
        assert result.mask[entry.symbol] is False
        assert by_symbol[entry.symbol].reason == GATE_REASON_BELOW_SMA


def test_asset_entry_imports_from_config_module_for_tests() -> None:
    # Sanity check that AssetEntry is exposed for downstream construction.
    entry = AssetEntry(symbol="SPY", category=ASSET_CATEGORY_RISK_CORE)
    assert entry.symbol == "SPY"
