"""JSON and Markdown backtest report generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from trade import __version__
from trade.backtest.monthly import MonthlyBacktestResult
from trade.data.loader import DataSnapshot
from trade.portfolio.output import build_portfolio_output


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    report: dict[str, object]


def generate_backtest_reports(
    result: MonthlyBacktestResult,
    snapshot: DataSnapshot,
    output_dir: Path,
    run_id: str | None = None,
) -> ReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_run_id = run_id or _default_run_id(result, snapshot)
    report = build_report_payload(result, snapshot, effective_run_id)
    json_path = output_dir / f"{effective_run_id}.json"
    markdown_path = output_dir / f"{effective_run_id}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return ReportArtifacts(
        run_id=effective_run_id,
        json_path=json_path,
        markdown_path=markdown_path,
        report=report,
    )


def build_report_payload(
    result: MonthlyBacktestResult, snapshot: DataSnapshot, run_id: str
) -> dict[str, object]:
    portfolio_output = build_portfolio_output(result)
    fills = result.fills
    first_fill = fills[0]
    total_return = result.ending_value / result.starting_capital - 1.0
    risk_flags = tuple(portfolio_output.risk_flags)
    return {
        "run": {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "package_version": __version__,
            "environment": "local_or_ci_fixture",
            "config_reference": "committed_fixture_defaults",
        },
        "strategy": {
            "strategy_id": result.signal.parameters.strategy_id,
            "strategy_version": "mvp",
            "universe_id": "synthetic_global_etf_fixture",
            "rebalance_frequency": "monthly",
            "signal_timing": "T close",
            "execution_timing": "T+1 open",
            "execution_price_policy": "default T+1 open, fallback flagged if missing",
        },
        "data": {
            "data_snapshot_id": snapshot.data_snapshot_id,
            "checksum": snapshot.checksum,
            "source": snapshot.source,
            "date_range": {
                "start": snapshot.start_date.isoformat(),
                "end": snapshot.end_date.isoformat(),
            },
            "trading_calendar_gaps": snapshot.trading_calendar_gaps,
            "adjusted_price_policy": snapshot.adjusted_price_policy,
        },
        "parameters": {
            "parameter_hash": result.signal.parameter_hash,
            "momentum_windows": [
                asdict(window) for window in result.signal.parameters.momentum_windows
            ],
            "top_n": result.signal.parameters.top_n,
            "defensive_asset": result.signal.parameters.defensive_asset,
            "trend_filter": {
                "trend_window": result.signal.parameters.trend_window,
                "require_positive_trend_return": (
                    result.signal.parameters.require_positive_trend_return
                ),
            },
            "cost_bps": result.cost_bps,
            "slippage_bps": result.slippage_bps,
            "benchmark": "not_configured_for_mvp_fixture",
        },
        "execution": {
            "signal_date": result.signal.signal_date.isoformat(),
            "signal_price_field": "close",
            "execution_date": first_fill.execution_date.isoformat(),
            "execution_price_field": first_fill.execution_price_field,
            "execution_assumption": first_fill.execution_assumption,
            "fills": [
                {
                    "symbol": fill.symbol,
                    "target_weight": fill.target_weight,
                    "signal_price": fill.signal_price,
                    "execution_price": fill.execution_price,
                    "execution_price_field": fill.execution_price_field,
                    "execution_assumption": fill.execution_assumption,
                    "risk_flags": fill.risk_flags,
                }
                for fill in fills
            ],
            "slippage_model": "fixed_bps",
        },
        "portfolio": {
            "starting_capital": result.starting_capital,
            "ending_value": result.ending_value,
            "strategy_budget": portfolio_output.strategy_budget,
            "target_weights": portfolio_output.target_weights,
            "max_position_constraints": "default max_single_etf_weight=0.35",
        },
        "risk": {
            "drawdown": portfolio_output.drawdown,
            "kill_switch_state": "not_triggered_in_mvp_fixture",
            "violations": tuple(flag for flag in risk_flags if "violation" in flag),
            "warning_flags": risk_flags,
        },
        "metrics": {
            "CAGR": total_return,
            "annualized_volatility": 0.0,
            "Sharpe": 0.0,
            "max_drawdown": portfolio_output.drawdown,
            "turnover": sum(fill.target_weight for fill in fills),
            "monthly_returns": {first_fill.execution_date.strftime("%Y-%m"): total_return},
            "yearly_returns": {first_fill.execution_date.strftime("%Y"): total_return},
            "benchmark_comparison": "not_configured_for_mvp_fixture",
        },
        "outputs": {},
    }


def render_markdown_report(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    data = _section(report, "data")
    parameters = _section(report, "parameters")
    execution = _section(report, "execution")
    portfolio = _section(report, "portfolio")
    risk = _section(report, "risk")
    metrics = _section(report, "metrics")
    return "\n".join(
        [
            f"# Backtest Report {run['run_id']}",
            "",
            "## Summary",
            f"- Strategy: {strategy['strategy_id']}",
            f"- Ending value: {portfolio['ending_value']}",
            f"- CAGR: {metrics['CAGR']}",
            "",
            "## Data And Parameters",
            f"- Data snapshot: {data['data_snapshot_id']}",
            f"- Parameter hash: {parameters['parameter_hash']}",
            f"- Momentum windows: {parameters['momentum_windows']}",
            "",
            "## Signal And Execution",
            f"- Signal timing: {strategy['signal_timing']}",
            f"- Signal price field: {execution['signal_price_field']}",
            f"- Execution timing: {strategy['execution_timing']}",
            f"- Execution price field: {execution['execution_price_field']}",
            f"- Execution assumption: {execution['execution_assumption']}",
            "",
            "## Performance Metrics",
            f"- Volatility: {metrics['annualized_volatility']}",
            f"- Sharpe: {metrics['Sharpe']}",
            f"- Max drawdown: {metrics['max_drawdown']}",
            f"- Turnover: {metrics['turnover']}",
            "",
            "## Benchmark Comparison",
            f"- {metrics['benchmark_comparison']}",
            "",
            "## Risk Flags",
            f"- {risk['warning_flags']}",
            "",
            "## Reproducibility",
            f"- Snapshot checksum: {data['checksum']}",
            f"- Config reference: {run['config_reference']}",
        ]
    )


def _section(report: dict[str, object], key: str) -> dict[str, object]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value


def _default_run_id(result: MonthlyBacktestResult, snapshot: DataSnapshot) -> str:
    snapshot_suffix = snapshot.data_snapshot_id.removeprefix("fixture:")
    return f"{result.signal.parameters.strategy_id}-{snapshot_suffix}"
