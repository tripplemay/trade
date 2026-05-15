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
    DEFAULT_REBALANCE_FREQUENCY as REGIME_DEFAULT_REBALANCE_FREQUENCY,
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
DIMENSION_CADENCE_VOL_TARGET = "cadence_vol_target"


@dataclass(frozen=True, slots=True)
class SweepWindow:
    """One backtest window for a sweep iteration."""

    name: str
    start_date: date
    end_date: date
    benchmark_ending_value: float | None = None


@dataclass(frozen=True, slots=True)
class SweepRunResult:
    """One sweep cell: strategy × dimension-value × window.

    The trailing optional fields ``cadence`` / ``vol_target`` / ``is_baseline``
    were added in B019 for the joint cadence×vol-target sweep so the gate
    evaluator can group cells by typed (cadence, vol_target) keys without
    re-parsing the ``value`` string. They default to ``None`` / ``False`` so
    B018 callsites continue to work unchanged.
    """

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
    cadence: str | None = None
    vol_target: float | None = None
    is_baseline: bool = False


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
# B019 — joint cadence × vol-target sweep + retune-gate dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RetuneGate:
    """Four-condition acceptance gate for a (cadence, vol_target) candidate."""

    min_calm_uplift_pct: float = 1.0
    min_calm_gap_narrowing_pp: float = 5.0
    do_no_harm_on_stress: bool = True
    max_turnover_increase_pct: float = 15.0


DEFAULT_GATE: RetuneGate = RetuneGate()


@dataclass(frozen=True, slots=True)
class CellGateVerdict:
    """Per-(cadence, vol_target) gate outcome with all four condition flags."""

    cadence: str
    vol_target: float
    calm_ending_value: float
    baseline_calm_ending_value: float
    calm_uplift_pct: float
    calm_gap_narrowing_pp: float
    stress_max_dd_deltas: tuple[tuple[str, float], ...]
    calm_turnover: float
    baseline_calm_turnover: float
    turnover_increase_pct: float
    pass_calm_uplift: bool
    pass_calm_gap_narrowing: bool
    pass_stress_do_no_harm: bool
    pass_turnover: bool
    all_pass: bool


@dataclass(frozen=True, slots=True)
class RetuneGateVerdict:
    """Top-level retune verdict for one strategy on one snapshot."""

    strategy: str
    gate: RetuneGate
    default_cadence: str
    default_vol_target: float
    calm_window: str
    stress_windows: tuple[str, ...]
    cells: tuple[CellGateVerdict, ...]
    gate_met: bool
    winning_cell: tuple[str, float] | None


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


def run_cadence_vs_default_sweep(
    records: tuple[PriceBar, ...],
    strategy_name: str,
    cadences: Sequence[str],
    vol_targets: Sequence[float],
    windows: Sequence[SweepWindow],
    *,
    default_baseline: bool = True,
    backtest_parameters: BacktestParameters | None = None,
) -> list[SweepRunResult]:
    """Joint (cadence × vol_target) sweep plus the strategy default baseline.

    Returns one row per (cadence, vol_target, window) for the explicit grid
    plus, when ``default_baseline=True``, one extra row per window that
    holds the strategy's *current* default ``(cadence, vol_target)``. The
    default values are read from the live ``RiskParityParameters()`` /
    ``RegimeAdaptiveConfig()`` instance so the gate evaluator always
    compares deltas against the real on-disk default rather than a
    hard-coded constant.

    Cell rows carry ``cadence``, ``vol_target``, and ``is_baseline=False``.
    Baseline rows carry the same metadata with ``is_baseline=True``.
    """

    _validate_strategy(strategy_name)
    parameters = backtest_parameters or BacktestParameters()
    results: list[SweepRunResult] = []

    for cadence in cadences:
        for target in vol_targets:
            for window in windows:
                results.append(
                    _run_cadence_vol_target_cell(
                        records=records,
                        strategy_name=strategy_name,
                        cadence=cadence,
                        vol_target=target,
                        window=window,
                        parameters=parameters,
                        is_baseline=False,
                    )
                )

    if default_baseline:
        default_cadence, default_vt = _default_cadence_vol_target(strategy_name)
        for window in windows:
            results.append(
                _run_cadence_vol_target_cell(
                    records=records,
                    strategy_name=strategy_name,
                    cadence=default_cadence,
                    vol_target=default_vt,
                    window=window,
                    parameters=parameters,
                    is_baseline=True,
                )
            )

    return results


