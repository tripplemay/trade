"""Monthly backtest with T close signals and T+1 open execution.

Cost caliber (B111 F004 fix-round): the defaults point at the UNIFIED
forward caliber in ``trade/backtest/execution_caliber.py`` — 5bps + 5bps
per leg, charged on the gross traded notional of BOTH legs
(``cost = capital x Sigma|delta_weight| x rate``), the same turnover form
the paper engine and the master / risk-parity / hk_china backtests use.
The pre-fix legacy caliber (1bp + 2bp, one-sided buy-leg haircut) stays
reproducible for historical-artifact provenance via explicit
``BacktestParameters(cost_bps=1.0, slippage_bps=2.0)`` plus the legacy
constants in ``execution_caliber``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from trade.backtest.execution_caliber import (
    UNIFIED_COST_BPS,
    UNIFIED_SLIPPAGE_BPS,
)
from trade.data.loader import PriceBar
from trade.strategies.global_etf_momentum import (
    MomentumParameters,
    MomentumSignal,
    generate_momentum_signal,
)

MissingTPlusOneOpenPolicy = Literal[
    "flag_and_fallback_to_signal_close",
    "skip_trade",
    "fail_closed",
]


@dataclass(frozen=True, slots=True)
class BacktestParameters:
    starting_capital: float = 100_000.0
    cost_bps: float = UNIFIED_COST_BPS
    slippage_bps: float = UNIFIED_SLIPPAGE_BPS
    missing_t_plus_1_open_policy: MissingTPlusOneOpenPolicy = "flag_and_fallback_to_signal_close"


@dataclass(frozen=True, slots=True)
class EquityPoint:
    date: date
    value: float


@dataclass(frozen=True, slots=True)
class ExecutionFill:
    symbol: str
    target_weight: float
    signal_date: date
    execution_date: date
    signal_price: float
    execution_price: float
    execution_price_field: str
    execution_assumption: str
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MonthlyBacktestResult:
    starting_capital: float
    ending_value: float
    signal: MomentumSignal
    fills: tuple[ExecutionFill, ...]
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float
    missing_t_plus_1_open_policy: MissingTPlusOneOpenPolicy
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    rebalance_results: tuple[MonthlyBacktestResult, ...] = ()
    # B111 F004 fix-round — explicit cost deducted under the unified both-legs
    # turnover caliber (was implicit in the legacy one-sided haircut).
    cost_amount: float = 0.0


class BacktestError(ValueError):
    """Raised when a monthly backtest cannot be constructed."""


def run_monthly_backtest(
    records: tuple[PriceBar, ...],
    strategy_parameters: MomentumParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
    signal_date: date | None = None,
    prior_weights: dict[str, float] | None = None,
) -> MonthlyBacktestResult:
    """Run a one-rebalance monthly MVP backtest from signal date to next available close.

    ``prior_weights`` is the book carried into the rebalance (B111 F004
    fix-round): ``None`` means a from-cash deployment, so only the buy leg
    exists and cost turnover = Σ|target weight| of the executed names. When
    given, cost turnover = Σ|Δweight| over prior ∪ new book (both legs of the
    full swap), matching the paper engine's ``gross_traded x rate`` form. A
    skipped trade keeps its prior position and contributes no turnover.
    """

    if strategy_parameters is None:
        strategy_parameters = MomentumParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")
    if backtest_parameters.cost_bps < 0 or backtest_parameters.slippage_bps < 0:
        raise BacktestError("cost_bps and slippage_bps must be non-negative")

    signal = generate_momentum_signal(records, strategy_parameters, signal_date)
    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    execution_date = _next_trading_date(all_dates, signal.signal_date)
    if execution_date is None:
        raise BacktestError("no trading date exists after signal_date for T+1 open execution")
    valuation_date = _next_trading_date(all_dates, execution_date) or execution_date

    fills: list[ExecutionFill] = []
    risk_flags: list[str] = []
    ending_value = 0.0
    # Unified both-legs turnover cost (B111 F004 fix-round) replaces the
    # legacy one-sided haircut on deployed capital.
    cost_rate = (
        backtest_parameters.cost_bps + backtest_parameters.slippage_bps
    ) / 10_000.0
    executed_weights: dict[str, float] = {}
    skipped_symbols: list[str] = []
    for symbol, weight in signal.target_weights.items():
        signal_record = by_symbol_date[(symbol, signal.signal_date)]
        execution_record = by_symbol_date.get((symbol, execution_date))
        fill_flags: tuple[str, ...] = ()
        if execution_record is None:
            fill_flags = (
                f"missing_t_plus_1_open:{symbol}:{execution_date.isoformat()}",
                f"missing_t_plus_1_open_policy:{backtest_parameters.missing_t_plus_1_open_policy}",
            )
            risk_flags.extend(fill_flags)
            if backtest_parameters.missing_t_plus_1_open_policy == "fail_closed":
                raise BacktestError(
                    f"missing T+1 open for {symbol} on {execution_date.isoformat()}"
                )
            if backtest_parameters.missing_t_plus_1_open_policy == "skip_trade":
                fills.append(
                    ExecutionFill(
                        symbol=symbol,
                        target_weight=weight,
                        signal_date=signal.signal_date,
                        execution_date=execution_date,
                        signal_price=signal_record.close,
                        execution_price=0.0,
                        execution_price_field="none",
                        execution_assumption="skip_trade_due_to_missing_t_plus_1_open",
                        risk_flags=fill_flags,
                    )
                )
                continue
            skipped_symbols.append(symbol)
            if (
                backtest_parameters.missing_t_plus_1_open_policy
                != "flag_and_fallback_to_signal_close"
            ):
                raise BacktestError("unsupported missing T+1 open policy")
            execution_record = signal_record
            execution_price = signal_record.close
            execution_price_field = "close"
            execution_assumption = "fallback_to_signal_close_due_to_missing_t_plus_1_open"
        else:
            execution_price = execution_record.open
            execution_price_field = "open"
            execution_assumption = "t_plus_1_open"

        executed_weights[symbol] = weight
        valuation_record = by_symbol_date.get((symbol, valuation_date), execution_record)
        capital = backtest_parameters.starting_capital * weight
        shares = capital / execution_price
        ending_value += shares * valuation_record.close
        fills.append(
            ExecutionFill(
                symbol=symbol,
                target_weight=weight,
                signal_date=signal.signal_date,
                execution_date=execution_date,
                signal_price=signal_record.close,
                execution_price=execution_price,
                execution_price_field=execution_price_field,
                execution_assumption=execution_assumption,
                risk_flags=fill_flags,
            )
        )

    # Unified cost: gross traded notional of BOTH legs x rate. The new book is
    # the executed target weights (a skipped trade instead keeps its prior
    # position); prior names absent from the new book are sold. From cash
    # (no prior) this collapses to the single buy leg.
    prior = dict(prior_weights or {})
    effective_new_weights = dict(executed_weights)
    for skipped in skipped_symbols:
        if skipped in prior:
            effective_new_weights[skipped] = prior[skipped]
    turnover = _weight_turnover(prior, effective_new_weights)
    cost_amount = backtest_parameters.starting_capital * turnover * cost_rate
    ending_value -= cost_amount

    return MonthlyBacktestResult(
        starting_capital=backtest_parameters.starting_capital,
        ending_value=ending_value,
        signal=signal,
        fills=tuple(fills),
        risk_flags=tuple(risk_flags),
        cost_bps=backtest_parameters.cost_bps,
        slippage_bps=backtest_parameters.slippage_bps,
        missing_t_plus_1_open_policy=backtest_parameters.missing_t_plus_1_open_policy,
        equity_curve=(
            EquityPoint(signal.signal_date, backtest_parameters.starting_capital),
            EquityPoint(valuation_date, ending_value),
        ),
        turnover=turnover,
        cost_amount=cost_amount,
    )


def run_multi_monthly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    strategy_parameters: MomentumParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> MonthlyBacktestResult:
    """Run repeated monthly rebalances over explicit signal dates."""

    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if strategy_parameters is None:
        strategy_parameters = MomentumParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()

    current_capital = backtest_parameters.starting_capital
    rebalance_results: list[MonthlyBacktestResult] = []
    risk_flags: list[str] = []
    previous_weights: dict[str, float] = {}
    turnover = 0.0
    total_cost = 0.0
    for current_signal_date in signal_dates:
        period_parameters = BacktestParameters(
            starting_capital=current_capital,
            cost_bps=backtest_parameters.cost_bps,
            slippage_bps=backtest_parameters.slippage_bps,
            missing_t_plus_1_open_policy=backtest_parameters.missing_t_plus_1_open_policy,
        )
        period_result = run_monthly_backtest(
            records,
            strategy_parameters,
            period_parameters,
            signal_date=current_signal_date,
            prior_weights=previous_weights,
        )
        rebalance_results.append(period_result)
        risk_flags.extend(period_result.risk_flags)
        turnover += period_result.turnover
        total_cost += period_result.cost_amount
        previous_weights = period_result.signal.target_weights
        current_capital = period_result.ending_value

    first_result = rebalance_results[0]
    equity_curve = (EquityPoint(signal_dates[0], backtest_parameters.starting_capital),) + tuple(
        result.equity_curve[-1] for result in rebalance_results
    )
    return MonthlyBacktestResult(
        starting_capital=backtest_parameters.starting_capital,
        ending_value=current_capital,
        signal=first_result.signal,
        fills=tuple(fill for result in rebalance_results for fill in result.fills),
        risk_flags=tuple(risk_flags),
        cost_bps=backtest_parameters.cost_bps,
        slippage_bps=backtest_parameters.slippage_bps,
        missing_t_plus_1_open_policy=backtest_parameters.missing_t_plus_1_open_policy,
        equity_curve=equity_curve,
        turnover=turnover,
        rebalance_results=tuple(rebalance_results),
        cost_amount=total_cost,
    )


def _next_trading_date(all_dates: tuple[date, ...], current: date) -> date | None:
    for candidate in all_dates:
        if candidate > current:
            return candidate
    return None


def _weight_turnover(previous: dict[str, float], current: dict[str, float]) -> float:
    symbols = set(previous) | set(current)
    return sum(abs(current.get(symbol, 0.0) - previous.get(symbol, 0.0)) for symbol in symbols)
