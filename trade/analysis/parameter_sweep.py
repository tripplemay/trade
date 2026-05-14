"""B018 — parameter sweep harness for B010 / B013 along three axes.

Pure-stdlib (math + statistics + dataclasses + typing + collections.abc only;
no scipy / numpy / pandas / sklearn / networkx / third-party). Research-only.

Drives the existing B010 (``run_risk_parity_monthly_backtest``) and B013
(``run_regime_adaptive_monthly_backtest``) entry points against pre-loaded
``PriceBar`` records for parameter variations along three axes:

- ``run_vol_target_sweep``: target_volatility ∈ {0.05, 0.08, 0.10, 0.12, 0.15}.
- ``run_universe_ablation_sweep``: 4-5 universe variants (full,
  drop_SGOV, drop_stabilizers, SPY+IEF only, SPY only).
- ``run_cadence_sweep``: monthly / quarterly / semiannual / annual derived
  by filtering monthly signal dates.

Each sweep returns a deterministic list of :class:`SweepRunResult` —
``status='ran'`` rows include ``ending_value``, ``gap_vs_60_40`` (if a
benchmark ending value is supplied), ``max_drawdown``, ``turnover``,
``transaction_costs``, ``sharpe``. ``status='skipped'`` rows include a
diagnostic reason and zeroed metric fields.

**Strategy-default safety:** every override config is constructed inline
via ``dataclasses.replace`` (frozen dataclasses cannot be mutated in
place). The strategy module's default parameters are never touched.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from math import sqrt
from typing import Any, cast

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import (
    RiskParityBacktestResult,
    run_risk_parity_monthly_backtest,
)
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.backtest import (
    RegimeAdaptiveBacktestResult,
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    AssetEntry,
    RegimeAdaptiveConfig,
)
from trade.strategies.risk_parity import RiskParityParameters

STRATEGY_B010 = "b010"
STRATEGY_B013 = "b013"
VALID_STRATEGIES: frozenset[str] = frozenset({STRATEGY_B010, STRATEGY_B013})

CADENCE_MONTHLY = "monthly"
CADENCE_QUARTERLY = "quarterly"
CADENCE_SEMIANNUAL = "semiannual"
CADENCE_ANNUAL = "annual"
SUPPORTED_CADENCES: frozenset[str] = frozenset(
    {CADENCE_MONTHLY, CADENCE_QUARTERLY, CADENCE_SEMIANNUAL, CADENCE_ANNUAL}
)
_CADENCE_TO_STRIDE: Mapping[str, int] = {
    CADENCE_MONTHLY: 1,
    CADENCE_QUARTERLY: 3,
    CADENCE_SEMIANNUAL: 6,
    CADENCE_ANNUAL: 12,
}

STATUS_RAN = "ran"
STATUS_SKIPPED = "skipped"

DIMENSION_VOL_TARGET = "vol_target"
DIMENSION_UNIVERSE = "universe"
DIMENSION_CADENCE = "cadence"


@dataclass(frozen=True, slots=True)
class SweepWindow:
    """One backtest window for a sweep iteration."""

    name: str
    start_date: date
    end_date: date
    benchmark_ending_value: float | None = None


@dataclass(frozen=True, slots=True)
class SweepRunResult:
    """One sweep cell: strategy × dimension-value × window."""

    strategy: str
    dimension: str
    value: str
    window: str
    status: str
    skipped_reason: str | None
    ending_value: float
    gap_vs_60_40: float
    max_drawdown: float
    turnover: float
    transaction_costs: float
    sharpe: float
    rebalance_count: int = 0


@dataclass(frozen=True, slots=True)
class UniverseVariant:
    """Universe ablation variant: a name plus the kept asset subset."""

    name: str
    symbols: tuple[str, ...]


DEFAULT_VOL_TARGETS: tuple[float, ...] = (0.05, 0.08, 0.10, 0.12, 0.15)

DEFAULT_UNIVERSE_VARIANTS: tuple[UniverseVariant, ...] = (
    UniverseVariant(
        "full",
        ("SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC", "SGOV"),
    ),
    UniverseVariant(
        "drop_sgov",
        ("SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC"),
    ),
    UniverseVariant(
        "drop_stabilizers",
        ("SPY", "QQQ", "VEA", "VWO", "SGOV"),
    ),
    UniverseVariant("spy_ief", ("SPY", "IEF")),
    UniverseVariant("spy_only", ("SPY",)),
)

DEFAULT_CADENCES: tuple[str, ...] = (
    CADENCE_MONTHLY,
    CADENCE_QUARTERLY,
    CADENCE_SEMIANNUAL,
    CADENCE_ANNUAL,
)

# --------------------------------------------------------------------------- #
# Public sweep entry points
# --------------------------------------------------------------------------- #


def run_vol_target_sweep(
    records: tuple[PriceBar, ...],
    strategy_name: str,
    targets: Sequence[float],
    windows: Sequence[SweepWindow],
    backtest_parameters: BacktestParameters | None = None,
) -> list[SweepRunResult]:
    """Run a vol-target sweep across the supplied targets × windows."""

    _validate_strategy(strategy_name)
    results: list[SweepRunResult] = []
    parameters = backtest_parameters or BacktestParameters()
    for target in targets:
        for window in windows:
            if target <= 0:
                results.append(
                    _skipped(
                        strategy=strategy_name,
                        dimension=DIMENSION_VOL_TARGET,
                        value=_serialize(target),
                        window=window.name,
                        reason=f"target_volatility must be positive; got {target}",
                    )
                )
                continue
            config = _build_config_with_vol_target(strategy_name, target)
            results.append(
                _run_window(
                    records=records,
                    strategy=strategy_name,
                    dimension=DIMENSION_VOL_TARGET,
                    value=_serialize(target),
                    window=window,
                    config=config,
                    cadence=CADENCE_MONTHLY,
                    parameters=parameters,
                )
            )
    return results


def run_universe_ablation_sweep(
    records: tuple[PriceBar, ...],
    strategy_name: str,
    variants: Sequence[UniverseVariant],
    windows: Sequence[SweepWindow],
    backtest_parameters: BacktestParameters | None = None,
) -> list[SweepRunResult]:
    """Run a universe-ablation sweep across the supplied variants × windows."""

    _validate_strategy(strategy_name)
    results: list[SweepRunResult] = []
    parameters = backtest_parameters or BacktestParameters()
    for variant in variants:
        for window in windows:
            try:
                config = _build_config_with_universe(strategy_name, variant)
            except ValueError as exc:
                results.append(
                    _skipped(
                        strategy=strategy_name,
                        dimension=DIMENSION_UNIVERSE,
                        value=variant.name,
                        window=window.name,
                        reason=str(exc),
                    )
                )
                continue
            results.append(
                _run_window(
                    records=records,
                    strategy=strategy_name,
                    dimension=DIMENSION_UNIVERSE,
                    value=variant.name,
                    window=window,
                    config=config,
                    cadence=CADENCE_MONTHLY,
                    parameters=parameters,
                )
            )
    return results


def run_cadence_sweep(
    records: tuple[PriceBar, ...],
    strategy_name: str,
    cadences: Sequence[str],
    windows: Sequence[SweepWindow],
    backtest_parameters: BacktestParameters | None = None,
) -> list[SweepRunResult]:
    """Run a cadence sweep by filtering monthly signal dates to the cadence stride."""

    _validate_strategy(strategy_name)
    results: list[SweepRunResult] = []
    parameters = backtest_parameters or BacktestParameters()
    for cadence in cadences:
        for window in windows:
            if cadence not in SUPPORTED_CADENCES:
                results.append(
                    _skipped(
                        strategy=strategy_name,
                        dimension=DIMENSION_CADENCE,
                        value=cadence,
                        window=window.name,
                        reason=(
                            f"cadence {cadence!r} not in supported set "
                            f"{sorted(SUPPORTED_CADENCES)!r}"
                        ),
                    )
                )
                continue
            config = _build_default_config(strategy_name)
            results.append(
                _run_window(
                    records=records,
                    strategy=strategy_name,
                    dimension=DIMENSION_CADENCE,
                    value=cadence,
                    window=window,
                    config=config,
                    cadence=cadence,
                    parameters=parameters,
                )
            )
    return results


# --------------------------------------------------------------------------- #
# Window-runner: dispatches to B010 / B013 entry, computes metrics
# --------------------------------------------------------------------------- #


def _run_window(
    *,
    records: tuple[PriceBar, ...],
    strategy: str,
    dimension: str,
    value: str,
    window: SweepWindow,
    config: RiskParityParameters | RegimeAdaptiveConfig,
    cadence: str,
    parameters: BacktestParameters,
) -> SweepRunResult:
    trading_dates = tuple(sorted({record.date for record in records}))
    signal_dates = build_monthly_signal_dates(
        trading_dates, window.start_date, window.end_date
    )
    signal_dates = _apply_cadence_stride(signal_dates, cadence)
    if not signal_dates:
        return _skipped(
            strategy=strategy,
            dimension=dimension,
            value=value,
            window=window.name,
            reason=(
                f"no signal dates inside window [{window.start_date}, {window.end_date}]"
                f" after applying cadence {cadence!r}"
            ),
        )
    try:
        if strategy == STRATEGY_B010:
            risk_parity_config = cast(RiskParityParameters, config)
            result_b010 = run_risk_parity_monthly_backtest(
                records, signal_dates, risk_parity_config, parameters
            )
            metrics = _metrics_from_risk_parity(result_b010, parameters)
        else:
            regime_config = cast(RegimeAdaptiveConfig, config)
            result_b013 = run_regime_adaptive_monthly_backtest(
                records, signal_dates, regime_config, parameters
            )
            metrics = _metrics_from_regime_adaptive(result_b013, parameters)
    except Exception as exc:  # noqa: BLE001 - capture any backtest error as skipped
        return _skipped(
            strategy=strategy,
            dimension=dimension,
            value=value,
            window=window.name,
            reason=f"backtest raised {type(exc).__name__}: {exc}",
        )
    gap = (
        metrics["ending_value"] - window.benchmark_ending_value
        if window.benchmark_ending_value is not None
        else 0.0
    )
    return SweepRunResult(
        strategy=strategy,
        dimension=dimension,
        value=value,
        window=window.name,
        status=STATUS_RAN,
        skipped_reason=None,
        ending_value=metrics["ending_value"],
        gap_vs_60_40=gap,
        max_drawdown=metrics["max_drawdown"],
        turnover=metrics["turnover"],
        transaction_costs=metrics["transaction_costs"],
        sharpe=metrics["sharpe"],
        rebalance_count=metrics["rebalance_count"],
    )


def _metrics_from_risk_parity(
    result: RiskParityBacktestResult, parameters: BacktestParameters
) -> dict[str, Any]:
    period_returns = _period_returns(tuple(point.value for point in result.equity_curve))
    annualized_volatility = _annualized_volatility(period_returns)
    annualized_return = _annualized_return(result.equity_curve, parameters.starting_capital)
    return {
        "ending_value": result.ending_value,
        "max_drawdown": _max_drawdown(tuple(point.value for point in result.equity_curve)),
        "turnover": result.turnover,
        "transaction_costs": result.cost_amount,
        "sharpe": _sharpe(annualized_return, annualized_volatility),
        "rebalance_count": len(result.rebalance_results),
    }


def _metrics_from_regime_adaptive(
    result: RegimeAdaptiveBacktestResult, parameters: BacktestParameters
) -> dict[str, Any]:
    period_returns = _period_returns(tuple(point.value for point in result.equity_curve))
    annualized_volatility = _annualized_volatility(period_returns)
    annualized_return = _annualized_return(result.equity_curve, parameters.starting_capital)
    return {
        "ending_value": result.ending_value,
        "max_drawdown": _max_drawdown(tuple(point.value for point in result.equity_curve)),
        "turnover": result.turnover,
        "transaction_costs": result.cost_amount,
        "sharpe": _sharpe(annualized_return, annualized_volatility),
        "rebalance_count": len(result.rebalance_results),
    }


# --------------------------------------------------------------------------- #
# Config builders — strictly via dataclasses.replace; defaults never mutated.
# --------------------------------------------------------------------------- #


def _build_default_config(strategy_name: str) -> RiskParityParameters | RegimeAdaptiveConfig:
    if strategy_name == STRATEGY_B010:
        return RiskParityParameters()
    return RegimeAdaptiveConfig()


def _build_config_with_vol_target(
    strategy_name: str, target: float
) -> RiskParityParameters | RegimeAdaptiveConfig:
    if strategy_name == STRATEGY_B010:
        return replace(RiskParityParameters(), target_volatility=target)
    return replace(RegimeAdaptiveConfig(), target_volatility=target)


def _build_config_with_universe(
    strategy_name: str, variant: UniverseVariant
) -> RiskParityParameters | RegimeAdaptiveConfig:
    if strategy_name == STRATEGY_B010:
        default = RiskParityParameters()
        if default.defensive_asset not in variant.symbols:
            raise ValueError(
                f"variant {variant.name!r} does not contain defensive_asset"
                f" {default.defensive_asset!r} (required by B010 invariants)"
            )
        return replace(default, universe=tuple(variant.symbols))
    default_regime = RegimeAdaptiveConfig()
    if default_regime.defensive_symbol not in variant.symbols:
        raise ValueError(
            f"variant {variant.name!r} does not contain defensive_symbol"
            f" {default_regime.defensive_symbol!r} (required by B013 invariants)"
        )
    if default_regime.regime_spy_symbol not in variant.symbols:
        raise ValueError(
            f"variant {variant.name!r} does not contain regime_spy_symbol"
            f" {default_regime.regime_spy_symbol!r} (required by B013 regime detector)"
        )
    universe = tuple(
        entry for entry in default_regime.universe if entry.symbol in variant.symbols
    )
    if not _has_risk_core(universe):
        raise ValueError(
            f"variant {variant.name!r} contains no risk_core asset; "
            "B013 requires at least one risk_core symbol"
        )
    return replace(default_regime, universe=universe)


def _has_risk_core(universe: tuple[AssetEntry, ...]) -> bool:
    return any(entry.category == "risk_core" for entry in universe)


# --------------------------------------------------------------------------- #
# Cadence-stride and signal-date helpers
# --------------------------------------------------------------------------- #


def build_monthly_signal_dates(
    trading_dates: Sequence[date], start: date, end: date
) -> tuple[date, ...]:
    if end < start:
        return ()
    last_by_month: dict[tuple[int, int], date] = {}
    for trading_date in trading_dates:
        if trading_date < start or trading_date > end:
            continue
        key = (trading_date.year, trading_date.month)
        existing = last_by_month.get(key)
        if existing is None or trading_date > existing:
            last_by_month[key] = trading_date
    return tuple(last_by_month[key] for key in sorted(last_by_month))


def _apply_cadence_stride(
    monthly_signal_dates: tuple[date, ...], cadence: str
) -> tuple[date, ...]:
    stride = _CADENCE_TO_STRIDE.get(cadence, 1)
    if stride <= 1:
        return monthly_signal_dates
    return tuple(
        monthly_signal_dates[index]
        for index in range(0, len(monthly_signal_dates), stride)
    )


# --------------------------------------------------------------------------- #
# Metric helpers (pure stdlib)
# --------------------------------------------------------------------------- #


def _period_returns(equity_values: Sequence[float]) -> tuple[float, ...]:
    returns: list[float] = []
    for earlier, later in zip(equity_values, equity_values[1:], strict=False):
        if earlier <= 0:
            continue
        returns.append(later / earlier - 1.0)
    return tuple(returns)


def _annualized_volatility(period_returns: Sequence[float]) -> float:
    if len(period_returns) < 2:
        return 0.0
    mean = sum(period_returns) / len(period_returns)
    variance = sum((value - mean) ** 2 for value in period_returns) / (len(period_returns) - 1)
    return sqrt(variance) * sqrt(12.0)


def _annualized_return(equity_curve: Sequence[Any], starting_capital: float) -> float:
    if starting_capital <= 0 or not equity_curve:
        return 0.0
    periods = max(len(equity_curve) - 1, 1)
    ending = float(equity_curve[-1].value)
    if ending <= 0:
        return 0.0
    return float((ending / starting_capital) ** (12.0 / periods) - 1.0)


def _sharpe(annualized_return: float, annualized_volatility: float) -> float:
    if annualized_volatility == 0:
        return 0.0
    return annualized_return / annualized_volatility


def _max_drawdown(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak <= 0:
            continue
        max_dd = min(max_dd, value / peak - 1.0)
    return max_dd


# --------------------------------------------------------------------------- #
# Bookkeeping helpers
# --------------------------------------------------------------------------- #


def _validate_strategy(strategy_name: str) -> None:
    if strategy_name not in VALID_STRATEGIES:
        raise ValueError(
            f"unknown strategy {strategy_name!r}; expected one of {sorted(VALID_STRATEGIES)!r}"
        )


def _serialize(value: Any) -> str:
    return f"{value}"


def _skipped(
    *,
    strategy: str,
    dimension: str,
    value: str,
    window: str,
    reason: str,
) -> SweepRunResult:
    return SweepRunResult(
        strategy=strategy,
        dimension=dimension,
        value=value,
        window=window,
        status=STATUS_SKIPPED,
        skipped_reason=reason,
        ending_value=0.0,
        gap_vs_60_40=0.0,
        max_drawdown=0.0,
        turnover=0.0,
        transaction_costs=0.0,
        sharpe=0.0,
        rebalance_count=0,
    )


# Public re-export of frozen default tuples for callers that want the
# spec-mandated sweep grids without redeclaring them.
__all__ = (
    "CADENCE_ANNUAL",
    "CADENCE_MONTHLY",
    "CADENCE_QUARTERLY",
    "CADENCE_SEMIANNUAL",
    "DEFAULT_CADENCES",
    "DEFAULT_UNIVERSE_VARIANTS",
    "DEFAULT_VOL_TARGETS",
    "DIMENSION_CADENCE",
    "DIMENSION_UNIVERSE",
    "DIMENSION_VOL_TARGET",
    "STATUS_RAN",
    "STATUS_SKIPPED",
    "STRATEGY_B010",
    "STRATEGY_B013",
    "SUPPORTED_CADENCES",
    "SweepRunResult",
    "SweepWindow",
    "UniverseVariant",
    "VALID_STRATEGIES",
    "build_monthly_signal_dates",
    "run_cadence_sweep",
    "run_universe_ablation_sweep",
    "run_vol_target_sweep",
)


# Reference the helpers that are intentionally exported even if not used in
# this module body; keeps ruff F401 silent on the analysis-level builders.
_ = (field,)
