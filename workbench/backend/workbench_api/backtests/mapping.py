"""B047 F002 — map the real engine's result to the API result shape.

Pure functions (no ``trade`` import at module load — the result objects are
passed in by the worker) so they unit-test without the heavy stack. The output
dicts match the F008 ``schemas.backtests`` shapes the frontend renders.
"""

from __future__ import annotations

from typing import Any


def map_metrics(report_payload: dict[str, Any]) -> dict[str, Any]:
    """``BacktestMetrics`` dict from the report payload's metrics block.

    The Master report exposes CAGR / Sharpe / max_drawdown / turnover;
    sortino + win_rate are not computed by the Master report → ``None``."""

    metrics = report_payload.get("metrics", {})
    return {
        "cagr": float(metrics.get("CAGR", 0.0)),
        "sharpe": float(metrics.get("Sharpe", 0.0)),
        "sortino": None,
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "turnover": float(metrics.get("turnover", 0.0)),
        "win_rate": None,
    }


def map_equity(result: Any) -> list[dict[str, Any]]:
    """``EquitySample`` rows from the equity curve (date + NAV)."""

    return [
        {"date": point.date.isoformat(), "nav": float(point.value)}
        for point in result.equity_curve
    ]


def map_allocations(result: Any) -> list[dict[str, Any]]:
    """``AllocationBar`` rows: the post-rebalance portfolio target weights per
    signal date."""

    return [
        {
            "date": period.signal_date.isoformat(),
            "weights": {
                symbol: float(weight)
                for symbol, weight in period.portfolio_target_weights.items()
            },
        }
        for period in result.rebalance_results
    ]


def map_trades(result: Any) -> list[dict[str, Any]]:
    """``BacktestTrade`` rows from the per-period execution fills.

    The Master fills carry a target_weight + execution price (a rebalance to
    target), not a signed quantity. We surface them as the executed rebalance
    legs: notional = target_weight × the period's starting value, quantity =
    notional / execution_price, side = 'buy' (rebalance into the target).
    Skips legs with no executable price (missing T+1 open)."""

    trades: list[dict[str, Any]] = []
    for period in result.rebalance_results:
        starting_value = float(period.starting_value)
        for fill in period.fills:
            price = float(fill.execution_price)
            if price <= 0:
                continue
            notional = float(fill.target_weight) * starting_value
            trades.append(
                {
                    "date": fill.execution_date.isoformat(),
                    "symbol": fill.symbol,
                    "side": "buy",
                    "quantity": round(notional / price, 6),
                    "price": price,
                    "notional": round(notional, 2),
                }
            )
    return trades
