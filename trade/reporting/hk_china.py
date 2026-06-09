"""HK-China Momentum JSON and Markdown research reports (B050 F003).

Mirrors the risk_parity report shape (the standalone HK-China result is
isomorphic to ``RiskParityBacktestResult``) so the workbench's ``map_metrics``
reads the same ``metrics`` block (CAGR / Sharpe / max_drawdown / turnover).
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import sqrt

from trade import __version__
from trade.backtest.hk_china import HkChinaBacktestResult
from trade.data.loader import DataSnapshot
from trade.data.quality import evaluate_data_quality


def build_hk_china_report_payload(
    result: HkChinaBacktestResult, snapshot: DataSnapshot, run_id: str
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
            "config_reference": "hk_china_momentum_fixture_defaults",
        },
        "strategy": {
            "strategy_id": result.parameters.strategy_id,
            "strategy_version": "mvp",
            "rebalance_frequency": result.parameters.rebalance_frequency,
            "signal_timing": "T close",
            "execution_timing": "T+1 open",
            "no_leverage": True,
        },
        "data": {
            "data_snapshot_id": snapshot.data_snapshot_id,
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
            "top_n": result.parameters.top_n,
            "defensive_asset": result.parameters.defensive_asset,
            "ma_long": result.parameters.ma_long,
            "cost_bps": result.cost_bps,
            "slippage_bps": result.slippage_bps,
        },
        "execution": {
            "rebalance_count": len(result.rebalance_results),
            "rebalance_trace": [
                {
                    "signal_date": period.signal.signal_date.isoformat(),
                    "target_weights": period.signal.target_weights,
                    "is_defensive": period.signal.is_defensive,
                    "turnover": period.turnover,
                    "cost_amount": period.cost_amount,
                    "ending_value": period.ending_value,
                }
                for period in result.rebalance_results
            ],
            "equity_curve": [
                {"date": point.date.isoformat(), "value": point.value}
                for point in result.equity_curve
            ],
        },
        "metrics": {
            "CAGR": _cagr(result),
            "annualized_volatility": realized_volatility,
            "Sharpe": _sharpe(tuple(returns.values()), realized_volatility),
            "max_drawdown": _max_drawdown(
                tuple(point.value for point in result.equity_curve)
            ),
            "turnover": result.turnover,
            "transaction_costs": result.cost_amount,
            "period_returns": returns,
        },
        "research_limitations": {
            "data_quality_flags": data_quality.quality_flags,
            "limitations": data_quality.research_limitations,
        },
    }


def render_hk_china_markdown(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    limitations = _section(report, "research_limitations")
    return "\n".join(
        [
            f"# HK-China Momentum Report {run['run_id']}",
            "",
            "## Summary",
            f"- Strategy: {strategy['strategy_id']}",
            f"- Rebalance frequency: {strategy['rebalance_frequency']}",
            f"- CAGR: {metrics['CAGR']}",
            f"- Annualized volatility: {metrics['annualized_volatility']}",
            f"- Sharpe: {metrics['Sharpe']}",
            f"- Max drawdown: {metrics['max_drawdown']}",
            f"- Turnover: {metrics['turnover']}",
            "",
            "## Rebalances",
            f"- Rebalance count: {execution['rebalance_count']}",
            f"- Transaction costs: {metrics['transaction_costs']}",
            "",
            "## Research Limitations",
            f"- Data quality flags: {limitations['data_quality_flags']}",
            f"- Limitations: {limitations['limitations']}",
        ]
    )


def _section(report: dict[str, object], key: str) -> dict[str, object]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value


def _period_returns(result: HkChinaBacktestResult) -> dict[str, float]:
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
    return sqrt(variance) * sqrt(4.0)  # quarterly → annualize by sqrt(4)


def _sharpe(period_returns: tuple[float, ...], annualized_volatility: float) -> float:
    if not period_returns or annualized_volatility == 0:
        return 0.0
    annualized_return = (sum(period_returns) / len(period_returns)) * 4.0
    return annualized_return / annualized_volatility


def _cagr(result: HkChinaBacktestResult) -> float:
    if result.starting_capital <= 0:
        return 0.0
    periods = max(len(result.equity_curve) - 1, 1)
    return float((result.ending_value / result.starting_capital) ** (4.0 / periods) - 1.0)


def _max_drawdown(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown
