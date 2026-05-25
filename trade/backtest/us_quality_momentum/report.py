"""B025 backtest report serialization.

Produces:

- ``reports/us_quality_momentum/<as_of>.json`` — machine-readable bundle
  (parameters, metrics, monthly + annual returns, sector exposure, ticker
  contributions, benchmarks, earnings decisions per period).
- ``reports/us_quality_momentum/<as_of>.md`` — human-readable Markdown with
  bilingual section titles and the mandatory bilingual disclaimer header
  (inherits B024 v0.9.26 pattern).

Professional terms (``Sharpe``, ``Sortino``, ``Calmar``, ``MDD``, ``bps``,
GICS sector names) are intentionally left in English even in the Chinese
column, matching B024 §4.3 convention.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trade.backtest.us_quality_momentum.benchmarks import (
    qqq_proxy_curve,
    rsp_proxy_curve,
    spy_proxy_curve,
    static_top_n_curve,
)
from trade.backtest.us_quality_momentum.engine import UsQualityBacktestResult
from trade.backtest.us_quality_momentum.metrics import (
    annual_returns,
    compute_performance_metrics,
    excess_returns_vs_benchmark,
    monthly_return_matrix,
)

DEFAULT_REPORTS_DIR = Path("reports/us_quality_momentum")
BILINGUAL_DISCLAIMER = (
    "research-only; not a trading instruction / 仅供研究使用；不构成交易指令"
)

METRIC_LABELS_BILINGUAL: dict[str, str] = {
    "annualized_return": "Annualized Return / 年化收益",
    "annualized_volatility": "Annualized Volatility / 年化波动",
    "sharpe_ratio": "Sharpe Ratio / Sharpe",
    "sortino_ratio": "Sortino Ratio / Sortino",
    "calmar_ratio": "Calmar Ratio / Calmar",
    "max_drawdown": "Max Drawdown / MDD",
    "win_rate": "Win Rate / 胜率",
    "profit_loss_ratio": "Profit/Loss Ratio / 盈亏比",
    "cumulative_return": "Cumulative Return / 累计收益",
    "total_turnover": "Total Turnover / 累计换手率",
}


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    json_path: Path
    markdown_path: Path
    payload: dict[str, object]


def _serialize_equity_curve(curve: pd.DataFrame) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for _, row in curve.iterrows():
        out.append(
            {
                "date": pd.Timestamp(row["date"]).date().isoformat(),
                "equity": round(float(row["equity"]), 4),
            }
        )
    return out


def _serialize_monthly_matrix(matrix: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    payload: dict[str, dict[str, float | None]] = {}
    if matrix.empty:
        return payload
    for year, row in matrix.iterrows():
        year_key = str(int(year))
        payload[year_key] = {
            str(int(month)): None if pd.isna(value) else round(float(value), 6)
            for month, value in row.items()
        }
    return payload


def _serialize_annual_returns(series: pd.Series) -> dict[str, float]:
    return {str(int(year)): round(float(value), 6) for year, value in series.items()}


def _per_ticker_contribution(
    result: UsQualityBacktestResult,
) -> dict[str, float]:
    """Average target weight per ticker across all rebalance periods."""

    if not result.rebalance_periods:
        return {}
    accum: dict[str, float] = {}
    for period in result.rebalance_periods:
        for ticker, weight in period.target_weights.items():
            accum[ticker] = accum.get(ticker, 0.0) + float(weight)
    n = len(result.rebalance_periods)
    return {ticker: round(total / n, 6) for ticker, total in accum.items()}


def _per_sector_contribution(
    result: UsQualityBacktestResult,
) -> dict[str, float]:
    if not result.rebalance_periods:
        return {}
    accum: dict[str, float] = {}
    for period in result.rebalance_periods:
        for sector, weight in period.sector_exposure.items():
            accum[sector] = accum.get(sector, 0.0) + float(weight)
    n = len(result.rebalance_periods)
    return {sector: round(total / n, 6) for sector, total in accum.items()}


def _benchmark_section(
    result: UsQualityBacktestResult, with_benchmarks: bool
) -> dict[str, object]:
    if not with_benchmarks or not result.rebalance_periods:
        return {}
    start = result.rebalance_periods[0].signal_date
    end = result.rebalance_periods[-1].valuation_date
    starting_capital = result.starting_capital
    curves = {
        "spy_proxy": spy_proxy_curve(start, end, starting_capital),
        "qqq_proxy": qqq_proxy_curve(start, end, starting_capital),
        "rsp_proxy": rsp_proxy_curve(start, end, starting_capital),
        "static_top_n": static_top_n_curve(
            start, end, starting_capital, parameters=result.parameters
        ),
    }
    payload: dict[str, object] = {}
    for name, curve in curves.items():
        ending = float(curve["equity"].iloc[-1]) if not curve.empty else 0.0
        cumulative = (ending / starting_capital - 1.0) if starting_capital > 0 else 0.0
        excess = excess_returns_vs_benchmark(result.equity_curve, curve)
        payload[name] = {
            "ending_value": round(ending, 4),
            "cumulative_return": round(cumulative, 6),
            "excess_return_total_bps": round(float(excess.sum()) * 10_000.0, 4),
            "excess_return_mean_daily_bps": (
                round(float(excess.mean()) * 10_000.0, 4) if not excess.empty else 0.0
            ),
        }
    return payload


def build_report_payload(
    result: UsQualityBacktestResult,
    with_benchmarks: bool = True,
) -> dict[str, object]:
    """Build the JSON-ready payload (also used by Markdown renderer)."""

    total_turnover = sum(period.turnover for period in result.rebalance_periods)
    metrics = compute_performance_metrics(
        result.equity_curve, result.daily_returns, total_turnover
    )
    monthly_matrix = monthly_return_matrix(result.equity_curve)
    annual = annual_returns(result.equity_curve)
    payload: dict[str, object] = {
        "disclaimer": BILINGUAL_DISCLAIMER,
        "strategy": {
            "id": result.parameters.strategy_id,
            "parameters_hash": result.parameters.parameter_hash(),
            "factor_weights": result.parameters.factor_weights.as_mapping(),
            "top_n": result.parameters.top_n,
            "max_position_weight": result.parameters.max_position_weight,
            "max_sector_weight": result.parameters.max_sector_weight,
            "earnings_window_days": result.parameters.earnings_window_days,
            "rebalance_frequency": result.parameters.rebalance_frequency,
        },
        "config": {
            "starting_capital": result.starting_capital,
            "cost_bps": result.config.cost_bps,
            "slippage_bps": result.config.slippage_bps,
        },
        "window": {
            "start": (
                result.rebalance_periods[0].signal_date.isoformat()
                if result.rebalance_periods
                else None
            ),
            "end": (
                result.rebalance_periods[-1].valuation_date.isoformat()
                if result.rebalance_periods
                else None
            ),
            "rebalance_count": len(result.rebalance_periods),
        },
        "metrics": metrics.as_dict(),
        "monthly_returns": _serialize_monthly_matrix(monthly_matrix),
        "annual_returns": _serialize_annual_returns(annual),
        "average_sector_exposure": _per_sector_contribution(result),
        "average_ticker_contribution": _per_ticker_contribution(result),
        "benchmarks": _benchmark_section(result, with_benchmarks),
        "data_source": "fixture:us_quality_momentum (synthetic, not actual filings)",
    }
    return payload


def render_markdown(payload: dict[str, object]) -> str:
    """Render the bilingual Markdown report from the JSON-ready payload."""

    # Payload is a heterogeneous dict[str, Any]-shaped tree built by
    # build_report_payload; cast at the boundary so the rest of this
    # function reads naturally.
    typed = cast("dict[str, Any]", payload)
    metrics: dict[str, float] = typed["metrics"]
    strategy: dict[str, Any] = typed["strategy"]
    window: dict[str, Any] = typed["window"]
    benchmarks: dict[str, dict[str, float]] = typed.get("benchmarks", {})
    avg_sector: dict[str, float] = typed["average_sector_exposure"]
    avg_tickers: dict[str, float] = typed["average_ticker_contribution"]
    annual: dict[str, float] = typed["annual_returns"]

    lines: list[str] = []
    lines.append("# US Quality Momentum Backtest / 美股质量动量回测")
    lines.append("")
    lines.append(f"> {typed['disclaimer']}")
    lines.append("")
    lines.append("## Strategy / 策略")
    lines.append(f"- strategy_id: `{strategy['id']}`")
    lines.append(f"- parameters_hash: `{strategy['parameters_hash']}`")
    lines.append(f"- factor weights / 因子权重: {strategy['factor_weights']}")
    lines.append(f"- top_n / 持仓数量: {strategy['top_n']}")
    lines.append(
        f"- max_position_weight / 单股上限: "
        f"{float(strategy['max_position_weight']):.2%}"
    )
    lines.append(
        f"- max_sector_weight / 行业上限: "
        f"{float(strategy['max_sector_weight']):.2%}"
    )
    lines.append(
        f"- earnings_window_days / 财报规避窗口: "
        f"{strategy['earnings_window_days']} 天"
    )
    lines.append("")
    lines.append("## Window / 回测窗口")
    lines.append(f"- start: {window['start']}")
    lines.append(f"- end: {window['end']}")
    lines.append(f"- rebalances / 调仓次数: {window['rebalance_count']}")
    lines.append("")
    lines.append("## Performance Metrics / 业绩指标")
    lines.append("")
    lines.append("| Metric / 指标 | Value / 数值 |")
    lines.append("|---|---|")
    percent_metrics = {
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "cumulative_return",
        "win_rate",
    }
    for metric_key, label in METRIC_LABELS_BILINGUAL.items():
        value = float(metrics[metric_key])
        if metric_key in percent_metrics:
            lines.append(f"| {label} | {value:.2%} |")
        else:
            lines.append(f"| {label} | {value:.4f} |")
    lines.append("")
    if annual:
        lines.append("## Annual Returns / 年度收益")
        lines.append("")
        lines.append("| Year / 年份 | Return / 收益 |")
        lines.append("|---|---|")
        for year, value in sorted(annual.items()):
            lines.append(f"| {year} | {float(value):.2%} |")
        lines.append("")
    if avg_sector:
        lines.append("## Average Sector Exposure / 平均行业暴露")
        lines.append("")
        lines.append("| Sector / 行业 | Weight / 权重 |")
        lines.append("|---|---|")
        for sector, weight in sorted(
            avg_sector.items(), key=lambda kv: -float(kv[1])
        ):
            lines.append(f"| {sector} | {float(weight):.2%} |")
        lines.append("")
    if avg_tickers:
        lines.append("## Average Ticker Contribution / 平均个股仓位")
        lines.append("")
        lines.append("| Ticker / 代码 | Avg Weight / 平均权重 |")
        lines.append("|---|---|")
        top_tickers = sorted(
            avg_tickers.items(), key=lambda kv: -float(kv[1])
        )[:20]
        for ticker, weight in top_tickers:
            lines.append(f"| {ticker} | {float(weight):.2%} |")
        lines.append("")
    if benchmarks:
        lines.append("## Benchmarks / 基准对比")
        lines.append("")
        lines.append(
            "| Benchmark / 基准 | Cumulative / 累计收益 | "
            "Excess (bps total) / 累计超额 |"
        )
        lines.append("|---|---|---|")
        for name, payload_b in benchmarks.items():
            lines.append(
                f"| {name} | {float(payload_b['cumulative_return']):.2%} | "
                f"{float(payload_b['excess_return_total_bps']):.1f} |"
            )
        lines.append("")
    lines.append("## Data Source / 数据来源")
    lines.append(f"- {typed['data_source']}")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    result: UsQualityBacktestResult,
    as_of: date | None = None,
    output_dir: Path | None = None,
    with_benchmarks: bool = True,
) -> ReportArtifacts:
    """Render the JSON + Markdown reports to disk and return their paths."""

    target_dir = output_dir or DEFAULT_REPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(result, with_benchmarks=with_benchmarks)
    label = (
        as_of.isoformat()
        if as_of is not None
        else (
            result.rebalance_periods[-1].signal_date.isoformat()
            if result.rebalance_periods
            else "empty"
        )
    )
    json_path = target_dir / f"{label}.json"
    md_path = target_dir / f"{label}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return ReportArtifacts(json_path=json_path, markdown_path=md_path, payload=payload)


__all__ = [
    "BILINGUAL_DISCLAIMER",
    "METRIC_LABELS_BILINGUAL",
    "ReportArtifacts",
    "build_report_payload",
    "render_markdown",
    "write_reports",
]
