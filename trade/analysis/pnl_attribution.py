"""B018 — P&L attribution decomposition for B010 / B013 vs a benchmark.

Pure-stdlib (math + statistics + dataclasses + typing + collections.abc only;
no scipy / numpy / pandas / sklearn / networkx / third-party). Research-only;
never authorizes any paper or production order flow.

Given a strategy's per-period attribution snapshot (target weights + per-asset
period returns + per-layer exposure-routing fractions) and a benchmark equity
curve, this module computes:

- **Per-asset cumulative dollar contribution to strategy total return.**
  Each entry is the signed dollar value the asset added to the strategy's
  ending value: positive when the asset's weighted return added value,
  negative when it dragged. Computed as
  ``sum_t capital_t * weight_i,t * asset_return_i,t``.

- **Per-layer dollar attribution to the gap (strategy - benchmark)**.
  Captures how much of the strategy's drag (or boost) came from each
  exposure-routing layer:

  - For B010: ``l2_vol_scaling`` (capital parked by the portfolio
    target-vol scaling) and ``defensive_routing`` (the resulting defensive
    sleeve allocation; for B010 this is the same parked capital, attributed
    on the "where it ended up" axis).
  - For B013: ``l1_gating``, ``l2_vol_scaling``, ``l3_crisis_cut``, and
    ``defensive_routing``.

  Per-period per-layer attribution =
  ``capital_t * parked_fraction_L,t * (defensive_return_t - avg_risk_return_t)``.
  The fraction is the marginal share of risk-asset capital each layer routed
  out of the risky allocation (so the four B013 fractions plus the surviving
  risk fraction sum to 1.0 each period). When risk assets out-earn the
  defensive (typical calm period), ``defensive_return - avg_risk`` is
  negative, so each layer's attribution is negative — that is the drag.

  ``defensive_routing`` here is the *base* defensive sleeve weight (any
  allocation that was defensive *before* exposure-reduction layers ran).
  For B010 that base is zero, so the layer is reported as 0.0 unless the
  caller explicitly populates ``base_defensive_share``.

  The four layers' sum is approximately the total gap when the benchmark's
  realised return tracks the strategy's risk-side average — a sanity
  identity verified by the unit tests with canned data.

- **Total gap** = ``strategy_ending - benchmark_ending`` (signed dollars).

Edge cases handled: empty attribution input, periods with zero capital,
single-asset strategies, missing benchmark dates (benchmark_ending falls
back to ``starting_capital``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

B010_LAYERS: tuple[str, ...] = ("l2_vol_scaling", "defensive_routing")
B013_LAYERS: tuple[str, ...] = (
    "l1_gating",
    "l2_vol_scaling",
    "l3_crisis_cut",
    "defensive_routing",
)


@dataclass(frozen=True, slots=True)
class PeriodAttribution:
    """One backtest period's attribution-relevant snapshot.

    ``target_weights`` is the post-routing weight dict (the same dict the
    backtester used to allocate capital). ``asset_returns`` is per-asset
    realised return between this period's start and end (decimal fraction
    such as ``0.012`` for +1.2%). ``parked_by_layer`` is the marginal share
    of risk-asset capital that each layer routed out — its entries should
    sum (with the surviving risk fraction) to 1.0 in the period.

    Layer keys present in ``parked_by_layer`` should be a subset of the
    strategy's declared ``layer_names`` (B010_LAYERS or B013_LAYERS).
    """

    signal_date: date
    starting_value: float
    target_weights: dict[str, float] = field(default_factory=dict)
    asset_returns: dict[str, float] = field(default_factory=dict)
    parked_by_layer: dict[str, float] = field(default_factory=dict)
    base_defensive_share: float = 0.0
    defensive_asset: str | None = None


@dataclass(frozen=True, slots=True)
class AttributionInput:
    strategy: str
    starting_capital: float
    layer_names: tuple[str, ...]
    periods: tuple[PeriodAttribution, ...]


@dataclass(frozen=True, slots=True)
class AttributionReport:
    strategy: str
    starting_capital: float
    strategy_ending: float
    benchmark_ending: float
    total_gap: float
    per_asset_contribution: dict[str, float]
    per_layer_contribution: dict[str, float]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def compute_per_asset_contribution(
    attribution_input: AttributionInput,
) -> dict[str, float]:
    """Cumulative dollar contribution to strategy total return per asset."""

    contributions: dict[str, float] = {}
    for period in attribution_input.periods:
        if period.starting_value <= 0:
            continue
        for symbol, weight in period.target_weights.items():
            asset_return = period.asset_returns.get(symbol, 0.0)
            increment = period.starting_value * weight * asset_return
            contributions[symbol] = contributions.get(symbol, 0.0) + increment
    return contributions


def compute_per_layer_contribution(
    attribution_input: AttributionInput,
    benchmark_curve: Sequence[tuple[date, float]],
) -> dict[str, float]:
    """Per-layer dollar attribution to the gap (strategy - benchmark).

    Each layer's dollar attribution is the signed period-wise sum of
    ``capital_t * parked_fraction_t * (defensive_return_t - avg_risk_return_t)``.
    The benchmark curve is accepted for parity with the public API and to
    permit future cross-checks against benchmark-relative attribution; the
    current implementation does not consume it directly because each layer
    already has a clean strategy-internal definition.
    """

    # benchmark_curve is part of the documented public API; reference it so
    # static analysis acknowledges the parameter is intentionally accepted.
    _ = benchmark_curve

    layer_contributions: dict[str, float] = {name: 0.0 for name in attribution_input.layer_names}

    for period in attribution_input.periods:
        if period.starting_value <= 0:
            continue
        avg_risk = _avg_risk_return(period)
        defensive_return = _defensive_return(period)
        differential = defensive_return - avg_risk  # negative when calm risk-up market

        # Each parked-by-layer fraction is a share of capital (decimal of 1.0).
        for layer_name in attribution_input.layer_names:
            if layer_name == "defensive_routing":
                share = period.base_defensive_share
            else:
                share = period.parked_by_layer.get(layer_name, 0.0)
            if share == 0.0:
                continue
            layer_contributions[layer_name] += period.starting_value * share * differential
    return layer_contributions


def attribution_summary(
    attribution_input: AttributionInput,
    benchmark_curve: Sequence[tuple[date, float]],
) -> AttributionReport:
    """Combined per-asset + per-layer + total-gap report."""

    per_asset = compute_per_asset_contribution(attribution_input)
    per_layer = compute_per_layer_contribution(attribution_input, benchmark_curve)
    strategy_ending = _strategy_ending(attribution_input)
    benchmark_ending = _benchmark_ending(attribution_input, benchmark_curve)
    return AttributionReport(
        strategy=attribution_input.strategy,
        starting_capital=attribution_input.starting_capital,
        strategy_ending=strategy_ending,
        benchmark_ending=benchmark_ending,
        total_gap=strategy_ending - benchmark_ending,
        per_asset_contribution=per_asset,
        per_layer_contribution=per_layer,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _avg_risk_return(period: PeriodAttribution) -> float:
    """Weight-weighted average return of non-defensive assets in this period."""

    risk_weights: dict[str, float] = {}
    for symbol, weight in period.target_weights.items():
        if period.defensive_asset is not None and symbol == period.defensive_asset:
            continue
        risk_weights[symbol] = weight
    total = sum(risk_weights.values())
    if total <= 0:
        # No risk allocation in this period — opportunity cost is undefined;
        # treat as zero so the layer attribution falls back to the defensive
        # return baseline (i.e., no drag attributed to this period).
        return _defensive_return(period)
    weighted = sum(
        weight * period.asset_returns.get(symbol, 0.0)
        for symbol, weight in risk_weights.items()
    )
    return weighted / total


def _defensive_return(period: PeriodAttribution) -> float:
    if period.defensive_asset is None:
        return 0.0
    return period.asset_returns.get(period.defensive_asset, 0.0)


def _strategy_ending(attribution_input: AttributionInput) -> float:
    """Cumulative strategy ending value implied by per-period weighted returns.

    Compounds each period's strategy return through the starting capital.
    Period strategy return = ``sum(weight_i * asset_return_i)``.
    """

    capital = attribution_input.starting_capital
    for period in attribution_input.periods:
        period_return = sum(
            weight * period.asset_returns.get(symbol, 0.0)
            for symbol, weight in period.target_weights.items()
        )
        capital *= 1.0 + period_return
    return capital


def _benchmark_ending(
    attribution_input: AttributionInput,
    benchmark_curve: Sequence[tuple[date, float]],
) -> float:
    """Benchmark ending value aligned with the strategy's window.

    Falls back to ``starting_capital`` when no benchmark observation is
    available — keeps ``total_gap`` finite for callers that pass an empty
    or non-overlapping curve.
    """

    if not benchmark_curve:
        return attribution_input.starting_capital
    if not attribution_input.periods:
        return float(benchmark_curve[-1][1])
    sorted_curve: list[tuple[date, float]] = sorted(benchmark_curve, key=lambda item: item[0])
    start_target = attribution_input.periods[0].signal_date
    end_target = attribution_input.periods[-1].signal_date
    start_value = _curve_value_at_or_before(sorted_curve, start_target)
    end_value = _curve_value_at_or_before(sorted_curve, end_target)
    if start_value is None or end_value is None or start_value <= 0:
        return attribution_input.starting_capital
    benchmark_return = (end_value / start_value) - 1.0
    return attribution_input.starting_capital * (1.0 + benchmark_return)


def _curve_value_at_or_before(
    sorted_curve: Sequence[tuple[date, float]], target: date
) -> float | None:
    last: float | None = None
    for item_date, value in sorted_curve:
        if item_date > target:
            break
        last = float(value)
    if last is None and sorted_curve:
        # Target is before all curve dates; fall back to the first observation.
        return float(sorted_curve[0][1])
    return last


def compute_period_asset_returns(
    prices_by_symbol: Mapping[str, Sequence[tuple[date, float]]],
    period_boundaries: Sequence[tuple[date, date]],
) -> list[dict[str, float]]:
    """Per-period per-asset return derived from price history.

    ``prices_by_symbol[symbol]`` is a chronologically sorted sequence of
    ``(date, adjusted_close)`` tuples. ``period_boundaries[t]`` is
    ``(start_date, end_date)`` for period t; the function returns one dict
    per period mapping symbol to the realised return over that boundary
    (uses the most recent observation at-or-before each boundary).
    """

    period_returns: list[dict[str, float]] = []
    for start_date, end_date in period_boundaries:
        returns: dict[str, float] = {}
        for symbol, series in prices_by_symbol.items():
            if not series:
                continue
            start_value = _curve_value_at_or_before(list(series), start_date)
            end_value = _curve_value_at_or_before(list(series), end_date)
            if start_value is None or end_value is None or start_value <= 0:
                continue
            returns[symbol] = (end_value / start_value) - 1.0
        period_returns.append(returns)
    return period_returns
