"""B016 — comparative backtest harness for risk-parity weighting methods.

Runs the B010 monthly backtest under both ``inverse_volatility`` (default
B010 behavior) and ``hrp`` (new B016 De Prado HRP path) on the same record
set, then emits a research-only comparative report with per-method metrics,
2020 / 2022 stress sub-window max drawdowns, per-asset weight history, and a
narrative on whether HRP shrinks the absolute-return gap versus a static
60/40 baseline (sourced from the B014 cross-strategy comparison sidecar when
available).

Two entry points:

- :func:`run_hrp_comparison` — pure-data harness; given a record bundle and a
  list of monthly signal dates, runs both weighting methods and returns a
  :class:`HRPComparisonResult`.
- :func:`try_run_real_snapshot_hrp_comparison` — loads the B014 yfinance
  manifest (if present) and runs the harness over the snapshot's overlapping
  window; falls back to a ``skipped`` result when the manifest is missing.

The artifact is research-only and never authorizes any paper or production
order flow.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from math import sqrt
from pathlib import Path
from typing import Any, cast

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import (
    RiskParityBacktestResult,
    run_risk_parity_monthly_backtest,
)
from trade.data.loader import PriceBar
from trade.strategies.risk_parity import RiskParityParameters

# --------------------------------------------------------------------------- #
# Status / constant strings
# --------------------------------------------------------------------------- #

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

ORDERED_METHODS: tuple[str, ...] = ("inverse_volatility", "hrp")

NARRATIVE_GAP_SHRUNK = "shrunk"
NARRATIVE_GAP_UNCHANGED = "unchanged"
NARRATIVE_GAP_WIDENED = "widened"
NARRATIVE_REAL_DATA_SKIPPED = "real_data_skipped"
NARRATIVE_REAL_DATA_RAN = "real_data_ran"
DEFAULT_GAP_TOLERANCE_DOLLARS = 100.0

RESEARCH_ONLY_DISCLAIMER = (
    "research-only B016 risk-parity HRP comparison; never authorizes paper or "
    "production order flow."
)
RESEARCH_LIMITATIONS_DEFAULT: tuple[str, ...] = (
    RESEARCH_ONLY_DISCLAIMER,
    "no_paper_or_production_order_flow_authorized",
    "fixture_or_research_snapshot_only",
    "60_40_baseline_sourced_from_B014_sidecar_when_available",
    "HRP vs inverse-vol comparison is empirical research finding, not pass/fail",
)


# --------------------------------------------------------------------------- #
# Result data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class HRPMethodRow:
    method: str
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    max_drawdown: float
    turnover: float
    rebalance_count: int
    stress_window_max_drawdowns: dict[str, float]
    stress_window_status: dict[str, str]
    ending_value: float
    cost_amount: float
    weight_history: tuple[tuple[str, dict[str, float]], ...]


@dataclass(frozen=True, slots=True)
class HRPComparisonResult:
    snapshot_status: str
    snapshot_reason: str | None
    snapshot_manifest_id: str | None
    snapshot_date_range: tuple[date, date] | None
    starting_capital: float
    universe: tuple[str, ...]
    stress_windows: tuple[tuple[date, date, str], ...]
    method_rows: tuple[HRPMethodRow, ...]


@dataclass(frozen=True, slots=True)
class HRPSnapshotBundle:
    records: tuple[PriceBar, ...]
    date_range: tuple[date, date]
    snapshot_id: str
    manifest_path: Path
    tickers: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class HRPComparisonArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    payload: dict[str, object]


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


def run_hrp_comparison(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    strategy_template: RiskParityParameters,
    *,
    backtest_parameters: BacktestParameters | None = None,
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    snapshot_status: str = COMPARISON_STATUS_RAN,
    snapshot_reason: str | None = None,
    snapshot_manifest_id: str | None = None,
    snapshot_date_range: tuple[date, date] | None = None,
) -> HRPComparisonResult:
    """Run B010 backtest twice — once per weighting method — and collect metrics.

    ``strategy_template`` provides the universe, lookback, defensive asset,
    target volatility, and max-exposure / max-asset-weight settings; the
    ``weighting_method`` field is overridden for each run.
    """

    parameters = backtest_parameters or BacktestParameters()
    rows: list[HRPMethodRow] = []
    for method in ORDERED_METHODS:
        method_config = replace(strategy_template, weighting_method=cast(Any, method))
        result = run_risk_parity_monthly_backtest(
            records,
            signal_dates,
            method_config,
            parameters,
        )
        rows.append(_build_row(method, result, stress_windows))
    return HRPComparisonResult(
        snapshot_status=snapshot_status,
        snapshot_reason=snapshot_reason,
        snapshot_manifest_id=snapshot_manifest_id,
        snapshot_date_range=snapshot_date_range,
        starting_capital=parameters.starting_capital,
        universe=tuple(strategy_template.universe),
        stress_windows=tuple(stress_windows),
        method_rows=tuple(rows),
    )


def _build_row(
    method: str,
    result: RiskParityBacktestResult,
    stress_windows: Sequence[tuple[date, date, str]],
) -> HRPMethodRow:
    period_returns = _period_returns(result)
    annualized_volatility = _annualized_volatility(period_returns)
    annualized_return = _annualized_return(result)
    sharpe = _sharpe(annualized_return, annualized_volatility)
    max_drawdown = _max_drawdown(
        tuple(point.value for point in result.equity_curve)
    )
    window_max_dd, window_status = _evaluate_stress_windows(result, stress_windows)
    weight_history = tuple(
        (period.signal.signal_date.isoformat(), dict(period.signal.target_weights))
        for period in result.rebalance_results
    )
    return HRPMethodRow(
        method=method,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        turnover=result.turnover,
        rebalance_count=len(result.rebalance_results),
        stress_window_max_drawdowns=window_max_dd,
        stress_window_status=window_status,
        ending_value=result.ending_value,
        cost_amount=result.cost_amount,
        weight_history=weight_history,
    )


def build_monthly_signal_dates(
    trading_dates: Sequence[date],
    start: date,
    end: date,
) -> tuple[date, ...]:
    """Pick the last trading date observed in each calendar month within ``[start, end]``."""

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


def load_hrp_snapshot_records(manifest_path: Path) -> HRPSnapshotBundle:
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
    return HRPSnapshotBundle(
        records=sorted_records,
        date_range=date_range,
        snapshot_id=snapshot_id,
        manifest_path=manifest_path,
        tickers=tuple(tickers),
    )


def try_run_real_snapshot_hrp_comparison(
    manifest_path: Path,
    strategy_template: RiskParityParameters,
    *,
    backtest_parameters: BacktestParameters | None = None,
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    window_start: date | None = None,
    window_end: date | None = None,
) -> HRPComparisonResult:
    """Run the comparison on the B014 snapshot; return ``skipped`` when absent."""

    parameters = backtest_parameters or BacktestParameters()
    if not manifest_path.is_file():
        return HRPComparisonResult(
            snapshot_status=COMPARISON_STATUS_SKIPPED,
            snapshot_reason=f"manifest not found at {manifest_path}",
            snapshot_manifest_id=None,
            snapshot_date_range=None,
            starting_capital=parameters.starting_capital,
            universe=tuple(strategy_template.universe),
            stress_windows=tuple(stress_windows),
            method_rows=(),
        )
    bundle = load_hrp_snapshot_records(manifest_path)
    effective_start = window_start or bundle.date_range[0]
    effective_end = window_end or bundle.date_range[1]
    trading_dates = tuple(sorted({record.date for record in bundle.records}))
    signal_dates = build_monthly_signal_dates(trading_dates, effective_start, effective_end)
    if not signal_dates:
        return HRPComparisonResult(
            snapshot_status=COMPARISON_STATUS_SKIPPED,
            snapshot_reason="no monthly signal dates inside the requested window",
            snapshot_manifest_id=bundle.snapshot_id,
            snapshot_date_range=bundle.date_range,
            starting_capital=parameters.starting_capital,
            universe=tuple(strategy_template.universe),
            stress_windows=tuple(stress_windows),
            method_rows=(),
        )
    return run_hrp_comparison(
        bundle.records,
        signal_dates,
        strategy_template,
        backtest_parameters=parameters,
        stress_windows=stress_windows,
        snapshot_status=COMPARISON_STATUS_RAN,
        snapshot_reason=None,
        snapshot_manifest_id=bundle.snapshot_id,
        snapshot_date_range=bundle.date_range,
    )


# --------------------------------------------------------------------------- #
# B014 sidecar baseline loader (60/40)
# --------------------------------------------------------------------------- #


def load_static_60_40_baseline(comparison_sidecar_path: Path) -> dict[str, object]:
    """Extract the static_60_40 baseline metrics from a B014 sidecar JSON.

    Returns an empty dict when the file is absent or malformed (so the
    report can still render with an empty baseline row).
    """

    if not comparison_sidecar_path.is_file():
        return {}
    try:
        payload = json.loads(comparison_sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    comparison = payload.get("comparison")
    if not isinstance(comparison, dict):
        return {}
    strategies = comparison.get("strategies")
    if not isinstance(strategies, dict):
        return {}
    raw = strategies.get("static_60_40")
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if key != "equity_curve"}


# --------------------------------------------------------------------------- #
# Report payload + Markdown rendering
# --------------------------------------------------------------------------- #


def build_hrp_comparison_payload(
    comparison: HRPComparisonResult,
    *,
    baseline_60_40: Mapping[str, object],
    run_id: str,
    report_date: date,
) -> dict[str, object]:
    """Build the JSON-safe report payload for the B016 HRP comparison."""

    method_rows = [_serialize_method_row(row) for row in comparison.method_rows]
    real_data = _real_data_block(comparison)
    narrative = _build_narrative_block(comparison, baseline_60_40)
    return {
        "run": {
            "run_id": run_id,
            "report_date": report_date.isoformat(),
            "batch": "B016",
            "description": (
                "Comparative backtest of B010 risk parity under two "
                "weighting_method values: inverse_volatility (B010 default) and "
                "hrp (B016 De Prado HRP). B011/B012/B013/B014/B015 strategy code "
                "is unchanged; only RiskParityParameters.weighting_method varies."
            ),
        },
        "real_data_status": real_data,
        "hrp_comparison": {
            "starting_capital": comparison.starting_capital,
            "universe": list(comparison.universe),
            "stress_windows": [
                {
                    "key": key,
                    "window_start": start.isoformat(),
                    "window_end": end.isoformat(),
                }
                for start, end, key in comparison.stress_windows
            ],
            "method_rows": method_rows,
        },
        "baselines": {
            "static_60_40": dict(baseline_60_40),
        },
        "narrative": narrative,
        "research_limitations": {
            "limitations": list(RESEARCH_LIMITATIONS_DEFAULT),
            "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        },
    }


def _serialize_method_row(row: HRPMethodRow) -> dict[str, object]:
    return {
        "method": row.method,
        "annualized_return": row.annualized_return,
        "annualized_volatility": row.annualized_volatility,
        "sharpe": row.sharpe,
        "max_drawdown": row.max_drawdown,
        "turnover": row.turnover,
        "rebalance_count": row.rebalance_count,
        "stress_window_max_drawdowns": dict(row.stress_window_max_drawdowns),
        "stress_window_status": dict(row.stress_window_status),
        "ending_value": row.ending_value,
        "cost_amount": row.cost_amount,
        "weight_history": [
            {"signal_date": signal_date, "weights": dict(weights)}
            for signal_date, weights in row.weight_history
        ],
    }


def _real_data_block(comparison: HRPComparisonResult) -> dict[str, object]:
    block: dict[str, object] = {"status": comparison.snapshot_status}
    if comparison.snapshot_reason is not None:
        block["reason"] = comparison.snapshot_reason
    if comparison.snapshot_manifest_id is not None:
        block["manifest_id"] = comparison.snapshot_manifest_id
    if comparison.snapshot_date_range is not None:
        block["date_range"] = (
            f"{comparison.snapshot_date_range[0].isoformat()}"
            f"..{comparison.snapshot_date_range[1].isoformat()}"
        )
    return block


def _build_narrative_block(
    comparison: HRPComparisonResult,
    baseline_60_40: Mapping[str, object],
) -> dict[str, object]:
    if comparison.snapshot_status != COMPARISON_STATUS_RAN or not comparison.method_rows:
        return {
            "status": NARRATIVE_REAL_DATA_SKIPPED,
            "note": (
                "Narrative is only emitted when the real-data harness ran end-to-end. "
                "The synthetic-fixture branch is a schema smoke check only."
            ),
        }
    by_method: dict[str, HRPMethodRow] = {row.method: row for row in comparison.method_rows}
    inverse_vol_row = by_method.get("inverse_volatility")
    hrp_row = by_method.get("hrp")
    baseline_ending = baseline_60_40.get("ending_value")
    if (
        inverse_vol_row is None
        or hrp_row is None
        or not isinstance(baseline_ending, (int, float))
    ):
        return {
            "status": NARRATIVE_REAL_DATA_SKIPPED,
            "note": (
                "Narrative skipped: missing one of inverse_volatility row, hrp row, or "
                "static_60_40 baseline ending_value (load B014 sidecar to enable)."
            ),
        }
    baseline_value = float(baseline_ending)
    inverse_vol_gap = baseline_value - inverse_vol_row.ending_value
    hrp_gap = baseline_value - hrp_row.ending_value
    delta = inverse_vol_gap - hrp_gap  # positive means HRP closer to 60/40
    if abs(delta) <= DEFAULT_GAP_TOLERANCE_DOLLARS:
        verdict = NARRATIVE_GAP_UNCHANGED
    elif delta > 0:
        verdict = NARRATIVE_GAP_SHRUNK
    else:
        verdict = NARRATIVE_GAP_WIDENED
    return {
        "status": NARRATIVE_REAL_DATA_RAN,
        "baseline_60_40_ending_value": baseline_value,
        "inverse_volatility_ending_value": inverse_vol_row.ending_value,
        "hrp_ending_value": hrp_row.ending_value,
        "inverse_volatility_gap_vs_60_40": inverse_vol_gap,
        "hrp_gap_vs_60_40": hrp_gap,
        "delta_inverse_minus_hrp": delta,
        "verdict": verdict,
        "tolerance_dollars": DEFAULT_GAP_TOLERANCE_DOLLARS,
    }


def render_hrp_comparison_markdown(payload: Mapping[str, object]) -> str:
    """Render the JSON payload into the B016 markdown report."""

    run = cast(dict[str, Any], _section(payload, "run"))
    real_data = cast(dict[str, Any], _section(payload, "real_data_status"))
    comparison_block = cast(dict[str, Any], _section(payload, "hrp_comparison"))
    baselines = cast(dict[str, Any], _section(payload, "baselines"))
    narrative = cast(dict[str, Any], _section(payload, "narrative"))
    limitations = cast(dict[str, Any], _section(payload, "research_limitations"))

    method_rows: list[dict[str, Any]] = list(comparison_block.get("method_rows", []))
    stress_windows: list[dict[str, Any]] = list(comparison_block.get("stress_windows", []))
    stress_keys = [str(window["key"]) for window in stress_windows]

    lines: list[str] = []
    lines.append(f"# {run['run_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Batch: {run['batch']}")
    lines.append(f"- Report date: {run['report_date']}")
    lines.append(f"- Description: {run['description']}")
    lines.append("")
    lines.append("## Real-Data Status")
    lines.append(f"- Status: {real_data['status']}")
    if real_data.get("manifest_id"):
        lines.append(f"- Snapshot manifest id: {real_data['manifest_id']}")
    if real_data.get("date_range"):
        lines.append(f"- Snapshot date range: {real_data['date_range']}")
    if real_data.get("reason"):
        lines.append(f"- Reason: {real_data['reason']}")
    lines.append("")
    lines.append("## Per-Method Metrics (B010 risk parity)")
    if method_rows:
        header = (
            "| method | annualized_return | annualized_volatility | sharpe | "
            "max_drawdown | turnover | rebalances | ending_value |"
        )
        separator = "|---|---|---|---|---|---|---|---|"
        lines.append(header)
        lines.append(separator)
        for row in method_rows:
            lines.append(
                "| {method} | {ann_return:.6f} | {ann_vol:.6f} | {sharpe:.6f} | "
                "{max_dd:.6f} | {turnover:.6f} | {count} | {ending:.2f} |".format(
                    method=row["method"],
                    ann_return=row["annualized_return"],
                    ann_vol=row["annualized_volatility"],
                    sharpe=row["sharpe"],
                    max_dd=row["max_drawdown"],
                    turnover=row["turnover"],
                    count=row["rebalance_count"],
                    ending=row["ending_value"],
                )
            )
    else:
        lines.append("- (no method rows; harness skipped)")
    lines.append("")

    lines.append("## Stress Window Verdict Per Method")
    if stress_keys and method_rows:
        header_stress = (
            "| method | "
            + " | ".join(f"{key} status / max_dd" for key in stress_keys)
            + " |"
        )
        separator_stress = "|---|" + "|".join(["---"] * len(stress_keys)) + "|"
        lines.append(header_stress)
        lines.append(separator_stress)
        for row in method_rows:
            cells = [str(row["method"])]
            for key in stress_keys:
                status = row["stress_window_status"].get(key, "n/a")
                value = row["stress_window_max_drawdowns"].get(key)
                cell = (
                    f"{status} / {value:.6f}"
                    if isinstance(value, (int, float))
                    else status
                )
                cells.append(cell)
            lines.append("| " + " | ".join(cells) + " |")
    else:
        lines.append("- (no stress windows; harness skipped)")
    lines.append("")

    lines.append("## Static 60/40 Baseline (reused from B014 sidecar when available)")
    static = baselines.get("static_60_40") or {}
    if isinstance(static, dict) and static:
        ending = static.get("ending_value")
        ann_return = static.get("CAGR")
        ann_vol = static.get("annualized_volatility")
        sharpe = static.get("Sharpe")
        max_dd = static.get("max_drawdown")
        lines.append(
            f"- ending_value={ending} | CAGR={ann_return} | "
            f"annualized_volatility={ann_vol} | Sharpe={sharpe} | "
            f"max_drawdown={max_dd}"
        )
    else:
        lines.append("- (B014 cross-strategy comparison sidecar not provided)")
    lines.append("")

    lines.append("## Narrative — Does HRP shrink the gap vs static 60/40?")
    lines.append(f"- Status: {narrative.get('status')}")
    if narrative.get("status") == NARRATIVE_REAL_DATA_RAN:
        lines.append(
            f"- inverse_volatility ending: {narrative['inverse_volatility_ending_value']:.2f}"
        )
        lines.append(f"- HRP ending: {narrative['hrp_ending_value']:.2f}")
        lines.append(
            f"- static_60_40 ending: {narrative['baseline_60_40_ending_value']:.2f}"
        )
        lines.append(
            f"- inverse_vol gap vs 60/40: {narrative['inverse_volatility_gap_vs_60_40']:.2f}"
        )
        lines.append(f"- HRP gap vs 60/40: {narrative['hrp_gap_vs_60_40']:.2f}")
        lines.append(
            f"- delta (inverse_vol_gap - hrp_gap): "
            f"{narrative['delta_inverse_minus_hrp']:.2f}"
        )
        lines.append(f"- Verdict: {narrative['verdict']}")
        lines.append(f"- Tolerance: ${narrative['tolerance_dollars']:.2f}")
    else:
        lines.append(f"- Note: {narrative.get('note')}")
    lines.append("")

    lines.append("## Research Limitations")
    for limitation in limitations.get("limitations", []):
        lines.append(f"- {limitation}")
    lines.append("")
    lines.append(f"_Disclaimer: {limitations['disclaimer']}_")
    lines.append("")
    return "\n".join(lines)


def generate_hrp_comparison_report(
    comparison: HRPComparisonResult,
    *,
    baseline_60_40: Mapping[str, object],
    output_dir: Path,
    run_id: str,
    report_date: date,
) -> HRPComparisonArtifacts:
    """Build the payload and emit ``<run_id>.md`` + ``<run_id>.json`` under ``output_dir``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40=baseline_60_40,
        run_id=run_id,
        report_date=report_date,
    )
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_hrp_comparison_markdown(payload), encoding="utf-8")
    return HRPComparisonArtifacts(
        run_id=run_id,
        json_path=json_path,
        markdown_path=markdown_path,
        payload=payload,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _section(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        return {}
    return value


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


def _period_returns(result: RiskParityBacktestResult) -> tuple[float, ...]:
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


def _annualized_return(result: RiskParityBacktestResult) -> float:
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


def _evaluate_stress_windows(
    result: RiskParityBacktestResult,
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
