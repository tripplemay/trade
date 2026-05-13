"""JSON and Markdown backtest report generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path

from trade import __version__
from trade.backtest.monthly import MonthlyBacktestResult
from trade.data.loader import DataSnapshot
from trade.data.quality import evaluate_data_quality
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
    rebalances = result.rebalance_results or (result,)
    monthly_returns = _period_returns(result)
    yearly_returns = _yearly_returns(monthly_returns)
    volatility = _annualized_volatility(tuple(monthly_returns.values()))
    risk_flags = tuple(portfolio_output.risk_flags)
    data_quality = evaluate_data_quality(snapshot)
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
            "quality_flags": data_quality.quality_flags,
            "research_limitations": data_quality.research_limitations,
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
            "missing_t_plus_1_open_policy": result.missing_t_plus_1_open_policy,
            "missing_t_plus_1_open_flags": tuple(
                flag for flag in result.risk_flags if flag.startswith("missing_t_plus_1_open")
            ),
            "rebalance_count": len(rebalances),
            "rebalance_trace": [
                {
                    "signal_date": rebalance.signal.signal_date.isoformat(),
                    "execution_date": rebalance.fills[0].execution_date.isoformat(),
                    "ending_value": rebalance.ending_value,
                    "target_weights": rebalance.signal.target_weights,
                    "risk_flags": rebalance.risk_flags,
                }
                for rebalance in rebalances
            ],
            "equity_curve": [
                {"date": point.date.isoformat(), "value": point.value}
                for point in result.equity_curve
            ],
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
            "violations": portfolio_output.warning_flags,
            "warning_flags": portfolio_output.warning_flags,
            "expected_warning_flags": portfolio_output.expected_warning_flags,
            "unexpected_warning_flags": portfolio_output.unexpected_warning_flags,
            "risk_flags": risk_flags,
        },
        "metrics": {
            "CAGR": _cagr(result),
            "annualized_volatility": volatility,
            "Sharpe": _sharpe(tuple(monthly_returns.values()), volatility),
            "max_drawdown": portfolio_output.drawdown,
            "turnover": result.turnover,
            "monthly_returns": monthly_returns,
            "yearly_returns": yearly_returns,
            "equity_curve": [
                {"date": point.date.isoformat(), "value": point.value}
                for point in result.equity_curve
            ],
            "benchmark_comparison": "not_configured_for_mvp_fixture",
        },
        "research_limitations": {
            "data_quality_flags": data_quality.quality_flags,
            "limitations": data_quality.research_limitations,
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
    limitations = _section(report, "research_limitations")
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
            f"- Missing T+1 open policy: {execution['missing_t_plus_1_open_policy']}",
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
            "## Research Limitations",
            f"- Data quality flags: {limitations['data_quality_flags']}",
            f"- Limitations: {limitations['limitations']}",
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


def _period_returns(result: MonthlyBacktestResult) -> dict[str, float]:
    returns: dict[str, float] = {}
    for earlier, later in zip(result.equity_curve, result.equity_curve[1:], strict=False):
        returns[later.date.strftime("%Y-%m")] = later.value / earlier.value - 1.0
    return returns


def _yearly_returns(monthly_returns: dict[str, float]) -> dict[str, float]:
    yearly: dict[str, float] = {}
    for month, value in monthly_returns.items():
        year = month[:4]
        yearly[year] = (1.0 + yearly.get(year, 0.0)) * (1.0 + value) - 1.0
    return yearly


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


def _cagr(result: MonthlyBacktestResult) -> float:
    periods = max(len(result.equity_curve) - 1, 1)
    return float((result.ending_value / result.starting_capital) ** (12.0 / periods) - 1.0)
