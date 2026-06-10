"""Risk Parity JSON and Markdown research reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path

from trade import __version__
from trade.backtest.risk_parity import RiskParityBacktestResult
from trade.data.loader import DataSnapshot
from trade.data.quality import evaluate_data_quality


@dataclass(frozen=True, slots=True)
class RiskParityReportArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    report: dict[str, object]


def generate_risk_parity_reports(
    result: RiskParityBacktestResult,
    snapshot: DataSnapshot,
    output_dir: Path,
    run_id: str = "risk-parity-run",
) -> RiskParityReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_risk_parity_report_payload(result, snapshot, run_id)
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_risk_parity_markdown(report), encoding="utf-8")
    return RiskParityReportArtifacts(run_id, json_path, markdown_path, report)


def build_risk_parity_report_payload(
    result: RiskParityBacktestResult, snapshot: DataSnapshot, run_id: str
) -> dict[str, object]:
    data_quality = evaluate_data_quality(snapshot)
    returns = _period_returns(result)
    realized_volatility = _annualized_volatility(tuple(returns.values()))
    return {
        "run": {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "package_version": __version__,
            "environment": "local_or_ci_fixture",
            "config_reference": "risk_parity_fixture_defaults",
        },
        "strategy": {
            "strategy_id": result.parameters.strategy_id,
            "strategy_version": "mvp",
            "weighting_method": result.parameters.weighting_method,
            "rebalance_frequency": result.parameters.rebalance_frequency,
            "signal_timing": "T close",
            "execution_timing": "T+1 open",
            "no_leverage": result.parameters.max_exposure <= 1.0,
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
            "quality_flags": data_quality.quality_flags,
            "research_limitations": data_quality.research_limitations,
        },
        "parameters": {
            "parameter_hash": result.parameters.parameter_hash(),
            "universe": result.parameters.universe,
            "volatility_lookback": result.parameters.volatility_lookback,
            "target_volatility": result.parameters.target_volatility,
            "defensive_asset": result.parameters.defensive_asset,
            "max_asset_weight": result.parameters.max_asset_weight,
            "max_exposure": result.parameters.max_exposure,
            "cost_bps": result.cost_bps,
            "slippage_bps": result.slippage_bps,
        },
        "execution": {
            "rebalance_count": len(result.rebalance_results),
            "rebalance_trace": [
                {
                    "signal_date": period.signal.signal_date.isoformat(),
                    "target_weights": period.signal.target_weights,
                    "exposure_scale": period.signal.exposure_scale,
                    "estimated_portfolio_volatility": (
                        period.signal.estimated_portfolio_volatility
                    ),
                    "defensive_weight": period.signal.defensive_weight,
                    "turnover": period.turnover,
                    "cost_amount": period.cost_amount,
                    "ending_value": period.ending_value,
                    "weighting_method": period.signal.parameters.weighting_method,
                }
                for period in result.rebalance_results
            ],
            "equity_curve": [
                {"date": point.date.isoformat(), "value": point.value}
                for point in result.equity_curve
            ],
            "weight_history": [
                {
                    "date": period.signal.signal_date.isoformat(),
                    "weights": period.signal.target_weights,
                }
                for period in result.rebalance_results
            ],
        },
        "metrics": {
            "CAGR": _cagr(result),
            "annualized_volatility": realized_volatility,
            "target_volatility": result.parameters.target_volatility,
            "realized_vs_target_volatility": (
                realized_volatility / result.parameters.target_volatility
            ),
            "Sharpe": _sharpe(tuple(returns.values()), realized_volatility),
            "max_drawdown": _max_drawdown(tuple(point.value for point in result.equity_curve)),
            "turnover": result.turnover,
            "transaction_costs": result.cost_amount,
            "monthly_returns": returns,
            "baseline_comparison": _static_equal_weight_baseline(result),
        },
        "research_limitations": {
            "data_quality_flags": data_quality.quality_flags,
            "limitations": data_quality.research_limitations,
        },
    }


def render_risk_parity_markdown(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    limitations = _section(report, "research_limitations")
    return "\n".join(
        [
            f"# Risk Parity Report / 风险平价回测报告 {run['run_id']}",
            "",
            "## Summary / 摘要",
            f"- Strategy / 策略: {strategy['strategy_id']}",
            f"- Weighting method / 加权方法: {strategy['weighting_method']}",
            f"- CAGR: {metrics['CAGR']}",
            f"- Annualized volatility / 年化波动率: {metrics['annualized_volatility']}",
            f"- Target volatility / 目标波动率: {metrics['target_volatility']}",
            f"- Sharpe: {metrics['Sharpe']}",
            f"- Max drawdown / 最大回撤: {metrics['max_drawdown']}",
            "",
            "## Rebalances / 再平衡",
            f"- Rebalance count / 再平衡次数: {execution['rebalance_count']}",
            f"- Weight history / 权重历史: {execution['weight_history']}",
            "",
            "## Costs And Baseline / 成本与基准",
            f"- Transaction costs / 交易成本: {metrics['transaction_costs']}",
            f"- Baseline comparison / 基准对比: {metrics['baseline_comparison']}",
            "",
            "## Research Limitations / 研究局限",
            f"- Data quality flags / 数据质量标记: {limitations['data_quality_flags']}",
            f"- Limitations / 局限: {limitations['limitations']}",
        ]
    )


def _section(report: dict[str, object], key: str) -> dict[str, object]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value


def _snapshot_manifest_reference(snapshot: DataSnapshot) -> dict[str, str] | None:
    if snapshot.manifest_path is None and snapshot.manifest_snapshot_id is None:
        return None
    return {
        "path": snapshot.manifest_path or "",
        "snapshot_id": snapshot.manifest_snapshot_id or "",
    }


def _period_returns(result: RiskParityBacktestResult) -> dict[str, float]:
    returns: dict[str, float] = {}
    for earlier, later in zip(result.equity_curve, result.equity_curve[1:], strict=False):
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


def _cagr(result: RiskParityBacktestResult) -> float:
    periods = max(len(result.equity_curve) - 1, 1)
    return float((result.ending_value / result.starting_capital) ** (12.0 / periods) - 1.0)


def _max_drawdown(values: tuple[float, ...]) -> float:
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown


def _static_equal_weight_baseline(result: RiskParityBacktestResult) -> dict[str, object]:
    return {
        "label": "static_equal_weight_multi_asset_placeholder",
        "note": "Baseline is structural only in B010; no external data or live dependency added.",
        "ending_value": result.ending_value,
    }
