"""Standalone HK-China Momentum quarterly backtest (B050 F003).

Before B050 the HK-China sleeve only ran *inside* the Master portfolio
(``master_portfolio`` calls ``generate_hk_china_signal`` for its 10% satellite).
B050 lets the backtest page run each strategy standalone, so this engine runs the
HK-China sleeve on its own — **reusing the exact same signal generator the Master
uses** (``generate_hk_china_signal``) so the standalone and in-Master HK-China
backtests never diverge.

Cadence mirrors the sleeve's config inside the Master: quarterly
(``HkChinaMomentumParameters.rebalance_frequency == "quarterly"``). The result is
intentionally isomorphic to ``RiskParityBacktestResult`` (T-close signal, T+1
open execution, per-period fills + equity curve) so it reuses the risk_parity
execution primitives and the workbench's risk_parity result adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.backtest.monthly import (
    BacktestError,
    BacktestParameters,
    EquityPoint,
    ExecutionFill,
)

# Reuse the risk_parity execution primitives (T+1 open fill / valuation / turnover)
# so the standalone HK-China backtest shares the exact same execution model.
from trade.backtest.risk_parity import (
    _execute_period,
    _next_trading_date,
    _weight_turnover,
)
from trade.data.loader import PriceBar
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_momentum.signal import (
    generate_signal as generate_hk_china_signal,
)


@dataclass(frozen=True, slots=True)
class HkChinaResolvedSignal:
    """The HK-China target weights resolved for one signal date.

    Holds ``signal_date`` + ``target_weights`` (the attributes the execution loop
    and the workbench risk_parity adapter read), plus provenance from the raw
    signal. ``target_weights`` is the sleeve-relative output of
    ``generate_hk_china_signal`` — or ``{defensive_asset: 1.0}`` when the records
    don't cover the chosen tickers (the same fallback the Master applies)."""

    signal_date: date
    target_weights: dict[str, float]
    parameters_hash: str
    is_defensive: bool


@dataclass(frozen=True, slots=True)
class HkChinaPeriodResult:
    signal: HkChinaResolvedSignal
    fills: tuple[ExecutionFill, ...]
    ending_value: float
    cost_amount: float
    turnover: float
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HkChinaBacktestResult:
    starting_capital: float
    ending_value: float
    parameters: HkChinaMomentumParameters
    rebalance_results: tuple[HkChinaPeriodResult, ...]
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    cost_amount: float
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float
    missing_t_plus_1_open_policy: str


def _resolve_hk_china_signal(
    records: tuple[PriceBar, ...],
    parameters: HkChinaMomentumParameters,
    signal_date: date,
    signal_prices: pd.DataFrame | None = None,
) -> HkChinaResolvedSignal:
    """Run the shared HK-China signal and resolve the executable target weights.

    Calls ``generate_hk_china_signal(parameters, signal_date)`` — the SAME entry
    the Master uses — then applies the Master's defensive fallback: when the
    records don't cover the chosen tickers on ``signal_date`` (legacy fixtures
    shipping only core ETFs), fall back to ``{defensive_asset: 1.0}`` so the
    standalone backtest stays consistent with the in-Master behaviour.

    ``signal_prices`` (B063 F003) is an optional already-PIT-safe frame injected
    into the signal so a caller can pin the signal and execution to the SAME data
    (a fair backtest comparison needs this); ``None`` keeps the default
    self-loading behaviour exactly as before (Master / B050 unaffected)."""

    raw = generate_hk_china_signal(parameters, signal_date, prices=signal_prices)
    target_weights = raw.weights_dict()
    symbols_on_signal_date = {r.symbol for r in records if r.date == signal_date}
    if not target_weights or not symbols_on_signal_date.issuperset(target_weights):
        return HkChinaResolvedSignal(
            signal_date=signal_date,
            target_weights={parameters.defensive_asset: 1.0},
            parameters_hash=raw.parameters_hash,
            is_defensive=True,
        )
    return HkChinaResolvedSignal(
        signal_date=signal_date,
        target_weights=target_weights,
        parameters_hash=raw.parameters_hash,
        is_defensive=raw.is_defensive(),
    )


def run_hk_china_quarterly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    strategy_parameters: HkChinaMomentumParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
    *,
    signal_prices: pd.DataFrame | None = None,
) -> HkChinaBacktestResult:
    """Run the standalone HK-China quarterly backtest over ``signal_dates``.

    Mirrors ``run_risk_parity_monthly_backtest``: T-close signal, T+1 open
    execution, per-period fills + cost + equity curve. The only difference is the
    signal generator (the shared HK-China one) + the defensive fallback.

    ``signal_prices`` (B063 F003) optionally pins the signal to a caller-supplied
    PIT frame instead of the default disk load — used by the comparison harness to
    keep signal + execution on the same data. ``None`` = unchanged behaviour."""

    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if strategy_parameters is None:
        strategy_parameters = HkChinaMomentumParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    current_capital = backtest_parameters.starting_capital
    previous_weights: dict[str, float] = {}
    periods: list[HkChinaPeriodResult] = []
    equity_points = [EquityPoint(signal_dates[0], backtest_parameters.starting_capital)]
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []

    for signal_date in signal_dates:
        signal = _resolve_hk_china_signal(
            records, strategy_parameters, signal_date, signal_prices
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
            # Structurally compatible: _execute_period only reads ``signal_date``
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
            HkChinaPeriodResult(
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

    return HkChinaBacktestResult(
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
