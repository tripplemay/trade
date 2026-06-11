"""Master Portfolio JSON and Markdown research reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import sqrt
from pathlib import Path

from trade import __version__
from trade.backtest.master_portfolio import (
    MasterPortfolioBacktestResult,
    MasterRebalancePeriodResult,
)
from trade.backtest.monthly import EquityPoint
from trade.data.loader import DataSnapshot, PriceBar
from trade.data.quality import evaluate_data_quality

BASELINE_LABEL = "static_60_40_etf_defensive_quarterly_rebalance"
BASELINE_WEIGHTS = {"SPY": 0.6, "AGG": 0.4}
BASELINE_FOLLOWUPS_ABSORBED = ("BL-B010-S2",)
RESEARCH_ONLY_LIMITATION = "research-only: not authorized for any paper or production order flow"


@dataclass(frozen=True, slots=True)
class MasterPortfolioReportArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    report: dict[str, object]


def generate_master_portfolio_reports(
    result: MasterPortfolioBacktestResult,
    snapshot: DataSnapshot,
    output_dir: Path,
    run_id: str = "master-portfolio-run",
) -> MasterPortfolioReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_master_portfolio_report_payload(result, snapshot, run_id)
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_master_portfolio_markdown(report), encoding="utf-8")
    return MasterPortfolioReportArtifacts(run_id, json_path, markdown_path, report)


def build_master_portfolio_report_payload(
    result: MasterPortfolioBacktestResult,
    snapshot: DataSnapshot,
    run_id: str,
) -> dict[str, object]:
    data_quality = evaluate_data_quality(snapshot)
    period_returns = _period_returns(result.equity_curve)
    realized_volatility = _annualized_volatility(tuple(period_returns.values()))
    cagr_value = _cagr(result)
    max_dd = _max_drawdown(tuple(point.value for point in result.equity_curve))
    sharpe = _sharpe(tuple(period_returns.values()), realized_volatility)
    planning_weights = {
        sleeve.sleeve_id: sleeve.planning_weight for sleeve in result.parameters.sleeves
    }
    baseline = _calculate_static_baseline(snapshot.records, result)
    research_limitations = list(data_quality.research_limitations) + [
        RESEARCH_ONLY_LIMITATION,
        "no_paper_or_live_execution_authorized",
        "fixture_or_research_snapshot_only",
    ]
    return {
        "run": {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "package_version": __version__,
            "environment": "local_or_ci_fixture",
            "config_reference": "master_portfolio_fixture_defaults",
        },
        "strategy": {
            "portfolio_id": result.parameters.portfolio_id,
            "strategy_version": "mvp",
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
            "quality_flags": list(data_quality.quality_flags),
        },
        "parameters": {
            "parameter_hash": result.parameters.parameter_hash(),
            "planning_weights": planning_weights,
            "defensive_asset": result.parameters.defensive_asset,
            "drawdown_threshold": result.parameters.drawdown_threshold,
            "max_exposure": result.parameters.max_exposure,
            "kill_switch_clearance_parameter": result.parameters.kill_switch_clearance_parameter,
            "cost_bps": result.cost_bps,
            "slippage_bps": result.slippage_bps,
        },
        "execution": {
            "rebalance_count": len(result.rebalance_results),
            "rebalance_trace": [_serialize_period(period) for period in result.rebalance_results],
            "equity_curve": [
                {"date": point.date.isoformat(), "value": point.value}
                for point in result.equity_curve
            ],
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
        },
        "account_risk": {
            "drawdown_threshold": result.parameters.drawdown_threshold,
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
        "baseline": baseline,
        "research_limitations": {
            "data_quality_flags": list(data_quality.quality_flags),
            "limitations": research_limitations,
        },
    }


def render_master_portfolio_markdown(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    account_risk = _section(report, "account_risk")
    baseline = _section(report, "baseline")
    limitations = _section(report, "research_limitations")
    return "\n".join(
        [
            f"# 旗舰组合回测报告 {run['run_id']}",
            "",
            "## 摘要",
            f"- 组合: {strategy['portfolio_id']}",
            f"- 再平衡频率: {strategy['rebalance_frequency']}",
            f"- 再平衡次数: {execution['rebalance_count']}",
            f"- 年化收益率: {metrics['CAGR']}",
            f"- 年化波动率: {metrics['annualized_volatility']}",
            f"- 夏普比率: {metrics['Sharpe']}",
            f"- 最大回撤: {metrics['max_drawdown']}",
            f"- 换手率: {metrics['turnover']}",
            f"- 交易成本: {metrics['transaction_costs']}",
            "",
            "## 账户风险控制",
            f"- 回撤阈值: {account_risk['drawdown_threshold']}",
            f"- 当前回撤: {account_risk['drawdown']}",
            f"- 历史高点: {account_risk['high_water_mark']}",
            f"- 熔断启用: {account_risk['kill_switch_active']}",
            f"- 熔断触发于: {account_risk['kill_switch_triggered_at']}",
            f"- 需人工复核: {account_risk['human_review_required']}",
            "",
            "## 基准对比",
            f"- 基准标签: {baseline['label']}",
            f"- 基准期末价值: {baseline['ending_value']}",
            f"- 已吸收的跟进: {baseline['followups_absorbed']}",
            "",
            "## 研究局限",
            f"- {limitations['limitations']}",
        ]
    )


def _serialize_period(period: MasterRebalancePeriodResult) -> dict[str, object]:
    return {
        "signal_date": period.signal_date.isoformat(),
        "execution_date": period.execution_date.isoformat(),
        "valuation_date": period.valuation_date.isoformat(),
        "starting_value": period.starting_value,
        "ending_value": period.ending_value,
        "cost_amount": period.cost_amount,
        "turnover": period.turnover,
        "effective_weights": dict(period.portfolio_target_weights),
        "weights_capped_by_kill_switch": dict(period.weights_capped_by_kill_switch),
        "sleeve_contributions": [
            {
                "sleeve_id": contribution.sleeve_id,
                "sleeve_type": contribution.sleeve_type,
                "strategy_id": contribution.strategy_id,
                "planning_weight": contribution.planning_weight,
                "child_target_weights": dict(contribution.child_target_weights),
                "contribution_weights": dict(contribution.contribution_weights),
            }
            for contribution in period.sleeve_contributions
        ],
        "pre_rebalance_account_risk_state": {
            "high_water_mark": period.pre_rebalance_account_risk_state.high_water_mark,
            "drawdown": period.pre_rebalance_account_risk_state.drawdown,
            "kill_switch_active": (
                period.pre_rebalance_account_risk_state.kill_switch_active
            ),
            "kill_switch_triggered_at": (
                period.pre_rebalance_account_risk_state.kill_switch_triggered_at.isoformat()
                if period.pre_rebalance_account_risk_state.kill_switch_triggered_at is not None
                else None
            ),
            "kill_switch_trigger_drawdown": (
                period.pre_rebalance_account_risk_state.kill_switch_trigger_drawdown
            ),
            "human_review_required": (
                period.pre_rebalance_account_risk_state.human_review_required
            ),
        },
        "risk_flags": list(period.risk_flags),
    }


def _calculate_static_baseline(
    records: tuple[PriceBar, ...], result: MasterPortfolioBacktestResult
) -> dict[str, object]:
    signal_dates = tuple(period.signal_date for period in result.rebalance_results)
    valuation_dates = tuple(period.valuation_date for period in result.rebalance_results)
    if not signal_dates:
        return {
            "label": BASELINE_LABEL,
            "weights": BASELINE_WEIGHTS,
            "followups_absorbed": list(BASELINE_FOLLOWUPS_ABSORBED),
            "ending_value": result.starting_capital,
            "equity_curve": [],
            "note": "no_signal_dates_supplied_in_master_backtest",
        }
    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    capital = result.starting_capital
    equity_points: list[EquityPoint] = [EquityPoint(signal_dates[0], capital)]
    for signal_date, valuation_date in zip(signal_dates, valuation_dates, strict=False):
        execution_date = _next_trading_date(all_dates, signal_date)
        if execution_date is None:
            break
        period_value = 0.0
        for symbol, weight in BASELINE_WEIGHTS.items():
            execution_record = by_symbol_date.get((symbol, execution_date))
            valuation_record = by_symbol_date.get((symbol, valuation_date))
            if execution_record is None or valuation_record is None:
                period_value += capital * weight
                continue
            shares = (capital * weight) / execution_record.open
            period_value += shares * valuation_record.close
        capital = period_value
        equity_points.append(EquityPoint(valuation_date, capital))
    return {
        "label": BASELINE_LABEL,
        "weights": BASELINE_WEIGHTS,
        "followups_absorbed": list(BASELINE_FOLLOWUPS_ABSORBED),
        "ending_value": capital,
        "equity_curve": [
            {"date": point.date.isoformat(), "value": point.value} for point in equity_points
        ],
        "note": "static_quarterly_rebalance_using_master_signal_dates",
    }


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


def _period_returns(equity_curve: tuple[EquityPoint, ...]) -> dict[str, float]:
    returns: dict[str, float] = {}
    for earlier, later in zip(equity_curve, equity_curve[1:], strict=False):
        if earlier.value <= 0:
            continue
        returns[later.date.strftime("%Y-%m-%d")] = later.value / earlier.value - 1.0
    return returns


def _annualized_volatility(period_returns: tuple[float, ...]) -> float:
    if len(period_returns) < 2:
        return 0.0
    mean = sum(period_returns) / len(period_returns)
    variance = sum((value - mean) ** 2 for value in period_returns) / (len(period_returns) - 1)
    return sqrt(variance) * sqrt(4.0)


def _sharpe(period_returns: tuple[float, ...], annualized_volatility: float) -> float:
    if not period_returns or annualized_volatility == 0:
        return 0.0
    annualized_return = (sum(period_returns) / len(period_returns)) * 4.0
    return annualized_return / annualized_volatility


def _cagr(result: MasterPortfolioBacktestResult) -> float:
    periods = max(len(result.equity_curve) - 1, 1)
    return float((result.ending_value / result.starting_capital) ** (4.0 / periods) - 1.0)


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
