"""Regime-Adaptive JSON / Markdown research reports.

Builds a research-only payload that summarises the regime-adaptive backtest: aggregated
equity, annualized return / volatility / Sharpe / max drawdown / turnover / transaction
costs; per-period rebalance trace including regime and gating history; tolerance-band
statistics (suppressed trades + turnover savings vs an internal no-band reference);
calculated baselines including static 60/40 (reused from B011 patterns) and placeholder
slots for B006 momentum / B010 risk parity results on overlapping windows; account-level
risk payload (kill switch, drawdown, HWM); 2020 / 2022 stress validation gates that
report pass / skip / fail without raising; and an explicit research-only disclaimer.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import sqrt
from pathlib import Path

from trade import __version__
from trade.data.loader import DataSnapshot, PriceBar
from trade.strategies.regime_adaptive.backtest import (
    RegimeAdaptiveBacktestResult,
    RegimeAdaptivePeriodResult,
)

BASELINE_LABEL_60_40 = "static_60_40_etf_defensive_quarterly_rebalance"
BASELINE_WEIGHTS_60_40 = {"SPY": 0.6, "AGG": 0.4}

STRESS_WINDOW_2020 = "2020_q1_q4"
STRESS_WINDOW_2022 = "2022_full_year"
STRESS_GATE_PASS = "pass"
STRESS_GATE_FAIL = "fail"
STRESS_GATE_SKIPPED = "skipped"
DEFAULT_STRESS_WINDOWS: tuple[tuple[date, date, str], ...] = (
    (date(2020, 2, 1), date(2020, 12, 31), STRESS_WINDOW_2020),
    (date(2022, 1, 1), date(2022, 12, 31), STRESS_WINDOW_2022),
)
STRESS_DRAWDOWN_LIMIT = -0.15

RESEARCH_ONLY_DISCLAIMER = (
    "research-only artifact; this is not a trading instruction. Regime-adaptive outputs "
    "never authorize any paper or production order flow."
)
RESEARCH_LIMITATIONS_DEFAULT: tuple[str, ...] = (
    RESEARCH_ONLY_DISCLAIMER,
    "no_paper_or_production_order_flow_authorized",
    "fixture_or_research_snapshot_only",
    "stress_gates_require_real_historical_snapshot_to_meaningfully_pass",
)


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveReportArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    report: dict[str, object]


def generate_regime_adaptive_reports(
    result: RegimeAdaptiveBacktestResult,
    snapshot: DataSnapshot,
    output_dir: Path,
    run_id: str = "regime-adaptive-run",
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    additional_baselines: dict[str, dict[str, object]] | None = None,
) -> RegimeAdaptiveReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_regime_adaptive_report_payload(
        result,
        snapshot,
        run_id,
        stress_windows=stress_windows,
        additional_baselines=additional_baselines,
    )
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_regime_adaptive_markdown(report), encoding="utf-8")
    return RegimeAdaptiveReportArtifacts(run_id, json_path, markdown_path, report)


def build_regime_adaptive_report_payload(
    result: RegimeAdaptiveBacktestResult,
    snapshot: DataSnapshot,
    run_id: str,
    *,
    stress_windows: Sequence[tuple[date, date, str]] = DEFAULT_STRESS_WINDOWS,
    additional_baselines: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    equity_curve = [
        {"date": point.date.isoformat(), "value": point.value}
        for point in result.equity_curve
    ]
    period_returns = _period_returns(result)
    realized_volatility = _annualized_volatility(tuple(period_returns.values()))
    cagr_value = _cagr(result)
    max_dd = _max_drawdown(tuple(point.value for point in result.equity_curve))
    sharpe = _sharpe(tuple(period_returns.values()), realized_volatility)
    baselines = _build_baselines(snapshot.records, result)
    if additional_baselines:
        baselines.update(additional_baselines)
    stress_validation = _evaluate_stress_windows(result, stress_windows)
    return {
        "run": {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "package_version": __version__,
            "environment": "local_or_ci_fixture",
            "config_reference": "regime_adaptive_fixture_defaults",
        },
        "strategy": {
            "strategy_id": result.config.strategy_id,
            "strategy_version": "mvp",
            "rebalance_frequency": "monthly",
            "signal_timing": "T close",
            "execution_timing": "T+1 open",
            "no_leverage": result.config.max_exposure <= 1.0,
        },
        "data": {
            "data_snapshot_id": snapshot.data_snapshot_id,
            "snapshot_manifest": _snapshot_manifest_reference(snapshot),
            "checksum": snapshot.checksum,
            "source": snapshot.source,
            "date_range": {
                "start": snapshot.start_date.isoformat(),
                "end": snapshot.end_date.isoformat(),
            },
        },
        "parameters": {
            "parameter_hash": result.config.parameter_hash(),
            "universe": [
                {"symbol": entry.symbol, "category": entry.category}
                for entry in result.config.universe
            ],
            "trend_window_days": result.config.trend_window_days,
            "vol_lookback_days": result.config.vol_lookback_days,
            "target_volatility": result.config.target_volatility,
            "regime_fast_vol_window_days": result.config.regime_fast_vol_window_days,
            "regime_slow_vol_window_days": result.config.regime_slow_vol_window_days,
            "regime_crisis_ratio": result.config.regime_crisis_ratio,
            "regime_crisis_exposure_scale": result.config.regime_crisis_exposure_scale,
            "tolerance_band": result.config.tolerance_band,
            "account_drawdown_threshold": result.config.account_drawdown_threshold,
            "max_exposure": result.config.max_exposure,
            "defensive_symbol": result.config.defensive_symbol,
            "cost_bps": result.cost_bps,
            "slippage_bps": result.slippage_bps,
        },
        "execution": {
            "rebalance_count": len(result.rebalance_results),
            "rebalance_trace": [_serialize_period(period) for period in result.rebalance_results],
            "equity_curve": equity_curve,
        },
        "portfolio": {
            "starting_capital": result.starting_capital,
            "ending_value": result.ending_value,
        },
        "metrics": {
            "CAGR": cagr_value,
            "annualized_volatility": realized_volatility,
            "Sharpe": sharpe,
            "max_drawdown": max_dd,
            "turnover": result.turnover,
            "transaction_costs": result.cost_amount,
            "period_returns": period_returns,
            "tolerance_band_statistics": _tolerance_band_statistics(result),
        },
        "account_risk": {
            "drawdown_threshold": result.config.account_drawdown_threshold,
            "high_water_mark": result.account_risk_state.high_water_mark,
            "drawdown": result.account_risk_state.drawdown,
            "kill_switch_active": result.account_risk_state.kill_switch_active,
            "kill_switch_triggered_at": (
                result.account_risk_state.kill_switch_triggered_at.isoformat()
                if result.account_risk_state.kill_switch_triggered_at is not None
                else None
            ),
            "kill_switch_trigger_drawdown": (
                result.account_risk_state.kill_switch_trigger_drawdown
            ),
            "human_review_required": result.account_risk_state.human_review_required,
            "events": [
                {
                    "event_kind": event.event_kind,
                    "signal_date": event.signal_date.isoformat(),
                    "drawdown": event.drawdown,
                    "high_water_mark": event.high_water_mark,
                }
                for event in result.kill_switch_events
            ],
        },
        "baselines": baselines,
        "stress_validation": stress_validation,
        "research_limitations": {
            "limitations": list(RESEARCH_LIMITATIONS_DEFAULT),
            "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        },
    }


def render_regime_adaptive_markdown(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    account_risk = _section(report, "account_risk")
    baselines = _section(report, "baselines")
    stress = _section(report, "stress_validation")
    limitations = _section(report, "research_limitations")
    static_60_40 = _section_or_empty(baselines, "static_60_40")
    return "\n".join(
        [
            f"# Regime-Adaptive Report {run['run_id']}",
            "",
            "## Summary",
            f"- Strategy: {strategy['strategy_id']}",
            f"- Rebalance count: {execution['rebalance_count']}",
            f"- CAGR: {metrics['CAGR']}",
            f"- Annualized volatility: {metrics['annualized_volatility']}",
            f"- Sharpe: {metrics['Sharpe']}",
            f"- Max drawdown: {metrics['max_drawdown']}",
            f"- Turnover: {metrics['turnover']}",
            f"- Transaction costs: {metrics['transaction_costs']}",
            "",
            "## Account Risk",
            f"- Drawdown threshold: {account_risk['drawdown_threshold']}",
            f"- HWM: {account_risk['high_water_mark']}",
            f"- Current drawdown: {account_risk['drawdown']}",
            f"- Kill switch active: {account_risk['kill_switch_active']}",
            f"- Human review required: {account_risk['human_review_required']}",
            "",
            "## Baseline Comparison",
            f"- Static 60/40 ending: {static_60_40.get('ending_value')}",
            f"- Momentum baseline: {baselines['global_etf_momentum']}",
            f"- Risk parity baseline: {baselines['risk_parity']}",
            "",
            "## Stress Validation",
            *_format_stress_lines(stress),
            "",
            "## Research Limitations",
            f"- {limitations['limitations']}",
        ]
    )


def _format_stress_lines(stress: dict[str, object]) -> list[str]:
    lines: list[str] = []
    for window, payload in stress.items():
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        max_drawdown = payload.get("max_drawdown")
        lines.append(f"- {window}: {status} (max_drawdown={max_drawdown})")
    return lines


def _serialize_period(period: RegimeAdaptivePeriodResult) -> dict[str, object]:
    return {
        "signal_date": period.signal_date.isoformat(),
        "execution_date": period.execution_date.isoformat(),
        "valuation_date": period.valuation_date.isoformat(),
        "starting_value": period.starting_value,
        "ending_value": period.ending_value,
        "cost_amount": period.cost_amount,
        "turnover": period.turnover,
        "target_weights": period.target_weights,
        "effective_weights": period.effective_weights,
        "suppressed_by_tolerance": list(period.suppressed_by_tolerance),
        "forced_rebalance_by_regime_transition": period.forced_rebalance_by_regime_transition,
        "regime": {
            "regime": period.regime_state.regime,
            "fast_volatility": period.regime_state.fast_volatility,
            "slow_volatility": period.regime_state.slow_volatility,
            "fast_slow_ratio": period.regime_state.fast_slow_ratio,
            "spy_trend_signal": period.regime_state.spy_trend_signal,
            "triggered_at": (
                period.regime_state.triggered_at.isoformat()
                if period.regime_state.triggered_at is not None
                else None
            ),
            "human_review_required": period.regime_state.human_review_required,
        },
        "gating": {
            "passing": list(period.gating_result.passing_symbols),
            "gated": list(period.gating_result.gated_symbols),
            "defensive_routing_symbol": period.gating_result.defensive_routing_symbol,
            "details": [
                {
                    "symbol": signal.symbol,
                    "passes": signal.passes,
                    "reason": signal.reason,
                    "observations": signal.observations,
                }
                for signal in period.gating_result.details
            ],
        },
        "kill_switch_constraint": period.weights_capped_by_kill_switch,
        "risk_flags": list(period.risk_flags),
    }


def _build_baselines(
    records: tuple[PriceBar, ...], result: RegimeAdaptiveBacktestResult
) -> dict[str, dict[str, object]]:
    static_60_40 = _compute_static_60_40_baseline(records, result)
    momentum_placeholder: dict[str, object] = {
        "status": "skipped",
        "reason": (
            "B006 Global ETF Momentum overlap is reported only when an explicit overlapping "
            "backtest result is supplied by the caller."
        ),
    }
    risk_parity_placeholder: dict[str, object] = {
        "status": "skipped",
        "reason": (
            "B010 Risk Parity overlap is reported only when an explicit overlapping "
            "backtest result is supplied by the caller."
        ),
    }
    return {
        "static_60_40": static_60_40,
        "global_etf_momentum": momentum_placeholder,
        "risk_parity": risk_parity_placeholder,
    }


def _compute_static_60_40_baseline(
    records: tuple[PriceBar, ...], result: RegimeAdaptiveBacktestResult
) -> dict[str, object]:
    signal_dates = tuple(period.signal_date for period in result.rebalance_results)
    valuation_dates = tuple(period.valuation_date for period in result.rebalance_results)
    if not signal_dates:
        return {
            "label": BASELINE_LABEL_60_40,
            "weights": dict(BASELINE_WEIGHTS_60_40),
            "ending_value": result.starting_capital,
            "equity_curve": [],
            "note": "no_signal_dates_supplied",
        }
    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    capital = result.starting_capital
    equity_points: list[dict[str, object]] = [
        {"date": signal_dates[0].isoformat(), "value": capital}
    ]
    for signal_date, valuation_date in zip(signal_dates, valuation_dates, strict=False):
        execution_date = _next_trading_date(all_dates, signal_date)
        if execution_date is None:
            break
        period_value = 0.0
        for symbol, weight in BASELINE_WEIGHTS_60_40.items():
            execution_record = by_symbol_date.get((symbol, execution_date))
            valuation_record = by_symbol_date.get((symbol, valuation_date))
            if execution_record is None or valuation_record is None:
                period_value += capital * weight
                continue
            shares = (capital * weight) / execution_record.open
            period_value += shares * valuation_record.close
        capital = period_value
        equity_points.append({"date": valuation_date.isoformat(), "value": capital})
    return {
        "label": BASELINE_LABEL_60_40,
        "weights": dict(BASELINE_WEIGHTS_60_40),
        "ending_value": capital,
        "equity_curve": equity_points,
        "note": "static_quarterly_rebalance_using_master_signal_dates",
    }


def _tolerance_band_statistics(result: RegimeAdaptiveBacktestResult) -> dict[str, object]:
    suppressed_total = sum(
        len(period.suppressed_by_tolerance) for period in result.rebalance_results
    )
    forced_full_rebalances = sum(
        1 for period in result.rebalance_results if period.forced_rebalance_by_regime_transition
    )
    return {
        "suppressed_per_period": [
            list(period.suppressed_by_tolerance) for period in result.rebalance_results
        ],
        "suppressed_total": suppressed_total,
        "forced_full_rebalances": forced_full_rebalances,
        "no_band_reference_turnover": "not_computed_in_main_run",
    }


def _evaluate_stress_windows(
    result: RegimeAdaptiveBacktestResult,
    stress_windows: Sequence[tuple[date, date, str]],
) -> dict[str, dict[str, object]]:
    outcomes: dict[str, dict[str, object]] = {}
    curve = [(point.date, point.value) for point in result.equity_curve]
    for window_start, window_end, key in stress_windows:
        window_points = [
            (point_date, value)
            for point_date, value in curve
            if window_start <= point_date <= window_end
        ]
        if not window_points:
            outcomes[key] = {
                "status": STRESS_GATE_SKIPPED,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "reason": "no_equity_points_inside_window",
            }
            continue
        peak = window_points[0][1]
        max_dd = 0.0
        for _, value in window_points:
            peak = max(peak, value)
            if peak <= 0:
                continue
            drawdown = value / peak - 1.0
            max_dd = min(max_dd, drawdown)
        status = STRESS_GATE_PASS if max_dd >= STRESS_DRAWDOWN_LIMIT else STRESS_GATE_FAIL
        outcomes[key] = {
            "status": status,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "max_drawdown": max_dd,
            "limit": STRESS_DRAWDOWN_LIMIT,
            "points_evaluated": len(window_points),
        }
    return outcomes


def _section(report: dict[str, object], key: str) -> dict[str, object]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value


def _section_or_empty(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _snapshot_manifest_reference(snapshot: DataSnapshot) -> dict[str, str] | None:
    if snapshot.manifest_path is None and snapshot.manifest_snapshot_id is None:
        return None
    return {
        "path": snapshot.manifest_path or "",
        "snapshot_id": snapshot.manifest_snapshot_id or "",
    }


def _period_returns(result: RegimeAdaptiveBacktestResult) -> dict[str, float]:
    returns: dict[str, float] = {}
    for earlier, later in zip(result.equity_curve, result.equity_curve[1:], strict=False):
        if earlier.value <= 0:
            continue
        returns[later.date.strftime("%Y-%m-%d")] = later.value / earlier.value - 1.0
    return returns


def _annualized_volatility(period_returns: tuple[float, ...]) -> float:
    if len(period_returns) < 2:
        return 0.0
    mean = sum(period_returns) / len(period_returns)
    variance = sum((value - mean) ** 2 for value in period_returns) / (len(period_returns) - 1)
    return sqrt(variance) * sqrt(12.0)


def _sharpe(period_returns: tuple[float, ...], annualized_volatility: float) -> float:
    if not period_returns or annualized_volatility == 0:
        return 0.0
    annualized_return = (sum(period_returns) / len(period_returns)) * 12.0
    return annualized_return / annualized_volatility


def _cagr(result: RegimeAdaptiveBacktestResult) -> float:
    periods = max(len(result.equity_curve) - 1, 1)
    return float((result.ending_value / result.starting_capital) ** (12.0 / periods) - 1.0)


def _max_drawdown(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown


def _next_trading_date(all_dates: tuple[date, ...], current: date) -> date | None:
    for candidate in all_dates:
        if candidate > current:
            return candidate
    return None
