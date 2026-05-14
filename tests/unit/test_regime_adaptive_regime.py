from dataclasses import replace
from datetime import date, timedelta

import pytest

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import default_regime_adaptive_config
from trade.strategies.regime_adaptive.regime import (
    REGIME_BEAR,
    REGIME_CRISIS,
    REGIME_NORMAL,
    RegimeState,
    apply_regime_exposure_adjustment,
    detect_regime,
)


def _bars(symbol: str, prices: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
    return [
        PriceBar(
            date=start + timedelta(days=index),
            symbol=symbol,
            open=price,
            close=price,
            adjusted_close=price,
            volume=1_000,
        )
        for index, price in enumerate(prices)
    ]


def _rising(length: int, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + step * index for index in range(length)]


def _falling(length: int, start: float = 200.0, step: float = 0.3) -> list[float]:
    return [start - step * index for index in range(length)]


def _calm_then_volatile(
    calm_length: int, volatile_length: int, calm_step: float, volatile_step: float
) -> list[float]:
    """Series that is calm for ``calm_length`` periods then highly volatile."""

    prices: list[float] = []
    price = 100.0
    for index in range(calm_length):
        if index:
            price *= 1.0 + (calm_step if index % 2 else -calm_step)
        prices.append(price)
    for index in range(volatile_length):
        price *= 1.0 + (volatile_step if index % 2 else -volatile_step)
        prices.append(price)
    return prices


def _config_with_short_windows() -> object:
    return replace(default_regime_adaptive_config(), trend_window_days=20)


def _spy_above_sma() -> list[float]:
    return _rising(220, start=100.0, step=0.5)


def _spy_below_sma() -> list[float]:
    return _falling(220, start=200.0, step=0.5)


def _build_universe_records(spy_series: list[float], length: int = 220) -> list[PriceBar]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for entry in config.universe:
        if entry.symbol == "SPY":
            rows.extend(_bars("SPY", spy_series))
        else:
            rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.2)))
    return rows


def _weights_full_spy() -> dict[str, float]:
    return {"SPY": 1.0}


def test_detect_regime_returns_normal_when_spy_above_sma_and_low_vol_ratio() -> None:
    config = _config_with_short_windows()
    records = tuple(_build_universe_records(_spy_above_sma()))
    signal_date = records[-1].date

    state = detect_regime(records, _weights_full_spy(), config, signal_date)

    assert isinstance(state, RegimeState)
    assert state.regime == REGIME_NORMAL
    assert state.spy_trend_signal is True
    assert state.human_review_required is False
    assert state.triggered_at is None


def test_detect_regime_returns_bear_when_spy_below_sma_without_vol_spike() -> None:
    config = _config_with_short_windows()
    records = tuple(_build_universe_records(_spy_below_sma()))
    signal_date = records[-1].date

    state = detect_regime(records, _weights_full_spy(), config, signal_date)

    assert state.regime == REGIME_BEAR
    assert state.spy_trend_signal is False
    assert state.human_review_required is False


def test_detect_regime_returns_crisis_when_spy_below_sma_and_vol_ratio_above_threshold() -> None:
    config = _config_with_short_windows()
    spy_series: list[float] = []
    price = 100.0
    for index in range(200):
        if index:
            price *= 1.0 + (0.001 if index % 2 else -0.001)
        spy_series.append(price)
    for index in range(20):
        price *= 0.95 if index % 2 == 0 else 1.01
        spy_series.append(price)
    records = tuple(_build_universe_records(spy_series))
    signal_date = records[-1].date

    state = detect_regime(records, _weights_full_spy(), config, signal_date)

    assert state.regime == REGIME_CRISIS
    assert state.fast_slow_ratio > config.regime_crisis_ratio
    assert state.spy_trend_signal is False
    assert state.human_review_required is True
    assert state.triggered_at == signal_date


