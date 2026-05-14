"""B015 — three-policy comparative backtest harness.

Runs the regime-adaptive monthly backtest three times — once per
``regime_activation_policy`` — over the same records + signal-date schedule and emits a
per-policy metrics row plus an optional real-snapshot wrapper that gracefully skips when
the B014 yfinance snapshot manifest is absent. The artifact is research-only and never
authorizes any paper or production order flow.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from math import sqrt
from pathlib import Path
from typing import cast

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.backtest import (
    RegimeAdaptiveBacktestResult,
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    POLICY_ALWAYS_ON,
    POLICY_ONLY_CRISIS,
    POLICY_ONLY_NON_NORMAL,
    RegimeActivationPolicy,
    RegimeAdaptiveConfig,
)

COMPARISON_STATUS_RAN = "ran"
COMPARISON_STATUS_SKIPPED = "skipped"

STRESS_WINDOW_2020 = "2020_q1_q4"
STRESS_WINDOW_2022 = "2022_full_year"
STRESS_GATE_PASS = "pass"
STRESS_GATE_FAIL = "fail"
STRESS_GATE_SKIPPED = "skipped"
STRESS_DRAWDOWN_LIMIT = -0.15

DEFAULT_STRESS_WINDOWS: tuple[tuple[date, date, str], ...] = (
    (date(2020, 2, 1), date(2020, 12, 31), STRESS_WINDOW_2020),
    (date(2022, 1, 1), date(2022, 12, 31), STRESS_WINDOW_2022),
)

ORDERED_POLICIES: tuple[str, ...] = (
    POLICY_ALWAYS_ON,
    POLICY_ONLY_NON_NORMAL,
    POLICY_ONLY_CRISIS,
)


@dataclass(frozen=True, slots=True)
class PolicyComparisonRow:
    policy: str
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    max_drawdown: float
    turnover: float
    rebalance_count: int
    regime_distribution: dict[str, int]
    l1_firing_rate: float
    stress_window_max_drawdowns: dict[str, float]
    stress_window_status: dict[str, str]
    ending_value: float
    cost_amount: float


@dataclass(frozen=True, slots=True)
class ActivationPolicyComparisonResult:
    snapshot_status: str
    snapshot_reason: str | None
    snapshot_manifest_id: str | None
    snapshot_date_range: tuple[date, date] | None
    starting_capital: float
    stress_windows: tuple[tuple[date, date, str], ...]
    policy_rows: tuple[PolicyComparisonRow, ...]


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveSnapshotBundle:
    records: tuple[PriceBar, ...]
    date_range: tuple[date, date]
    snapshot_id: str
    manifest_path: Path
    tickers: tuple[str, ...] = field(default_factory=tuple)


def run_activation_policy_comparison(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    base_config: RegimeAdaptiveConfig,
    *,
    backtest_parameters: BacktestParameters | None = None,
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    snapshot_status: str = COMPARISON_STATUS_RAN,
    snapshot_reason: str | None = None,
    snapshot_manifest_id: str | None = None,
    snapshot_date_range: tuple[date, date] | None = None,
) -> ActivationPolicyComparisonResult:
    """Backtest B013 three times — once per activation policy — and collect metrics."""

    parameters = backtest_parameters or BacktestParameters()
    rows: list[PolicyComparisonRow] = []
    for policy in ORDERED_POLICIES:
        policy_config = replace(
            base_config,
            regime_activation_policy=cast(RegimeActivationPolicy, policy),
        )
        result = run_regime_adaptive_monthly_backtest(
            records,
            signal_dates,
            policy_config,
            parameters,
        )
        rows.append(_build_row(policy, result, stress_windows))
    return ActivationPolicyComparisonResult(
        snapshot_status=snapshot_status,
        snapshot_reason=snapshot_reason,
        snapshot_manifest_id=snapshot_manifest_id,
        snapshot_date_range=snapshot_date_range,
        starting_capital=parameters.starting_capital,
        stress_windows=tuple(stress_windows),
        policy_rows=tuple(rows),
    )


def _build_row(
    policy: str,
    result: RegimeAdaptiveBacktestResult,
    stress_windows: Sequence[tuple[date, date, str]],
) -> PolicyComparisonRow:
    period_returns = _period_returns(result)
    annualized_volatility = _annualized_volatility(period_returns)
    annualized_return = _annualized_return(result)
    sharpe = _sharpe(annualized_return, annualized_volatility)
    max_drawdown = _max_drawdown(
        tuple(point.value for point in result.equity_curve)
    )
    regime_distribution = _regime_distribution(result)
    l1_firing_rate = _l1_firing_rate(result)
    window_max_dd, window_status = _evaluate_stress_windows(result, stress_windows)
    return PolicyComparisonRow(
        policy=policy,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        turnover=result.turnover,
        rebalance_count=len(result.rebalance_results),
        regime_distribution=regime_distribution,
        l1_firing_rate=l1_firing_rate,
        stress_window_max_drawdowns=window_max_dd,
        stress_window_status=window_status,
        ending_value=result.ending_value,
        cost_amount=result.cost_amount,
    )


def build_monthly_signal_dates(
    trading_dates: Sequence[date],
    start: date,
    end: date,
) -> tuple[date, ...]:
    """Pick the last trading date observed in each calendar month within [start, end]."""

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


def load_regime_adaptive_snapshot_records(
    manifest_path: Path,
) -> RegimeAdaptiveSnapshotBundle:
    """Read the B014 yfinance manifest + per-ticker CSVs into a deterministic bundle."""

    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    snapshot_id = manifest.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError(f"manifest missing snapshot_id: {manifest_path}")
    file_entries = manifest.get("files") or []
    records: list[PriceBar] = []
    tickers: list[str] = []
    for entry in file_entries:
        ticker = entry.get("ticker")
        csv_path = Path(entry["path"])
        if not csv_path.is_absolute():
            csv_path = manifest_path.parent / csv_path.name
        if not csv_path.is_file():
            raise FileNotFoundError(f"manifest references missing CSV: {csv_path}")
        ticker_rows = _read_ticker_csv(csv_path, ticker)
        records.extend(ticker_rows)
        tickers.append(str(ticker))
    if not records:
        raise ValueError(f"manifest produced no price records: {manifest_path}")
    sorted_records = tuple(sorted(records, key=lambda item: (item.date, item.symbol)))
    date_range = (sorted_records[0].date, sorted_records[-1].date)
    return RegimeAdaptiveSnapshotBundle(
        records=sorted_records,
        date_range=date_range,
        snapshot_id=snapshot_id,
        manifest_path=manifest_path,
        tickers=tuple(tickers),
    )


def try_run_real_snapshot_activation_policy_comparison(
    manifest_path: Path,
    base_config: RegimeAdaptiveConfig,
    *,
    backtest_parameters: BacktestParameters | None = None,
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    window_start: date | None = None,
    window_end: date | None = None,
) -> ActivationPolicyComparisonResult:
    """Run the comparison on the B014 snapshot, returning a SKIPPED row when absent."""

    parameters = backtest_parameters or BacktestParameters()
    if not manifest_path.is_file():
        return ActivationPolicyComparisonResult(
            snapshot_status=COMPARISON_STATUS_SKIPPED,
            snapshot_reason=f"manifest not found at {manifest_path}",
            snapshot_manifest_id=None,
            snapshot_date_range=None,
            starting_capital=parameters.starting_capital,
            stress_windows=tuple(stress_windows),
            policy_rows=(),
        )
    bundle = load_regime_adaptive_snapshot_records(manifest_path)
    effective_start = window_start or bundle.date_range[0]
    effective_end = window_end or bundle.date_range[1]
    trading_dates = tuple(sorted({record.date for record in bundle.records}))
    signal_dates = build_monthly_signal_dates(trading_dates, effective_start, effective_end)
    if not signal_dates:
        return ActivationPolicyComparisonResult(
            snapshot_status=COMPARISON_STATUS_SKIPPED,
            snapshot_reason="no monthly signal dates inside the requested window",
            snapshot_manifest_id=bundle.snapshot_id,
            snapshot_date_range=bundle.date_range,
            starting_capital=parameters.starting_capital,
            stress_windows=tuple(stress_windows),
            policy_rows=(),
        )
    return run_activation_policy_comparison(
        bundle.records,
        signal_dates,
        base_config,
        backtest_parameters=parameters,
        stress_windows=stress_windows,
        snapshot_status=COMPARISON_STATUS_RAN,
        snapshot_reason=None,
        snapshot_manifest_id=bundle.snapshot_id,
        snapshot_date_range=bundle.date_range,
    )


def _read_ticker_csv(path: Path, ticker: object) -> list[PriceBar]:
    if not isinstance(ticker, str) or not ticker:
        raise ValueError(f"manifest entry for {path} has no ticker symbol")
    rows: list[PriceBar] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "date" not in reader.fieldnames:
            raise ValueError(f"{path} is missing the 'date' column")
        for raw in reader:
            rows.append(
                PriceBar(
                    date=date.fromisoformat(raw["date"]),
                    symbol=ticker,
                    open=float(raw["open"]),
                    close=float(raw["close"]),
                    adjusted_close=float(raw["adjusted_close"]),
                    volume=int(float(raw["volume"])),
                )
            )
    return rows


def _period_returns(result: RegimeAdaptiveBacktestResult) -> tuple[float, ...]:
    returns: list[float] = []
    for earlier, later in zip(result.equity_curve, result.equity_curve[1:], strict=False):
        if earlier.value <= 0:
            continue
        returns.append(later.value / earlier.value - 1.0)
    return tuple(returns)


def _annualized_volatility(period_returns: tuple[float, ...]) -> float:
    if len(period_returns) < 2:
        return 0.0
    mean = sum(period_returns) / len(period_returns)
    variance = sum((value - mean) ** 2 for value in period_returns) / (len(period_returns) - 1)
    return sqrt(variance) * sqrt(12.0)


def _annualized_return(result: RegimeAdaptiveBacktestResult) -> float:
    periods = max(len(result.equity_curve) - 1, 1)
    if result.starting_capital <= 0:
        return 0.0
    return float((result.ending_value / result.starting_capital) ** (12.0 / periods) - 1.0)


def _sharpe(annualized_return: float, annualized_volatility: float) -> float:
    if annualized_volatility == 0:
        return 0.0
    return annualized_return / annualized_volatility


def _max_drawdown(values: tuple[float, ...]) -> float:
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


def _regime_distribution(result: RegimeAdaptiveBacktestResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for period in result.rebalance_results:
        label = period.regime_state.regime
        counts[label] = counts.get(label, 0) + 1
    return counts


def _l1_firing_rate(result: RegimeAdaptiveBacktestResult) -> float:
    if not result.rebalance_results:
        return 0.0
    active_count = sum(1 for period in result.rebalance_results if period.l1_active)
    return active_count / len(result.rebalance_results)


def _evaluate_stress_windows(
    result: RegimeAdaptiveBacktestResult,
    stress_windows: Sequence[tuple[date, date, str]],
) -> tuple[dict[str, float], dict[str, str]]:
    window_max_dd: dict[str, float] = {}
    window_status: dict[str, str] = {}
    curve = [(point.date, point.value) for point in result.equity_curve]
    for window_start, window_end, key in stress_windows:
        window_points = [
            (point_date, value)
            for point_date, value in curve
            if window_start <= point_date <= window_end
        ]
        if not window_points:
            window_max_dd[key] = 0.0
            window_status[key] = STRESS_GATE_SKIPPED
            continue
        peak = window_points[0][1]
        max_dd = 0.0
        for _, value in window_points:
            peak = max(peak, value)
            if peak <= 0:
                continue
            drawdown = value / peak - 1.0
            max_dd = min(max_dd, drawdown)
        window_max_dd[key] = max_dd
        window_status[key] = (
            STRESS_GATE_PASS if max_dd >= STRESS_DRAWDOWN_LIMIT else STRESS_GATE_FAIL
        )
    return window_max_dd, window_status
