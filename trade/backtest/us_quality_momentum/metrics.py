"""Backtest performance metrics for the B025 strategy.

All computations are deterministic given a fixed input. Annualization uses
252 trading days; risk-free rate is assumed zero (the strategy is
research-only, so absolute Sharpe vs T-bills is not the primary lens).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """All of the spec §F004 metric outputs in one bundle."""

    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_loss_ratio: float
    cumulative_return: float
    total_turnover: float

    def as_dict(self) -> dict[str, float]:
        return {
            "annualized_return": self.annualized_return,
            "annualized_volatility": self.annualized_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_loss_ratio": self.profit_loss_ratio,
            "cumulative_return": self.cumulative_return,
            "total_turnover": self.total_turnover,
        }


def annualized_return(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0
    start_value = float(equity_curve["equity"].iloc[0])
    end_value = float(equity_curve["equity"].iloc[-1])
    if start_value <= 0 or end_value <= 0:
        return 0.0
    span_days = (equity_curve["date"].iloc[-1] - equity_curve["date"].iloc[0]).days
    years = max(span_days / 365.25, 1e-9)
    return float((end_value / start_value) ** (1.0 / years) - 1.0)


def annualized_volatility(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    return float(daily_returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


_VOL_FLOOR = 1e-12  # treat sub-FP-noise volatility as effectively zero


def sharpe_ratio(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    vol = float(daily_returns.std(ddof=1))
    if vol <= _VOL_FLOOR:
        return 0.0
    mean = float(daily_returns.mean())
    return float(mean / vol * np.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    downside = daily_returns[daily_returns < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    if downside_std <= _VOL_FLOOR:
        return 0.0
    mean = float(daily_returns.mean())
    return float(mean / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR))


def calmar_ratio(equity_curve: pd.DataFrame) -> float:
    ann_ret = annualized_return(equity_curve)
    mdd = abs(max_drawdown(equity_curve))
    if mdd == 0:
        return 0.0
    return ann_ret / mdd


def max_drawdown(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    series = equity_curve["equity"].astype(float)
    cummax = series.cummax()
    drawdowns = (series - cummax) / cummax
    return float(drawdowns.min())


def win_rate(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    return float((daily_returns > 0).mean())


def profit_loss_ratio(daily_returns: pd.Series) -> float:
    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]
    if losses.empty or wins.empty:
        return 0.0
    avg_win = float(wins.mean())
    avg_loss = float(abs(losses.mean()))
    if avg_loss == 0:
        return 0.0
    return avg_win / avg_loss


def cumulative_return(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    start = float(equity_curve["equity"].iloc[0])
    if start <= 0:
        return 0.0
    end = float(equity_curve["equity"].iloc[-1])
    return end / start - 1.0


def monthly_return_matrix(equity_curve: pd.DataFrame) -> pd.DataFrame:
    """Pivot: rows = year, columns = month (1–12), values = period return."""

    if equity_curve.empty:
        return pd.DataFrame()
    ec = equity_curve.copy()
    ec["date"] = pd.to_datetime(ec["date"])
    ec = ec.set_index("date")["equity"]
    monthly = ec.resample("ME").last().pct_change().dropna()
    if monthly.empty:
        return pd.DataFrame()
    frame = monthly.to_frame("return")
    frame["year"] = frame.index.year
    frame["month"] = frame.index.month
    return frame.pivot_table(
        index="year", columns="month", values="return", aggfunc="last"
    ).sort_index()


def annual_returns(equity_curve: pd.DataFrame) -> pd.Series:
    if equity_curve.empty:
        return pd.Series(dtype=float)
    ec = equity_curve.copy()
    ec["date"] = pd.to_datetime(ec["date"])
    ec = ec.set_index("date")["equity"]
    yearly = ec.resample("YE").last().pct_change().dropna()
    yearly.index = yearly.index.year
    return yearly


def excess_returns_vs_benchmark(
    equity_curve: pd.DataFrame, benchmark_curve: pd.DataFrame
) -> pd.Series:
    """Aligned daily strategy return − benchmark return."""

    if equity_curve.empty or benchmark_curve.empty:
        return pd.Series(dtype=float)
    strat = equity_curve.set_index("date")["equity"].pct_change().dropna()
    bench = benchmark_curve.set_index("date")["equity"].pct_change().dropna()
    aligned = pd.concat([strat, bench], axis=1, join="inner")
    aligned.columns = pd.Index(["strategy", "benchmark"])
    return (aligned["strategy"] - aligned["benchmark"]).rename("excess")


def compute_performance_metrics(
    equity_curve: pd.DataFrame, daily_returns: pd.Series, total_turnover: float
) -> PerformanceMetrics:
    return PerformanceMetrics(
        annualized_return=annualized_return(equity_curve),
        annualized_volatility=annualized_volatility(daily_returns),
        sharpe_ratio=sharpe_ratio(daily_returns),
        sortino_ratio=sortino_ratio(daily_returns),
        calmar_ratio=calmar_ratio(equity_curve),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate(daily_returns),
        profit_loss_ratio=profit_loss_ratio(daily_returns),
        cumulative_return=cumulative_return(equity_curve),
        total_turnover=total_turnover,
    )


__all__ = [
    "PerformanceMetrics",
    "annual_returns",
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "compute_performance_metrics",
    "cumulative_return",
    "excess_returns_vs_benchmark",
    "max_drawdown",
    "monthly_return_matrix",
    "profit_loss_ratio",
    "sharpe_ratio",
    "sortino_ratio",
    "win_rate",
]
