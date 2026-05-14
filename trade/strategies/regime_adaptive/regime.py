"""L3 portfolio-level regime detection and exposure adjustment.

Classifies the supplied price history into NORMAL / BEAR / CRISIS using a Fast/Slow
volatility ratio plus the SPY 200-day SMA trend signal. CRISIS halves all non-defensive
weights and routes the released exposure to the defensive sleeve; BEAR and NORMAL leave
weights untouched at the portfolio layer. The artifact is research-only and never
authorizes any paper or production order flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import RegimeAdaptiveConfig

REGIME_NORMAL = "NORMAL"
REGIME_BEAR = "BEAR"
REGIME_CRISIS = "CRISIS"

ANNUALIZATION_FACTOR = 252.0


@dataclass(frozen=True, slots=True)
class RegimeState:
    regime: str
    fast_volatility: float
    slow_volatility: float
    fast_slow_ratio: float
    spy_trend_signal: bool
    triggered_at: date | None
    human_review_required: bool


def detect_regime(
    records: tuple[PriceBar, ...],
    prior_weights: dict[str, float],
    config: RegimeAdaptiveConfig,
    signal_date: date,
) -> RegimeState:
    spy_trend_signal = _spy_trend_signal(records, config, signal_date)
    fast_vol, slow_vol = _portfolio_volatilities(records, prior_weights, config, signal_date)
    ratio = (fast_vol / slow_vol) if slow_vol > 0 else 0.0
    if (
        slow_vol > 0
        and ratio > config.regime_crisis_ratio
        and not spy_trend_signal
    ):
        regime = REGIME_CRISIS
    elif not spy_trend_signal:
        regime = REGIME_BEAR
    else:
        regime = REGIME_NORMAL
    triggered_at = signal_date if regime == REGIME_CRISIS else None
    return RegimeState(
        regime=regime,
        fast_volatility=fast_vol,
        slow_volatility=slow_vol,
        fast_slow_ratio=ratio,
        spy_trend_signal=spy_trend_signal,
        triggered_at=triggered_at,
        human_review_required=regime == REGIME_CRISIS,
    )


def apply_regime_exposure_adjustment(
    weights: dict[str, float],
    regime_state: RegimeState,
    config: RegimeAdaptiveConfig,
) -> dict[str, float]:
    if regime_state.regime != REGIME_CRISIS:
        return dict(weights)
    defensive_symbol = config.defensive_symbol
    scale = config.regime_crisis_exposure_scale
    adjusted: dict[str, float] = {}
    released = 0.0
    for symbol, weight in weights.items():
        if symbol == defensive_symbol:
            adjusted[symbol] = weight
            continue
        scaled = weight * scale
        released += weight - scaled
        adjusted[symbol] = scaled
    adjusted[defensive_symbol] = adjusted.get(defensive_symbol, 0.0) + released
    return adjusted


def _spy_trend_signal(
    records: tuple[PriceBar, ...], config: RegimeAdaptiveConfig, signal_date: date
) -> bool:
    spy_history = tuple(
        record
        for record in records
        if record.symbol == config.regime_spy_symbol and record.date <= signal_date
    )
    if len(spy_history) < config.trend_window_days:
        return False
    spy_history = tuple(sorted(spy_history, key=lambda item: item.date))
    window = spy_history[-config.trend_window_days :]
    sma = sum(record.adjusted_close for record in window) / config.trend_window_days
    return spy_history[-1].adjusted_close > sma


def _portfolio_volatilities(
    records: tuple[PriceBar, ...],
    prior_weights: dict[str, float],
    config: RegimeAdaptiveConfig,
    signal_date: date,
) -> tuple[float, float]:
    contributing = {
        symbol: weight
        for symbol, weight in prior_weights.items()
        if weight > 0 and symbol != config.defensive_symbol
    }
    if not contributing:
        return 0.0, 0.0
    by_symbol = _group_by_symbol(records, signal_date)
    series_returns: dict[str, list[float]] = {}
    min_length = None
    for symbol in contributing:
        prices = by_symbol.get(symbol)
        if not prices:
            continue
        returns = _daily_returns(prices)
        if not returns:
            continue
        series_returns[symbol] = returns
        if min_length is None or len(returns) < min_length:
            min_length = len(returns)
    if min_length is None or min_length < 2:
        return 0.0, 0.0
    aligned_returns: dict[str, list[float]] = {
        symbol: returns[-min_length:] for symbol, returns in series_returns.items()
    }
    total_weight = sum(prior_weights[symbol] for symbol in aligned_returns)
    if total_weight <= 0:
        return 0.0, 0.0
    portfolio_returns: list[float] = []
    for index in range(min_length):
        value = 0.0
        for symbol, weight in prior_weights.items():
            if symbol in aligned_returns:
                value += (weight / total_weight) * aligned_returns[symbol][index]
        portfolio_returns.append(value)
    fast_window = portfolio_returns[-min(config.regime_fast_vol_window_days, min_length):]
    slow_window = portfolio_returns[-min(config.regime_slow_vol_window_days, min_length):]
    return _annualized_volatility(fast_window), _annualized_volatility(slow_window)


def _group_by_symbol(
    records: tuple[PriceBar, ...], signal_date: date
) -> dict[str, tuple[PriceBar, ...]]:
    buckets: dict[str, list[PriceBar]] = {}
    for record in records:
        if record.date > signal_date:
            continue
        buckets.setdefault(record.symbol, []).append(record)
    return {
        symbol: tuple(sorted(rows, key=lambda item: item.date))
        for symbol, rows in buckets.items()
    }


def _daily_returns(prices: tuple[PriceBar, ...]) -> list[float]:
    returns: list[float] = []
    for prior, current in zip(prices, prices[1:], strict=False):
        if prior.adjusted_close <= 0:
            continue
        returns.append(current.adjusted_close / prior.adjusted_close - 1.0)
    return returns


def _annualized_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return sqrt(variance) * sqrt(ANNUALIZATION_FACTOR)