def evaluate_retune_gate(
    results: Sequence[SweepRunResult],
    strategy_name: str,
    *,
    calm_window: str,
    stress_windows: Sequence[str],
    gate: RetuneGate = DEFAULT_GATE,
    starting_capital: float | None = None,
) -> RetuneGateVerdict:
    """Evaluate the four-condition retune gate over a cadence-vs-default sweep.

    The verdict is deterministic: cells are iterated in sorted
    ``(cadence, vol_target)`` order, and the winning cell (when multiple
    candidates pass) is selected by the spec-mandated tiebreaker
    ``(highest calm ending value, lowest stress-2 max DD, lowest turnover)``.
    """

    _validate_strategy(strategy_name)
    if starting_capital is None:
        starting_capital = BacktestParameters().starting_capital
    stress_window_tuple = tuple(stress_windows)

    strategy_rows = [row for row in results if row.strategy == strategy_name]
    baseline_rows = [
        row for row in strategy_rows if row.is_baseline and row.status == STATUS_RAN
    ]
    sweep_rows = [
        row for row in strategy_rows if not row.is_baseline and row.status == STATUS_RAN
    ]

    baseline_by_window: dict[str, SweepRunResult] = {}
    for row in baseline_rows:
        baseline_by_window[row.window] = row

    default_cadence = ""
    default_vt = 0.0
    if baseline_rows:
        first = baseline_rows[0]
        if first.cadence is not None:
            default_cadence = first.cadence
        if first.vol_target is not None:
            default_vt = float(first.vol_target)

    grouped: dict[tuple[str, float], dict[str, SweepRunResult]] = {}
    for row in sweep_rows:
        if row.cadence is None or row.vol_target is None:
            continue
        key = (row.cadence, float(row.vol_target))
        grouped.setdefault(key, {})[row.window] = row

    verdicts: list[CellGateVerdict] = []
    for key in sorted(grouped.keys()):
        cadence, vt = key
        verdicts.append(
            _compute_cell_verdict(
                cadence=cadence,
                vol_target=vt,
                cell_results=grouped[key],
                baseline_results=baseline_by_window,
                calm_window=calm_window,
                stress_windows=stress_window_tuple,
                gate=gate,
                starting_capital=starting_capital,
            )
        )

    winning_cell = _pick_winning_cell(verdicts, stress_window_tuple)
    return RetuneGateVerdict(
        strategy=strategy_name,
        gate=gate,
        default_cadence=default_cadence,
        default_vol_target=default_vt,
        calm_window=calm_window,
        stress_windows=stress_window_tuple,
        cells=tuple(verdicts),
        gate_met=winning_cell is not None,
        winning_cell=winning_cell,
    )


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


def _run_cadence_vol_target_cell(
    *,
    records: tuple[PriceBar, ...],
    strategy_name: str,
    cadence: str,
    vol_target: float,
    window: SweepWindow,
    parameters: BacktestParameters,
    is_baseline: bool,
) -> SweepRunResult:
    value_str = "default" if is_baseline else f"{cadence}@{vol_target:.4f}"
    if cadence not in SUPPORTED_CADENCES:
        return replace(
            _skipped(
                strategy=strategy_name,
                dimension=DIMENSION_CADENCE_VOL_TARGET,
                value=value_str,
                window=window.name,
                reason=(
                    f"cadence {cadence!r} not in supported set "
                    f"{sorted(SUPPORTED_CADENCES)!r}"
                ),
            ),
            cadence=cadence,
            vol_target=vol_target,
            is_baseline=is_baseline,
        )
    if vol_target <= 0:
        return replace(
            _skipped(
                strategy=strategy_name,
                dimension=DIMENSION_CADENCE_VOL_TARGET,
                value=value_str,
                window=window.name,
                reason=f"target_volatility must be positive; got {vol_target}",
            ),
            cadence=cadence,
            vol_target=vol_target,
            is_baseline=is_baseline,
        )
    config = _build_config_with_vol_target(strategy_name, vol_target)
    base = _run_window(
        records=records,
        strategy=strategy_name,
        dimension=DIMENSION_CADENCE_VOL_TARGET,
        value=value_str,
        window=window,
        config=config,
        cadence=cadence,
        parameters=parameters,
    )
    return replace(
        base,
        cadence=cadence,
        vol_target=vol_target,
        is_baseline=is_baseline,
    )


