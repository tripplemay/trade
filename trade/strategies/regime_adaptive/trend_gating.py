"""L1 per-asset 200-day SMA trend gating for the regime-adaptive strategy.

For every non-defensive asset in the configured universe, this layer compares the latest
adjusted close at the supplied signal date against its trailing trend_window_days SMA. The
defensive symbol (default ``SGOV``) is never gated; gated capital from risk-core and
stabilizer sleeves is reported as routed to the defensive sleeve. Insufficient history
fails closed (asset gated off) so the upstream weighting layer never receives a partial
signal. The artifacts produced here are research-only and never authorize any paper or
production order flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    AssetEntry,
    RegimeAdaptiveConfig,
)

GATE_REASON_PASS = "passes_trend_filter"
GATE_REASON_BELOW_SMA = "close_at_or_below_sma"
GATE_REASON_INSUFFICIENT_HISTORY = "insufficient_history"
GATE_REASON_DEFENSIVE_PASS = "defensive_never_gated"


@dataclass(frozen=True, slots=True)
class AssetTrendSignal:
    symbol: str
    category: str
    passes: bool
    reason: str
    latest_adjusted_close: float
    moving_average: float
    observations: int


@dataclass(frozen=True, slots=True)
class TrendGatingResult:
    signal_date: date
    mask: dict[str, bool]
    details: tuple[AssetTrendSignal, ...]
    gated_symbols: tuple[str, ...]
    passing_symbols: tuple[str, ...]
    defensive_routing_symbol: str


def apply_trend_gating(
    records: tuple[PriceBar, ...],
    config: RegimeAdaptiveConfig,
    signal_date: date,
) -> TrendGatingResult:
    by_symbol = _group_by_symbol(records)
    details: list[AssetTrendSignal] = []
    mask: dict[str, bool] = {}
    for entry in config.universe:
        history = tuple(
            record
            for record in by_symbol.get(entry.symbol, ())
            if record.date <= signal_date
        )
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            latest = history[-1].adjusted_close if history else 0.0
            details.append(
                AssetTrendSignal(
                    symbol=entry.symbol,
                    category=entry.category,
                    passes=True,
                    reason=GATE_REASON_DEFENSIVE_PASS,
                    latest_adjusted_close=latest,
                    moving_average=latest,
                    observations=len(history),
                )
            )
            mask[entry.symbol] = True
            continue
        if not history:
            raise ValueError(
                f"missing price history for required asset {entry.symbol}"
            )
        details.append(_signal_for_risk_asset(entry, history, config.trend_window_days))
        mask[entry.symbol] = details[-1].passes

    gated_symbols = tuple(sorted(symbol for symbol, passes in mask.items() if not passes))
    passing_symbols = tuple(sorted(symbol for symbol, passes in mask.items() if passes))
    return TrendGatingResult(
        signal_date=signal_date,
        mask=mask,
        details=tuple(details),
        gated_symbols=gated_symbols,
        passing_symbols=passing_symbols,
        defensive_routing_symbol=config.defensive_symbol,
    )


def _signal_for_risk_asset(
    entry: AssetEntry, history: tuple[PriceBar, ...], trend_window_days: int
) -> AssetTrendSignal:
    if len(history) < trend_window_days:
        return AssetTrendSignal(
            symbol=entry.symbol,
            category=entry.category,
            passes=False,
            reason=GATE_REASON_INSUFFICIENT_HISTORY,
            latest_adjusted_close=history[-1].adjusted_close if history else 0.0,
            moving_average=0.0,
            observations=len(history),
        )
    window = history[-trend_window_days:]
    moving_average = sum(record.adjusted_close for record in window) / trend_window_days
    latest = history[-1].adjusted_close
    passes = latest > moving_average
    return AssetTrendSignal(
        symbol=entry.symbol,
        category=entry.category,
        passes=passes,
        reason=GATE_REASON_PASS if passes else GATE_REASON_BELOW_SMA,
        latest_adjusted_close=latest,
        moving_average=moving_average,
        observations=trend_window_days,
    )


def _group_by_symbol(records: tuple[PriceBar, ...]) -> dict[str, tuple[PriceBar, ...]]:
    buckets: dict[str, list[PriceBar]] = {}
    for record in records:
        buckets.setdefault(record.symbol, []).append(record)
    return {
        symbol: tuple(sorted(items, key=lambda item: item.date))
        for symbol, items in buckets.items()
    }
