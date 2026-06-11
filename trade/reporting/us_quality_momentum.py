"""US Quality Momentum JSON and Markdown research reports (B050 F002).

Mirrors the risk_parity report shape so the workbench's ``map_metrics`` reads the
same ``metrics`` block (CAGR / Sharpe / max_drawdown / turnover). The engine's
result differs from the other sleeves — the equity curve is a daily
``pd.DataFrame`` and there are no per-leg fills — so metrics are computed from
the daily curve + ``daily_returns`` series here, and the workbench adapter
surfaces an empty trades list (the engine reports no fills; we do not fabricate
execution legs).
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from trade import __version__
from trade.backtest.us_quality_momentum.engine import UsQualityBacktestResult
from trade.data.loader import DataSnapshot
from trade.data.quality import evaluate_data_quality

_TRADING_DAYS_PER_YEAR = 252.0


def _iso_date(value: Any) -> str:
    """ISO ``YYYY-MM-DD`` from a date / pandas Timestamp / string."""

    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value)[:10]


def _equity_values(result: UsQualityBacktestResult) -> list[float]:
    return [float(v) for v in result.equity_curve["equity"].tolist()]


def _daily_returns(result: UsQualityBacktestResult) -> list[float]:
    """Finite daily returns (the first ``pct_change`` row is NaN)."""

    return [
        float(v)
        for v in result.daily_returns.tolist()
        if v is not None and not math.isnan(float(v))
    ]


def _cagr(result: UsQualityBacktestResult) -> float:
    if result.starting_capital <= 0:
        return 0.0
    dates = [_iso_date(d) for d in result.equity_curve["date"].tolist()]
    if len(dates) < 2:
        return 0.0
    span_days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
    years = max(span_days / 365.25, 1.0 / 365.25)
    return float((result.ending_value / result.starting_capital) ** (1.0 / years) - 1.0)


def _annualized_volatility(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((value - mean) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
    return math.sqrt(variance) * math.sqrt(_TRADING_DAYS_PER_YEAR)


def _sharpe(daily_returns: list[float], annualized_volatility: float) -> float:
    if not daily_returns or annualized_volatility == 0:
        return 0.0
    annualized_return = (sum(daily_returns) / len(daily_returns)) * _TRADING_DAYS_PER_YEAR
    return annualized_return / annualized_volatility


def _max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown


def _total_turnover(result: UsQualityBacktestResult) -> float:
    return float(sum(period.turnover for period in result.rebalance_periods))


def build_us_quality_report_payload(
    result: UsQualityBacktestResult, snapshot: DataSnapshot, run_id: str
) -> dict[str, object]:
    data_quality = evaluate_data_quality(snapshot)
    values = _equity_values(result)
    daily_returns = _daily_returns(result)
    annualized_volatility = _annualized_volatility(daily_returns)
    return {
        "run": {
            "run_id": run_id,
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "package_version": __version__,
            "environment": "local_or_ci_fixture",
            "config_reference": "us_quality_momentum_fixture_defaults",
        },
        "strategy": {
            "strategy_id": result.parameters.strategy_id,
            "strategy_version": "mvp",
            "top_n": result.parameters.top_n,
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
            "top_n": result.parameters.top_n,
            "max_position_weight": result.parameters.max_position_weight,
            "max_sector_weight": result.parameters.max_sector_weight,
            "earnings_window_days": result.parameters.earnings_window_days,
            "cost_bps": result.config.cost_bps,
            "slippage_bps": result.config.slippage_bps,
        },
        "execution": {
            "rebalance_count": len(result.rebalance_periods),
            "rebalance_trace": [
                {
                    "signal_date": _iso_date(period.signal_date),
                    "target_weights": period.target_weights,
                    "turnover": period.turnover,
                    "cost_amount": period.cost_amount,
                    "ending_value": period.ending_value,
                    "sector_exposure": period.sector_exposure,
                }
                for period in result.rebalance_periods
            ],
            "equity_curve": [
                {"date": _iso_date(d), "value": float(v)}
                for d, v in zip(
                    result.equity_curve["date"].tolist(),
                    result.equity_curve["equity"].tolist(),
                    strict=False,
                )
            ],
        },
        "metrics": {
            "CAGR": _cagr(result),
            "annualized_volatility": annualized_volatility,
            "Sharpe": _sharpe(daily_returns, annualized_volatility),
            "max_drawdown": _max_drawdown(values),
            "turnover": _total_turnover(result),
            "transaction_costs": float(
                sum(period.cost_amount for period in result.rebalance_periods)
            ),
        },
        "research_limitations": {
            "data_quality_flags": data_quality.quality_flags,
            "limitations": data_quality.research_limitations,
            "no_fills_note": (
                "The single-sleeve engine reports period valuations, not per-leg "
                "fills; the trades view is intentionally empty (no fabricated legs)."
            ),
        },
    }


def render_us_quality_markdown(report: dict[str, object]) -> str:
    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    limitations = _section(report, "research_limitations")
    return "\n".join(
        [
            f"# 美股质量动量回测报告 {run['run_id']}",
            "",
            "## 摘要",
            f"- 策略: {strategy['strategy_id']}",
            f"- 持仓数量: {strategy['top_n']}",
            f"- 年化收益率: {metrics['CAGR']}",
            f"- 年化波动率: {metrics['annualized_volatility']}",
            f"- 夏普比率: {metrics['Sharpe']}",
            f"- 最大回撤: {metrics['max_drawdown']}",
            f"- 换手率: {metrics['turnover']}",
            "",
            "## 再平衡",
            f"- 再平衡次数: {execution['rebalance_count']}",
            f"- 交易成本: {metrics['transaction_costs']}",
            "",
            "## 研究局限",
            f"- 数据质量标记: {limitations['data_quality_flags']}",
            f"- 局限: {limitations['limitations']}",
            f"- 成交: {limitations['no_fills_note']}",
        ]
    )


def _section(report: dict[str, object], key: str) -> dict[str, object]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value
