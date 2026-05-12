"""Portfolio Manager-compatible strategy output DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from trade.backtest.monthly import MonthlyBacktestResult
from trade.risk.checks import RiskCheckResult, evaluate_risk


@dataclass(frozen=True, slots=True)
class PortfolioTargetOutput:
    strategy_id: str
    strategy_budget: float
    target_weights: dict[str, float]
    drawdown: float
    risk_flags: tuple[str, ...]
    warning_flags: tuple[str, ...]
    expected_warning_flags: tuple[str, ...]
    unexpected_warning_flags: tuple[str, ...]
    defensive_switch: bool


def build_portfolio_output(
    result: MonthlyBacktestResult,
    strategy_budget: float = 0.4,
    max_single_etf_weight: float = 0.35,
    expected_warning_prefixes: tuple[str, ...] = (),
) -> PortfolioTargetOutput:
    """Create PM-compatible output without performing real PM rebalancing or OMS work."""

    risk = evaluate_result_risk(result, max_single_etf_weight, expected_warning_prefixes)
    return PortfolioTargetOutput(
        strategy_id=result.signal.parameters.strategy_id,
        strategy_budget=strategy_budget,
        target_weights=result.signal.target_weights,
        drawdown=risk.drawdown.max_drawdown,
        risk_flags=risk.risk_flags,
        warning_flags=risk.warning_flags,
        expected_warning_flags=risk.expected_warning_flags,
        unexpected_warning_flags=risk.unexpected_warning_flags,
        defensive_switch=risk.defensive_switch,
    )


def evaluate_result_risk(
    result: MonthlyBacktestResult,
    max_single_etf_weight: float = 0.35,
    expected_warning_prefixes: tuple[str, ...] = (),
) -> RiskCheckResult:
    return evaluate_risk(
        target_weights=result.signal.target_weights,
        equity_curve=tuple(point.value for point in result.equity_curve),
        defensive_asset=result.signal.defensive_asset,
        max_single_etf_weight=max_single_etf_weight,
        existing_flags=result.risk_flags,
        expected_warning_prefixes=expected_warning_prefixes,
    )