def test_detect_regime_stays_normal_when_vol_ratio_high_but_spy_above_sma() -> None:
    """High vol ratio alone is not enough; SPY trend must also be down."""

    config = _config_with_short_windows()
    spy_series: list[float] = []
    price = 100.0
    for index in range(200):
        if index:
            price *= 1.0 + (0.001 if index % 2 else -0.001)
        spy_series.append(price)
    # 20-day spike up with high vol so SMA20 stays below latest close.
    for index in range(20):
        price *= 1.05 if index % 2 == 0 else 0.99
        spy_series.append(price)
    records = tuple(_build_universe_records(spy_series))
    signal_date = records[-1].date

    state = detect_regime(records, _weights_full_spy(), config, signal_date)

    assert state.regime == REGIME_NORMAL
    assert state.spy_trend_signal is True
    assert state.human_review_required is False


def test_detect_regime_defaults_to_normal_when_prior_weights_empty() -> None:
    config = _config_with_short_windows()
    records = tuple(_build_universe_records(_spy_above_sma()))
    signal_date = records[-1].date

    state = detect_regime(records, {}, config, signal_date)

    assert state.regime == REGIME_NORMAL
    assert state.fast_volatility == pytest.approx(0.0)
    assert state.slow_volatility == pytest.approx(0.0)


def test_apply_regime_exposure_adjustment_passes_normal_weights_through_untouched() -> None:
    config = default_regime_adaptive_config()
    weights = {"SPY": 0.4, "VEA": 0.3, "SGOV": 0.3}
    state = RegimeState(
        regime=REGIME_NORMAL,
        fast_volatility=0.1,
        slow_volatility=0.1,
        fast_slow_ratio=1.0,
        spy_trend_signal=True,
        triggered_at=None,
        human_review_required=False,
    )

    adjusted = apply_regime_exposure_adjustment(weights, state, config)

    assert adjusted == weights


def test_apply_regime_exposure_adjustment_passes_bear_weights_through_untouched() -> None:
    config = default_regime_adaptive_config()
    weights = {"SPY": 0.4, "VEA": 0.3, "SGOV": 0.3}
    state = RegimeState(
        regime=REGIME_BEAR,
        fast_volatility=0.12,
        slow_volatility=0.10,
        fast_slow_ratio=1.2,
        spy_trend_signal=False,
        triggered_at=None,
        human_review_required=False,
    )

    adjusted = apply_regime_exposure_adjustment(weights, state, config)

    assert adjusted == weights


def test_apply_regime_exposure_adjustment_halves_non_defensive_in_crisis() -> None:
    config = default_regime_adaptive_config()
    weights = {"SPY": 0.4, "VEA": 0.2, "GLD": 0.2, "SGOV": 0.2}
    state = RegimeState(
        regime=REGIME_CRISIS,
        fast_volatility=0.30,
        slow_volatility=0.15,
        fast_slow_ratio=2.0,
        spy_trend_signal=False,
        triggered_at=date(2024, 3, 1),
        human_review_required=True,
    )

    adjusted = apply_regime_exposure_adjustment(weights, state, config)

    assert adjusted["SPY"] == pytest.approx(0.2)
    assert adjusted["VEA"] == pytest.approx(0.1)
    assert adjusted["GLD"] == pytest.approx(0.1)
    assert adjusted["SGOV"] == pytest.approx(0.6)
    assert round(sum(adjusted.values()), 8) == 1.0


def test_apply_regime_adjustment_with_zero_non_defensive_leaves_weights_unchanged() -> None:
    config = default_regime_adaptive_config()
    weights = {"SPY": 0.0, "SGOV": 1.0}
    state = RegimeState(
        regime=REGIME_CRISIS,
        fast_volatility=0.30,
        slow_volatility=0.15,
        fast_slow_ratio=2.0,
        spy_trend_signal=False,
        triggered_at=date(2024, 3, 1),
        human_review_required=True,
    )

    adjusted = apply_regime_exposure_adjustment(weights, state, config)

    assert adjusted == {"SPY": 0.0, "SGOV": 1.0}
