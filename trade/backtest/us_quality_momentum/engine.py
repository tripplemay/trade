"""Single-sleeve backtest engine for B025 US Quality Momentum.

Pure pandas / numpy. Reads from the committed fixture via the Repository.
Monthly-cadence rebalance using ``signal.generate_signal`` followed by a
T+1-open execution model that mirrors the existing Master Portfolio
backtest. Emits a :class:`UsQualityBacktestResult` that the report module
serializes to JSON + bilingual Markdown.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from trade.data.us_quality_universe import (
    load_earnings_calendar,
    load_fundamentals,
    load_prices,
    load_universe,
)
from trade.strategies.us_quality_momentum.construction import (
    PortfolioWeights,
    _sector_map_from_universe,
    build_portfolio,
    compute_sector_exposure,
)
from trade.strategies.us_quality_momentum.factors import (
    low_vol_score,
    momentum_12_1,
    quality_score,
    trend_score,
    value_score,
)
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)

DEFAULT_STARTING_CAPITAL = 100_000.0
DEFAULT_TRADING_COST_BPS = 5.0  # one-way bid/ask + brokerage
DEFAULT_SLIPPAGE_BPS = 5.0
TRADING_DAYS_PER_YEAR = 252


class BacktestError(ValueError):
    """Raised when backtest inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Top-level controls — separate from strategy parameters."""

    starting_capital: float = DEFAULT_STARTING_CAPITAL
    cost_bps: float = DEFAULT_TRADING_COST_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def friction_rate(self) -> float:
        return (self.cost_bps + self.slippage_bps) / 10_000.0


@dataclass(frozen=True, slots=True)
class RebalancePeriod:
    """Single rebalance interval, signal_date → next signal_date (or end)."""

    signal_date: date
    execution_date: date
    valuation_date: date
    target_weights: dict[str, float]
    starting_value: float
    ending_value: float
    cost_amount: float
    turnover: float
    cash_buffer: float
    sector_exposure: dict[str, float]


@dataclass(frozen=True, slots=True)
class UsQualityBacktestResult:
    """Container for backtest outputs consumed by metrics + report."""

    parameters: UsQualityMomentumParameters
    config: BacktestConfig
    starting_capital: float
    ending_value: float
    equity_curve: pd.DataFrame  # columns: date, equity
    rebalance_periods: tuple[RebalancePeriod, ...]
    daily_returns: pd.Series
    portfolio_log: tuple[dict[str, dict[str, float]], ...] = field(
        default_factory=tuple
    )

    def signal_dates(self) -> tuple[date, ...]:
        return tuple(period.signal_date for period in self.rebalance_periods)


def monthly_signal_dates(
    trading_dates: Iterable[pd.Timestamp],
    start: date,
    end: date,
) -> list[date]:
    """Return the last trading date inside each calendar month in ``[start, end]``."""

    all_dates = pd.DatetimeIndex(sorted(set(trading_dates)))
    if all_dates.empty:
        raise BacktestError("trading_dates is empty")
    window = all_dates[
        (all_dates >= pd.Timestamp(start)) & (all_dates <= pd.Timestamp(end))
    ]
    if window.empty:
        raise BacktestError(f"no trading dates inside [{start}, {end}]")
    period_index = window.to_period("M")
    last_of_month: dict[pd.Period, pd.Timestamp] = {}
    for trading_day, period in zip(window, period_index, strict=True):
        if period not in last_of_month or trading_day > last_of_month[period]:
            last_of_month[period] = trading_day
    return [day.date() for _, day in sorted(last_of_month.items())]


def _wide_close(prices: pd.DataFrame) -> pd.DataFrame:
    return (
        prices.pivot_table(
            index="date", columns="ticker", values="adj_close", aggfunc="last"
        )
        .sort_index()
    )


def _wide_open(prices: pd.DataFrame) -> pd.DataFrame:
    return (
        prices.pivot_table(
            index="date", columns="ticker", values="open", aggfunc="last"
        )
        .sort_index()
    )


def _compute_factor_scores(
    prices: pd.DataFrame, fundamentals: pd.DataFrame, as_of: date
) -> dict[str, pd.Series]:
    return {
        "momentum": momentum_12_1(prices, as_of),
        "quality": quality_score(fundamentals, as_of),
        "low_vol": low_vol_score(prices, as_of),
        "value": value_score(fundamentals, as_of),
        "trend": trend_score(prices, as_of),
    }


def _execute_at_open(
    wide_open_: pd.DataFrame,
    execution_date: date,
    portfolio: PortfolioWeights,
    capital: float,
) -> dict[str, float]:
    """Convert weights → share counts using ``execution_date`` open prices."""

    if pd.Timestamp(execution_date) not in wide_open_.index:
        raise BacktestError(
            f"execution_date {execution_date.isoformat()} missing in price index"
        )
    opens = wide_open_.loc[pd.Timestamp(execution_date)]
    shares: dict[str, float] = {}
    for ticker, weight in portfolio.weights:
        price = opens.get(ticker)
        if price is None or pd.isna(price) or price <= 0:
            continue
        shares[ticker] = (capital * weight) / float(price)
    return shares


def _valuation_at_close(
    wide_close: pd.DataFrame,
    valuation_date: date,
    shares: dict[str, float],
) -> float:
    closes = wide_close.loc[pd.Timestamp(valuation_date)]
    return float(sum(shares.get(ticker, 0.0) * float(closes.get(ticker, 0.0)) for ticker in shares))


def _weight_turnover(prev: dict[str, float], curr: dict[str, float]) -> float:
    symbols = set(prev) | set(curr)
    return sum(abs(curr.get(symbol, 0.0) - prev.get(symbol, 0.0)) for symbol in symbols)


def _build_daily_equity_curve(
    wide_close: pd.DataFrame,
    rebalance_periods: list[RebalancePeriod],
    period_shares: list[dict[str, float]],
    starting_capital: float,
) -> pd.DataFrame:
    """True daily mark-to-market: each trading day = sum(shares × close).

    Each rebalance period contributes one row per trading day inside
    ``[execution_date, valuation_date]`` so the resulting curve has daily
    granularity — required for Sharpe / Sortino / drawdown to annualize
    correctly with the ``sqrt(252)`` factor.
    """

    if not rebalance_periods:
        return pd.DataFrame({"date": [], "equity": []})
    rows: list[dict[str, object]] = [
        {"date": pd.Timestamp(rebalance_periods[0].signal_date), "equity": starting_capital}
    ]
    for period, shares in zip(rebalance_periods, period_shares, strict=True):
        if not shares:
            rows.append(
                {
                    "date": pd.Timestamp(period.valuation_date),
                    "equity": period.ending_value,
                }
            )
            continue
        window = wide_close.loc[
            pd.Timestamp(period.execution_date) : pd.Timestamp(period.valuation_date)
        ]
        for day, closes in window.iterrows():
            equity = float(
                sum(
                    shares.get(ticker, 0.0) * float(closes.get(ticker, 0.0) or 0.0)
                    for ticker in shares
                )
            )
            rows.append({"date": day, "equity": equity})
    curve = pd.DataFrame(rows).drop_duplicates(subset="date", keep="last")
    return curve.sort_values("date").reset_index(drop=True)


def run_backtest(
    parameters: UsQualityMomentumParameters | None = None,
    config: BacktestConfig | None = None,
    start: date | None = None,
    end: date | None = None,
) -> UsQualityBacktestResult:
    """Run the monthly-rebalance single-sleeve backtest over ``[start, end]``.

    Defaults: full fixture range, parameter defaults, ``BacktestConfig()``.
    """

    if parameters is None:
        parameters = UsQualityMomentumParameters()
    if config is None:
        config = BacktestConfig()
    if config.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    universe = load_universe()
    prices = load_prices()
    fundamentals = load_fundamentals()
    earnings = load_earnings_calendar()

    wide_close = _wide_close(prices)
    wide_open = _wide_open(prices)
    trading_dates = wide_close.index

    # Default window: start once enough history exists for 12-1 momentum +
    # 252d vol (so ~ 14 months into the fixture). End at the last trading day.
    if start is None:
        start = (pd.Timestamp(prices["date"].min()) + pd.DateOffset(months=14)).date()
    if end is None:
        end = pd.Timestamp(prices["date"].max()).date()
    signal_dates = monthly_signal_dates(trading_dates, start, end)
    if len(signal_dates) < 2:
        raise BacktestError(
            "need >= 2 monthly signal dates to run a meaningful backtest"
        )

    sector_map = _sector_map_from_universe(universe)
    friction_rate = config.friction_rate()
    capital = config.starting_capital
    previous_weights: dict[str, float] = {}
    periods: list[RebalancePeriod] = []
    period_shares: list[dict[str, float]] = []

    for idx, signal_date in enumerate(signal_dates):
        execution_date = _next_trading_day(trading_dates, signal_date)
        if execution_date is None:
            break
        valuation_date = (
            signal_dates[idx + 1] if idx + 1 < len(signal_dates) else trading_dates[-1].date()
        )

        factor_scores = _compute_factor_scores(prices, fundamentals, signal_date)
        portfolio = build_portfolio(
            scores=factor_scores,
            universe=universe,
            sector_map=sector_map,
            earnings_dates=earnings,
            as_of=signal_date,
            parameters=parameters,
            current_holdings=previous_weights,
        )
        target_weights = portfolio.as_dict()
        turnover = _weight_turnover(previous_weights, target_weights)
        period_cost = capital * turnover * friction_rate
        capital_after_cost = capital - period_cost
        shares = _execute_at_open(wide_open, execution_date, portfolio, capital_after_cost)
        ending_value = _valuation_at_close(wide_close, valuation_date, shares)
        if ending_value <= 0:
            ending_value = capital_after_cost
        sector_exposure = compute_sector_exposure(target_weights, sector_map)
        periods.append(
            RebalancePeriod(
                signal_date=signal_date,
                execution_date=execution_date,
                valuation_date=valuation_date,
                target_weights=target_weights,
                starting_value=capital,
                ending_value=ending_value,
                cost_amount=period_cost,
                turnover=turnover,
                cash_buffer=portfolio.cash_buffer,
                sector_exposure=sector_exposure,
            )
        )
        period_shares.append(shares)
        previous_weights = target_weights
        capital = ending_value

    equity_curve = _build_daily_equity_curve(
        wide_close, periods, period_shares, config.starting_capital
    )
    daily_returns = equity_curve.set_index("date")["equity"].pct_change().dropna()

    return UsQualityBacktestResult(
        parameters=parameters,
        config=config,
        starting_capital=config.starting_capital,
        ending_value=capital,
        equity_curve=equity_curve,
        rebalance_periods=tuple(periods),
        daily_returns=daily_returns,
    )


def _next_trading_day(trading_dates: pd.DatetimeIndex, current: date) -> date | None:
    later = trading_dates[trading_dates > pd.Timestamp(current)]
    if later.empty:
        return None
    result: date = pd.Timestamp(later[0]).date()
    return result


__all__ = [
    "BacktestConfig",
    "BacktestError",
    "RebalancePeriod",
    "UsQualityBacktestResult",
    "monthly_signal_dates",
    "run_backtest",
]