def _default_cadence_vol_target(strategy_name: str) -> tuple[str, float]:
    """Read the strategy's *current* default (cadence, vol_target).

    For B010 the cadence is ``RiskParityParameters().rebalance_frequency``.
    For B013 the config dataclass has no ``rebalance_frequency`` field —
    cadence is applied externally by the caller's signal_dates — so the
    canonical default cadence is read from the module-level
    ``DEFAULT_REBALANCE_FREQUENCY`` constant exposed by
    ``trade.strategies.regime_adaptive.config``.
    """

    if strategy_name == STRATEGY_B010:
        cfg = RiskParityParameters()
        return (cfg.rebalance_frequency, float(cfg.target_volatility))
    cfg_b013 = RegimeAdaptiveConfig()
    return (REGIME_DEFAULT_REBALANCE_FREQUENCY, float(cfg_b013.target_volatility))


def _compute_cell_verdict(
    *,
    cadence: str,
    vol_target: float,
    cell_results: Mapping[str, SweepRunResult],
    baseline_results: Mapping[str, SweepRunResult],
    calm_window: str,
    stress_windows: tuple[str, ...],
    gate: RetuneGate,
    starting_capital: float,
) -> CellGateVerdict:
    calm_cell = cell_results.get(calm_window)
    calm_base = baseline_results.get(calm_window)

    if (
        calm_cell is None
        or calm_base is None
        or calm_cell.status != STATUS_RAN
        or calm_base.status != STATUS_RAN
        or starting_capital <= 0
    ):
        return CellGateVerdict(
            cadence=cadence,
            vol_target=vol_target,
            calm_ending_value=0.0,
            baseline_calm_ending_value=0.0,
            calm_uplift_pct=0.0,
            calm_gap_narrowing_pp=0.0,
            stress_max_dd_deltas=tuple((sw, 0.0) for sw in stress_windows),
            calm_turnover=0.0,
            baseline_calm_turnover=0.0,
            turnover_increase_pct=0.0,
            pass_calm_uplift=False,
            pass_calm_gap_narrowing=False,
            pass_stress_do_no_harm=False,
            pass_turnover=False,
            all_pass=False,
        )

    if calm_base.ending_value <= 0:
        calm_uplift_pct = 0.0
    else:
        calm_uplift_pct = (
            (calm_cell.ending_value - calm_base.ending_value)
            / calm_base.ending_value
            * 100.0
        )

    base_gap_pp = calm_base.gap_vs_60_40 / starting_capital * 100.0
    cell_gap_pp = calm_cell.gap_vs_60_40 / starting_capital * 100.0
    calm_gap_narrowing_pp = abs(base_gap_pp) - abs(cell_gap_pp)

    if calm_base.turnover <= 0:
        turnover_increase_pct = 0.0 if calm_cell.turnover <= 0 else float("inf")
    else:
        turnover_increase_pct = (
            (calm_cell.turnover - calm_base.turnover) / calm_base.turnover * 100.0
        )

    stress_deltas: list[tuple[str, float]] = []
    do_no_harm = True
    for stress_name in stress_windows:
        cell_s = cell_results.get(stress_name)
        base_s = baseline_results.get(stress_name)
        if (
            cell_s is None
            or base_s is None
            or cell_s.status != STATUS_RAN
            or base_s.status != STATUS_RAN
        ):
            stress_deltas.append((stress_name, 0.0))
            do_no_harm = False
            continue
        delta = cell_s.max_drawdown - base_s.max_drawdown
        stress_deltas.append((stress_name, delta))
        if cell_s.max_drawdown < base_s.max_drawdown - 1e-9:
            do_no_harm = False

    pass_calm_uplift = calm_uplift_pct >= gate.min_calm_uplift_pct
    pass_calm_gap_narrowing = calm_gap_narrowing_pp >= gate.min_calm_gap_narrowing_pp
    pass_stress_do_no_harm = do_no_harm if gate.do_no_harm_on_stress else True
    pass_turnover = turnover_increase_pct <= gate.max_turnover_increase_pct
    all_pass = (
        pass_calm_uplift
        and pass_calm_gap_narrowing
        and pass_stress_do_no_harm
        and pass_turnover
    )

    return CellGateVerdict(
        cadence=cadence,
        vol_target=vol_target,
        calm_ending_value=calm_cell.ending_value,
        baseline_calm_ending_value=calm_base.ending_value,
        calm_uplift_pct=calm_uplift_pct,
        calm_gap_narrowing_pp=calm_gap_narrowing_pp,
        stress_max_dd_deltas=tuple(stress_deltas),
        calm_turnover=calm_cell.turnover,
        baseline_calm_turnover=calm_base.turnover,
        turnover_increase_pct=turnover_increase_pct,
        pass_calm_uplift=pass_calm_uplift,
        pass_calm_gap_narrowing=pass_calm_gap_narrowing,
        pass_stress_do_no_harm=pass_stress_do_no_harm,
        pass_turnover=pass_turnover,
        all_pass=all_pass,
    )


