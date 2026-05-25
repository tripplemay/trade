"""Benchmark equity curves for the B025 backtest.

The fixture does not include separate SPY / QQQ / RSP tickers — adding real
ETF series is out of scope (spec §3 no paid data). Instead, this module
synthesizes proxy benchmarks from the same universe:

- ``SPY proxy`` / ``RSP proxy`` — equal-weight buy-and-hold across the full
  universe (a synthetic broad-market analogue).
- ``QQQ proxy`` — equal-weight buy-and-hold across the Information
  Technology + Communication Services sectors (the growth-tilted analogue).
- ``Static Top N`` — uses the first signal-date's :func:`build_portfolio`
  result, then holds those weights through the end of the window.

Each function returns a daily equity DataFrame with the same ``(date,
equity)`` shape as :data:`UsQualityBacktestResult.equity_curve`, so the
metrics module compares like-with-like.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pandas as pd

from trade.data.us_quality_universe import (
    UniverseEntry,
    load_earnings_calendar,
    load_fundamentals,
    load_prices,
    load_universe,
)
from trade.strategies.us_quality_momentum.construction import (
    _sector_map_from_universe,
    build_portfolio,
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

QQQ_PROXY_SECTORS: frozenset[str] = frozenset(
    {"Information Technology", "Communication Services"}
)


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


def _next_trading_day_after(prices_index: pd.DatetimeIndex, after: date) -> date:
    later = prices_index[prices_index > pd.Timestamp(after)]
    if later.empty:
        raise ValueError(f"no trading day after {after.isoformat()}")
    result: date = pd.Timestamp(later[0]).date()
    return result


def _buy_and_hold_curve(
    wide_close: pd.DataFrame,
    wide_open: pd.DataFrame,
    weights: Mapping[str, float],
    start: date,
    end: date,
    starting_capital: float,
) -> pd.DataFrame:
    """Buy at the first trading day after ``start``, value daily through ``end``."""

    execution_date = _next_trading_day_after(wide_close.index, start)
    opens = wide_open.loc[pd.Timestamp(execution_date)]
    shares: dict[str, float] = {}
    for ticker, weight in weights.items():
        price = opens.get(ticker)
        if price is None or pd.isna(price) or price <= 0:
            continue
        shares[ticker] = (starting_capital * float(weight)) / float(price)
    rows: list[dict[str, object]] = [
        {"date": pd.Timestamp(start), "equity": starting_capital}
    ]
    window = wide_close.loc[
        pd.Timestamp(execution_date) : pd.Timestamp(end)
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


def spy_proxy_curve(
    start: date, end: date, starting_capital: float
) -> pd.DataFrame:
    universe = load_universe()
    prices = load_prices()
    wide_close = _wide_close(prices)
    wide_open = _wide_open(prices)
    weights = {entry.ticker: 1.0 / len(universe) for entry in universe}
    return _buy_and_hold_curve(
        wide_close, wide_open, weights, start, end, starting_capital
    )


def qqq_proxy_curve(
    start: date, end: date, starting_capital: float
) -> pd.DataFrame:
    universe = load_universe()
    tech: tuple[UniverseEntry, ...] = tuple(
        entry for entry in universe if entry.gics_sector in QQQ_PROXY_SECTORS
    )
    if not tech:
        raise ValueError("no tickers in QQQ_PROXY_SECTORS — universe misconfigured")
    prices = load_prices()
    wide_close = _wide_close(prices)
    wide_open = _wide_open(prices)
    weights = {entry.ticker: 1.0 / len(tech) for entry in tech}
    return _buy_and_hold_curve(
        wide_close, wide_open, weights, start, end, starting_capital
    )


def rsp_proxy_curve(
    start: date, end: date, starting_capital: float
) -> pd.DataFrame:
    """Equal-weight S&P 500 proxy — identical to SPY proxy on this universe."""

    return spy_proxy_curve(start, end, starting_capital)


def static_top_n_curve(
    start: date,
    end: date,
    starting_capital: float,
    parameters: UsQualityMomentumParameters | None = None,
) -> pd.DataFrame:
    """Static Top N benchmark: pick weights on ``start``, then hold to ``end``."""

    if parameters is None:
        parameters = UsQualityMomentumParameters()
    universe = load_universe()
    prices = load_prices()
    fundamentals = load_fundamentals()
    earnings = load_earnings_calendar()
    sector_map = _sector_map_from_universe(universe)
    factor_scores = {
        "momentum": momentum_12_1(prices, start),
        "quality": quality_score(fundamentals, start),
        "low_vol": low_vol_score(prices, start),
        "value": value_score(fundamentals, start),
        "trend": trend_score(prices, start),
    }
    portfolio = build_portfolio(
        scores=factor_scores,
        universe=universe,
        sector_map=sector_map,
        earnings_dates=earnings,
        as_of=start,
        parameters=parameters,
    )
    weights = portfolio.as_dict()
    if not weights:
        # No eligible candidates at start → fall back to all-equal so the
        # static benchmark still produces a curve (cash-only is a degenerate
        # reference).
        weights = {entry.ticker: 1.0 / len(universe) for entry in universe}
    wide_close = _wide_close(prices)
    wide_open = _wide_open(prices)
    return _buy_and_hold_curve(
        wide_close, wide_open, weights, start, end, starting_capital
    )


__all__ = [
    "QQQ_PROXY_SECTORS",
    "qqq_proxy_curve",
    "rsp_proxy_curve",
    "spy_proxy_curve",
    "static_top_n_curve",
]
