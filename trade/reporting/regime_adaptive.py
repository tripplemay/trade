"""B057 F002 — Regime-Adaptive workbench backtest report (Simplified Chinese).

The workbench backtest worker dispatches each strategy to a ``trade.reporting.X``
builder + Chinese markdown renderer (B054 localization). The regime-adaptive
strategy already has a rich *research* report in
``trade.strategies.regime_adaptive.reports`` (stress windows, 60/40 baseline) —
this module reuses that payload builder (single source for the metrics) but:

* drops the fixed historical stress windows (a workbench run spans an arbitrary
  user-selected range that rarely overlaps the doctrinal 2020/2022 windows, and
  the backtest page does not surface a stress section); and
* renders a **Simplified-Chinese** summary markdown that matches the other
  workbench strategy reports (``trade.reporting.risk_parity`` etc.).

The payload's ``metrics`` block (CAGR / Sharpe / max_drawdown / turnover) is the
shape ``workbench_api.backtests.mapping.map_metrics`` reads, so the backtest page
renders regime results exactly like the other strategies. Research-only artifact;
never authorizes an order.
"""

from __future__ import annotations

from typing import Any

from trade.data.loader import DataSnapshot
from trade.strategies.regime_adaptive.backtest import RegimeAdaptiveBacktestResult
from trade.strategies.regime_adaptive.reports import (
    build_regime_adaptive_report_payload as _build_research_payload,
)


def build_regime_adaptive_report_payload(
    result: RegimeAdaptiveBacktestResult, snapshot: DataSnapshot, run_id: str
) -> dict[str, object]:
    """Workbench regime report payload — the research payload without the fixed
    historical stress windows (an arbitrary workbench range rarely overlaps
    them). Reuses the research builder so the metrics are a single source."""

    return _build_research_payload(result, snapshot, run_id, stress_windows=())


def render_regime_adaptive_markdown(report: dict[str, object]) -> str:
    """Simplified-Chinese summary markdown (B054) for the workbench backtest page."""

    run = _section(report, "run")
    strategy = _section(report, "strategy")
    metrics = _section(report, "metrics")
    execution = _section(report, "execution")
    account_risk = _section(report, "account_risk")
    limitations = _section(report, "research_limitations")
    return "\n".join(
        [
            f"# 智能择时组合回测报告 {run['run_id']}",
            "",
            "## 摘要",
            f"- 策略: {strategy['strategy_id']}",
            f"- 调仓频率: {strategy['rebalance_frequency']}",
            f"- 再平衡次数: {execution['rebalance_count']}",
            f"- 年化收益率: {metrics['CAGR']}",
            f"- 年化波动率: {metrics['annualized_volatility']}",
            f"- 夏普比率: {metrics['Sharpe']}",
            f"- 最大回撤: {metrics['max_drawdown']}",
            f"- 换手率: {metrics['turnover']}",
            f"- 交易成本: {metrics['transaction_costs']}",
            "",
            "## 账户风控",
            f"- 回撤阈值: {account_risk['drawdown_threshold']}",
            f"- 历史高水位: {account_risk['high_water_mark']}",
            f"- 当前回撤: {account_risk['drawdown']}",
            f"- 风控开关激活: {account_risk['kill_switch_active']}",
            f"- 需人工复核: {account_risk['human_review_required']}",
            "",
            "## 研究局限",
            f"- {limitations['limitations']}",
            "",
            "> 研究态：本组合为基于市场状态自适应的研究策略，非收益预测，亦非交易指令。",
        ]
    )


def _section(report: dict[str, object], key: str) -> dict[str, Any]:
    value = report[key]
    if not isinstance(value, dict):
        raise TypeError(f"report section {key} must be a dict")
    return value
