"""Minimum Global ETF Momentum signal generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from trade.data.loader import PriceBar


@dataclass(frozen=True, slots=True)
class MomentumWindow:
    """Weighted lookback window measured in available fixture observations."""

    periods: int
    weight: float


@dataclass(frozen=True, slots=True)
class MomentumParameters:
    """Parameters recorded with every Global ETF Momentum signal."""

    strategy_id: str = "global_etf_momentum"
    top_n: int = 2
    defensive_asset: str = "AGG"
    momentum_windows: tuple[MomentumWindow, ...] = (
        MomentumWindow(periods=3, weight=0.4),
        MomentumWindow(periods=6, weight=0.3),
        MomentumWindow(periods=9, weight=0.3),
    )
    trend_window: int = 3
    require_positive_trend_return: bool = True

    def parameter_hash(self) -> str:
        payload = {
            "defensive_asset": self.defensive_asset,
            "momentum_windows": [
                {"periods": window.periods, "weight": window.weight}
                for window in self.momentum_windows
            ],
            "require_positive_trend_return": self.require_positive_trend_return,
            "strategy_id": self.strategy_id,
            "top_n": self.top_n,
            "trend_window": self.trend_window,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class RankedAsset:
    symbol: str
    momentum_score: float
    passed_trend_filter: bool
    trend_return: float
    latest_adjusted_close: float
    moving_average: float


@dataclass(frozen=True, slots=True)
class MomentumSignal:
    signal_date: date
    target_weights: dict[str, float]
    ranked_assets: tuple[RankedAsset, ...]
    selected_assets: tuple[str, ...]
    defensive_asset: str
    defensive_weight: float
    parameter_hash: str
    parameters: MomentumParameters


class MomentumSignalError(ValueError):
    """Raised when signal generation cannot be performed from supplied data."""


def generate_momentum_signal(
    records: tuple[PriceBar, ...],
    parameters: MomentumParameters | None = None,
    signal_date: date | None = None,
) -> MomentumSignal:
    """Generate equal-weight Top N momentum targets with defensive fallback."""

    if parameters is None:
        parameters = MomentumParameters()
    _validate_parameters(parameters)
    by_symbol = _prices_by_symbol(records)
    if parameters.defensive_asset not in by_symbol:
        raise MomentumSignalError("defensive asset must exist in price records")

    effective_signal_date = signal_date or max(record.date for record in records)
    ranked_assets = tuple(
        sorted(
            (
                _rank_asset(symbol, prices, parameters, effective_signal_date)
                for symbol, prices in by_symbol.items()
                if symbol != parameters.defensive_asset
            ),
            key=lambda item: (-item.momentum_score, item.symbol),
        )
    )
    eligible = tuple(asset for asset in ranked_assets if asset.passed_trend_filter)
    selected = eligible[: parameters.top_n]

    per_slot_weight = 1.0 / parameters.top_n
    target_weights = {asset.symbol: per_slot_weight for asset in selected}
    defensive_weight = 1.0 - (per_slot_weight * len(selected))
    if defensive_weight > 0:
        target_weights[parameters.defensive_asset] = defensive_weight

    return MomentumSignal(
        signal_date=effective_signal_date,
        target_weights=target_weights,
        ranked_assets=ranked_assets,
        selected_assets=tuple(asset.symbol for asset in selected),
        defensive_asset=parameters.defensive_asset,
        defensive_weight=defensive_weight,
        parameter_hash=parameters.parameter_hash(),
        parameters=parameters,
    )


def _validate_parameters(parameters: MomentumParameters) -> None:
    if parameters.top_n <= 0:
        raise MomentumSignalError("top_n must be positive")
    if parameters.trend_window <= 0:
        raise MomentumSignalError("trend_window must be positive")
    if not parameters.momentum_windows:
        raise MomentumSignalError("at least one momentum window is required")
    for window in parameters.momentum_windows:
        if window.periods <= 0:
            raise MomentumSignalError("momentum window periods must be positive")
        if window.weight <= 0:
            raise MomentumSignalError("momentum window weights must be positive")


def _prices_by_symbol(records: tuple[PriceBar, ...]) -> dict[str, tuple[PriceBar, ...]]:
    grouped: dict[str, list[PriceBar]] = {}
    for record in records:
        grouped.setdefault(record.symbol, []).append(record)
    return {
        symbol: tuple(sorted(symbol_records, key=lambda item: item.date))
        for symbol, symbol_records in grouped.items()
    }


def _rank_asset(
    symbol: str, prices: tuple[PriceBar, ...], parameters: MomentumParameters, signal_date: date
) -> RankedAsset:
    history = tuple(record for record in prices if record.date <= signal_date)
    required_periods = max(
        max(window.periods for window in parameters.momentum_windows), parameters.trend_window
    )
    if len(history) <= required_periods:
        raise MomentumSignalError(f"not enough history for {symbol}")

    latest = history[-1]
    score = sum(
        window.weight * _lookback_return(history, window.periods)
        for window in parameters.momentum_windows
    )
    trend_return = _lookback_return(history, parameters.trend_window)
    moving_average = (
        sum(record.adjusted_close for record in history[-parameters.trend_window :])
        / parameters.trend_window
    )
    passed_filter = latest.adjusted_close > moving_average
    if parameters.require_positive_trend_return:
        passed_filter = passed_filter and trend_return > 0

    return RankedAsset(
        symbol=symbol,
        momentum_score=score,
        passed_trend_filter=passed_filter,
        trend_return=trend_return,
        latest_adjusted_close=latest.adjusted_close,
        moving_average=moving_average,
    )


def _lookback_return(history: tuple[PriceBar, ...], periods: int) -> float:
    latest = history[-1].adjusted_close
    prior = history[-periods - 1].adjusted_close
    return latest / prior - 1.0
