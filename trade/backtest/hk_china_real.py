"""B063 F003 — standalone real-data HK-China quarterly backtest engine.

The research counterpart of :mod:`trade.backtest.hk_china` (which backtests the
*proxy* sleeve over the four US-listed ETFs). This engine runs the **real-data**
strategy (:mod:`trade.strategies.hk_china_real`) over the wide individual-stock
universe, on **USD-converted** prices, so a B063 comparison is apples-to-apples
with the USD proxy.

It is intentionally isomorphic to :class:`trade.backtest.hk_china.
HkChinaBacktestResult` (T-close signal, T+1-open execution, per-period fills +
equity curve) and **reuses the exact same execution primitives**
(``_execute_period`` / ``_next_trading_date`` / ``_weight_turnover`` from
:mod:`trade.backtest.risk_parity`) and the shared resolved-signal shape
(:class:`trade.backtest.hk_china.HkChinaResolvedSignal`). The only differences
from the proxy engine are the signal generator (the real strategy's
:func:`~trade.strategies.hk_china_real.construction.build_real_portfolio`) and
that the input frame is already USD.

Research-only: never wired into the live Master.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.backtest.hk_china import HkChinaResolvedSignal
from trade.backtest.monthly import (
    BacktestError,
    BacktestParameters,
    EquityPoint,
    ExecutionFill,
)
from trade.backtest.risk_parity import (
    _execute_period,
    _next_trading_date,
    _weight_turnover,
)
from trade.data.hk_china_real_universe import load_real_universe, usd_price_bars
from trade.strategies.hk_china_real.construction import (
    RealPortfolio,
    build_real_portfolio,
)
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters


@dataclass(frozen=True, slots=True)
class RealHkChinaPeriodResult:
    signal: HkChinaResolvedSignal
    portfolio: RealPortfolio
    fills: tuple[ExecutionFill, ...]
    ending_value: float
    cost_amount: float
    turnover: float
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RealHkChinaBacktestResult:
    starting_capital: float
    ending_value: float
    parameters: HkChinaRealParameters
    rebalance_results: tuple[RealHkChinaPeriodResult, ...]
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    cost_amount: float
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float
    missing_t_plus_1_open_policy: str


def _resolve_real_signal(
    usd_prices: pd.DataFrame,
    parameters: HkChinaRealParameters,
    signal_date: date,
    symbols_on_date: frozenset[str],
) -> tuple[HkChinaResolvedSignal, RealPortfolio]:
    """Build the real-data sleeve weights at ``signal_date`` and resolve them.

    Runs :func:`build_real_portfolio` over the point-in-time universe, then
    applies the same defensive fallback the proxy engine uses: when the USD
    records don't cover the chosen names on ``signal_date`` (so execution can't
    price them), fall back to ``{defensive_asset: 1.0}``."""

    universe = load_real_universe(as_of=signal_date)
    portfolio = build_real_portfolio(
        prices=usd_prices,
        universe_tickers=tuple(entry.ticker for entry in universe),
        as_of=signal_date,
        parameters=parameters,
    )
    target_weights = portfolio.as_dict()
    uncovered = not target_weights or not symbols_on_date.issuperset(target_weights)
    if uncovered:
        signal = HkChinaResolvedSignal(
            signal_date=signal_date,
            target_weights={parameters.defensive_asset: 1.0},
            parameters_hash=parameters.parameter_hash(),
            is_defensive=True,
        )
    else:
        signal = HkChinaResolvedSignal(
            signal_date=signal_date,
            target_weights=target_weights,
            parameters_hash=parameters.parameter_hash(),
            is_defensive=not portfolio.selected,
        )
    return signal, portfolio


def run_real_hk_china_quarterly_backtest(
    usd_prices: pd.DataFrame,
    signal_dates: tuple[date, ...],
    strategy_parameters: HkChinaRealParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> RealHkChinaBacktestResult:
    """Run the standalone real-data HK-China quarterly backtest.

    ``usd_prices`` is the long-format **USD-converted** OHLCV frame (from
    :func:`trade.data.hk_china_real_universe.to_usd_prices`) covering the
    universe + the defensive asset. Mirrors
    :func:`trade.backtest.hk_china.run_hk_china_quarterly_backtest`: T-close
    signal, T+1-open execution, per-period fills + cost + equity curve."""

    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if strategy_parameters is None:
        strategy_parameters = HkChinaRealParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    bars = usd_price_bars(usd_prices)
    by_symbol_date = {(bar.symbol, bar.date): bar for bar in bars}
    all_dates = tuple(sorted({bar.date for bar in bars}))
    # Per-date symbol coverage (drives the defensive fallback when a chosen name
    # isn't priced on the signal date).
    grouped: dict[date, set[str]] = {}
    for bar in bars:
        grouped.setdefault(bar.date, set()).add(bar.symbol)
    symbols_on_date = {day: frozenset(symbols) for day, symbols in grouped.items()}

    current_capital = backtest_parameters.starting_capital
    previous_weights: dict[str, float] = {}
    periods: list[RealHkChinaPeriodResult] = []
    equity_points = [EquityPoint(signal_dates[0], backtest_parameters.starting_capital)]
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []

    for signal_date in signal_dates:
        signal, portfolio = _resolve_real_signal(
            usd_prices,
            strategy_parameters,
            signal_date,
            symbols_on_date.get(signal_date, frozenset()),
        )
        execution_date = _next_trading_date(all_dates, signal.signal_date)
        if execution_date is None:
            raise BacktestError(
                "no trading date exists after signal_date for T+1 open execution"
            )
        valuation_date = _next_trading_date(all_dates, execution_date) or execution_date
        turnover = _weight_turnover(previous_weights, signal.target_weights)
        friction_rate = (
            backtest_parameters.cost_bps + backtest_parameters.slippage_bps
        ) / 10_000.0
        period_cost = current_capital * turnover * friction_rate
        period_value, fills, period_flags = _execute_period(
            by_symbol_date,
            current_capital,
            # Structurally compatible: _execute_period reads only ``signal_date``
            # + ``target_weights``, both present on HkChinaResolvedSignal.
            signal,  # type: ignore[arg-type]
            execution_date,
            valuation_date,
            backtest_parameters,
        )
        period_value -= period_cost
        total_turnover += turnover
        total_cost += period_cost
        risk_flags.extend(period_flags)
        periods.append(
            RealHkChinaPeriodResult(
                signal=signal,
                portfolio=portfolio,
                fills=fills,
                ending_value=period_value,
                cost_amount=period_cost,
                turnover=turnover,
                risk_flags=tuple(period_flags),
            )
        )
        equity_points.append(EquityPoint(valuation_date, period_value))
        previous_weights = signal.target_weights
        current_capital = period_value

    return RealHkChinaBacktestResult(
        starting_capital=backtest_parameters.starting_capital,
        ending_value=current_capital,
        parameters=strategy_parameters,
        rebalance_results=tuple(periods),
        equity_curve=tuple(equity_points),
        turnover=total_turnover,
        cost_amount=total_cost,
        risk_flags=tuple(risk_flags),
        cost_bps=backtest_parameters.cost_bps,
        slippage_bps=backtest_parameters.slippage_bps,
        missing_t_plus_1_open_policy=backtest_parameters.missing_t_plus_1_open_policy,
    )
