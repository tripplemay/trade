"""Minimum Global ETF Momentum signal generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from trade.data.loader import PriceBar

# The ETF universe the Global ETF Momentum sleeve ranks over. This is the broad
# ETF set the strategy was designed and validated to trade (design doc §3/§17);
# it deliberately EXCLUDES the individual equities that share the production
# unified prices CSV (the us_quality universe). Without this whitelist the
# sleeve ranked all 42 mixed symbols and the live book ended up holding single
# stocks (CAT/HD) — P0-1, diagnosis §2. Kept in sync with
# ``workbench_api.data_refresh.refresh.ETF_UNIVERSE`` by a workbench drift-guard
# test (the momentum sleeve trades exactly the priced ETF set).
GLOBAL_ETF_MOMENTUM_UNIVERSE: frozenset[str] = frozenset(
    {
        "AGG",
        "ASHR",
        "DBC",
        "EEM",
        "FXI",
        "GLD",
        "IEF",
        "KWEB",
        "MCHI",
        "QQQ",
        "SGOV",
        "SPY",
        "TLT",
        "VEA",
        "VWO",
    }
)


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


def filter_to_universe(
    records: tuple[PriceBar, ...], universe: frozenset[str]
) -> tuple[PriceBar, ...]:
    """Keep only the bars whose symbol is in ``universe`` (order preserved)."""

    return tuple(record for record in records if record.symbol in universe)


def resample_to_month_end(records: tuple[PriceBar, ...]) -> tuple[PriceBar, ...]:
    """Collapse each symbol to its last bar per calendar month.

    The momentum windows are bar-counted (``_lookback_return`` steps back
    ``periods`` bars), and the strategy's design semantics are monthly (design
    doc §5.1: 3/6/9 are *months*). Production feeds daily bars, which silently
    turned the 3/6/9-month windows into 3/6/9-*day* windows — an unvalidated,
    high-noise signal (P0-1). Keeping only the last trading day of each calendar
    month restores the monthly cadence the backtest validated. Idempotent on
    inputs that are already monthly (the committed fixture / backtest records),
    so the validated backtest behaviour is unchanged; only the daily production
    feed is corrected.
    """

    latest_by_key: dict[tuple[str, int, int], PriceBar] = {}
    for record in records:
        key = (record.symbol, record.date.year, record.date.month)
        existing = latest_by_key.get(key)
        if existing is None or record.date > existing.date:
            latest_by_key[key] = record
    return tuple(sorted(latest_by_key.values(), key=lambda bar: (bar.symbol, bar.date)))


def required_history_bars(parameters: MomentumParameters) -> int:
    """Bars a non-defensive symbol needs on/before the signal date to be
    rankable — mirrors the guard in :func:`_rank_asset`."""

    return max(
        max(window.periods for window in parameters.momentum_windows),
        parameters.trend_window,
    )


def prepare_momentum_records(
    records: tuple[PriceBar, ...],
    *,
    parameters: MomentumParameters,
    signal_date: date,
    universe: frozenset[str] = GLOBAL_ETF_MOMENTUM_UNIVERSE,
) -> tuple[PriceBar, ...]:
    """Prepare the production price feed for the Global ETF Momentum sleeve.

    Three transforms, all no-ops on the ETF-only, already-monthly backtest
    fixture (so validated behaviour is unchanged), that together restore the
    sleeve's validated monthly ETF-rotation semantics on the polluted daily
    production feed (P0-1 fix, diagnosis §6 F1):

    1. restrict to the ETF ``universe`` (plus the defensive asset), dropping the
       individual equities that share the unified prices CSV;
    2. collapse each symbol to month-end bars, so the 3/6/9 windows span months
       not days;
    3. drop any non-defensive symbol that still lacks enough month-end history
       to be scored as of ``signal_date`` (e.g. a recently listed ETF), so one
       short-history ETF cannot abort the whole 40% sleeve — that symbol is
       simply not a candidate this period, exactly as production intends.
    """

    kept = universe | {parameters.defensive_asset}
    monthly = resample_to_month_end(filter_to_universe(records, kept))
    required = required_history_bars(parameters)
    counts: dict[str, int] = {}
    for bar in monthly:
        if bar.date <= signal_date:
            counts[bar.symbol] = counts.get(bar.symbol, 0) + 1
    return tuple(
        bar
        for bar in monthly
        if bar.symbol == parameters.defensive_asset
        or counts.get(bar.symbol, 0) > required
    )
