"""Monthly Risk Parity backtest with T close signals and T+1 open execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade.backtest.monthly import BacktestError, BacktestParameters, EquityPoint, ExecutionFill
from trade.data.loader import PriceBar
from trade.strategies.risk_parity import (
    RiskParityParameters,
    RiskParitySignal,
    generate_risk_parity_signal,
)


@dataclass(frozen=True, slots=True)
class RiskParityPeriodResult:
    signal: RiskParitySignal
    fills: tuple[ExecutionFill, ...]
    ending_value: float
    cost_amount: float
    turnover: float
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskParityBacktestResult:
    starting_capital: float
    ending_value: float
    parameters: RiskParityParameters
    rebalance_results: tuple[RiskParityPeriodResult, ...]
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    cost_amount: float
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float
    missing_t_plus_1_open_policy: str


def run_risk_parity_monthly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    strategy_parameters: RiskParityParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> RiskParityBacktestResult:
    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if strategy_parameters is None:
        strategy_parameters = RiskParityParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    current_capital = backtest_parameters.starting_capital
    previous_weights: dict[str, float] = {}
    periods: list[RiskParityPeriodResult] = []
    equity_points = [EquityPoint(signal_dates[0], backtest_parameters.starting_capital)]
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []

    for signal_date in signal_dates:
        signal = generate_risk_parity_signal(records, strategy_parameters, signal_date)
        execution_date = _next_trading_date(all_dates, signal.signal_date)
        if execution_date is None:
            raise BacktestError("no trading date exists after signal_date for T+1 open execution")
        valuation_date = _next_trading_date(all_dates, execution_date) or execution_date
        turnover = _weight_turnover(previous_weights, signal.target_weights)
        friction_rate = (backtest_parameters.cost_bps + backtest_parameters.slippage_bps) / 10_000.0
        period_cost = current_capital * turnover * friction_rate
        period_value, fills, period_flags = _execute_period(
            by_symbol_date,
            current_capital,
            signal,
            execution_date,
            valuation_date,
            backtest_parameters,
        )
        period_value -= period_cost
        total_turnover += turnover
        total_cost += period_cost
        risk_flags.extend(period_flags)
        periods.append(
            RiskParityPeriodResult(
                signal=signal,
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

    return RiskParityBacktestResult(
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


def _execute_period(
    by_symbol_date: dict[tuple[str, date], PriceBar],
    capital: float,
    signal: RiskParitySignal,
    execution_date: date,
    valuation_date: date,
    parameters: BacktestParameters,
) -> tuple[float, tuple[ExecutionFill, ...], tuple[str, ...]]:
    fills: list[ExecutionFill] = []
    risk_flags: list[str] = []
    ending_value = 0.0
    for symbol, weight in signal.target_weights.items():
        signal_record = by_symbol_date[(symbol, signal.signal_date)]
        execution_record = by_symbol_date.get((symbol, execution_date))
        fill_flags: tuple[str, ...] = ()
        if execution_record is None:
            fill_flags = (
                f"missing_t_plus_1_open:{symbol}:{execution_date.isoformat()}",
                f"missing_t_plus_1_open_policy:{parameters.missing_t_plus_1_open_policy}",
            )
            risk_flags.extend(fill_flags)
            if parameters.missing_t_plus_1_open_policy == "fail_closed":
                raise BacktestError(
                    f"missing T+1 open for {symbol} on {execution_date.isoformat()}"
                )
            if parameters.missing_t_plus_1_open_policy == "skip_trade":
                continue
            execution_record = signal_record
            execution_price = signal_record.close
            execution_price_field = "close"
            execution_assumption = "fallback_to_signal_close_due_to_missing_t_plus_1_open"
        else:
            execution_price = execution_record.open
            execution_price_field = "open"
            execution_assumption = "t_plus_1_open"
        valuation_record = by_symbol_date.get((symbol, valuation_date), execution_record)
        shares = (capital * weight) / execution_price
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
    return ending_value, tuple(fills), tuple(risk_flags)


def _next_trading_date(all_dates: tuple[date, ...], current: date) -> date | None:
    for candidate in all_dates:
        if candidate > current:
            return candidate
    return None


def _weight_turnover(previous: dict[str, float], current: dict[str, float]) -> float:
    symbols = set(previous) | set(current)
    return sum(abs(current.get(symbol, 0.0) - previous.get(symbol, 0.0)) for symbol in symbols)