def _pick_winning_cell(
    cells: Sequence[CellGateVerdict],
    stress_windows: tuple[str, ...],
) -> tuple[str, float] | None:
    passing = [cell for cell in cells if cell.all_pass]
    if not passing:
        return None
    if len(stress_windows) >= 2:
        tiebreak_window: str | None = stress_windows[1]
    elif len(stress_windows) >= 1:
        tiebreak_window = stress_windows[0]
    else:
        tiebreak_window = None

    def _sort_key(cell: CellGateVerdict) -> tuple[float, float, float, str, float]:
        stress_dd_delta = 0.0
        if tiebreak_window is not None:
            for window_name, delta in cell.stress_max_dd_deltas:
                if window_name == tiebreak_window:
                    stress_dd_delta = delta
                    break
        return (
            -cell.calm_ending_value,
            -stress_dd_delta,
            cell.turnover_increase_pct,
            cell.cadence,
            cell.vol_target,
        )

    winner = min(passing, key=_sort_key)
    return (winner.cadence, winner.vol_target)


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
    "DEFAULT_GATE",
    "DEFAULT_UNIVERSE_VARIANTS",
    "DEFAULT_VOL_TARGETS",
    "DIMENSION_CADENCE",
    "DIMENSION_CADENCE_VOL_TARGET",
    "DIMENSION_UNIVERSE",
    "DIMENSION_VOL_TARGET",
    "STATUS_RAN",
    "STATUS_SKIPPED",
    "STRATEGY_B010",
    "STRATEGY_B013",
    "SUPPORTED_CADENCES",
    "CellGateVerdict",
    "RetuneGate",
    "RetuneGateVerdict",
    "SweepRunResult",
    "SweepWindow",
    "UniverseVariant",
    "VALID_STRATEGIES",
    "build_monthly_signal_dates",
    "evaluate_retune_gate",
    "run_cadence_sweep",
    "run_cadence_vs_default_sweep",
    "run_universe_ablation_sweep",
    "run_vol_target_sweep",
)


# Reference the helpers that are intentionally exported even if not used in
# this module body; keeps ruff F401 silent on the analysis-level builders.
_ = (field,)
