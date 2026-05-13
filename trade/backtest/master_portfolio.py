"""Master Portfolio quarterly rebalance backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade.backtest.monthly import (
    BacktestError,
    BacktestParameters,
    EquityPoint,
    ExecutionFill,
)
from trade.data.loader import PriceBar
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    SLEEVE_TYPE_SATELLITE_STUB,
    MasterPortfolioParameters,
    MasterSleeveConfig,
    default_master_portfolio_parameters,
    validate_master_portfolio_parameters,
)
from trade.strategies.global_etf_momentum import (
    MomentumParameters,
    generate_momentum_signal,
)
from trade.strategies.risk_parity import (
    RiskParityParameters,
    generate_risk_parity_signal,
)

WEIGHT_ROUND_DIGITS = 12


@dataclass(frozen=True, slots=True)
class MasterChildStrategyParameters:
    """Optional per-child overrides; None falls back to the child's own defaults."""

    momentum: MomentumParameters | None = None
    risk_parity: RiskParityParameters | None = None


@dataclass(frozen=True, slots=True)
class MasterSleeveContribution:
    sleeve_id: str
    sleeve_type: str
    strategy_id: str | None
    planning_weight: float
    child_target_weights: dict[str, float]
    contribution_weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class MasterRebalancePeriodResult:
    signal_date: date
    execution_date: date
    valuation_date: date
    portfolio_target_weights: dict[str, float]
    sleeve_contributions: tuple[MasterSleeveContribution, ...]
    fills: tuple[ExecutionFill, ...]
    starting_value: float
    ending_value: float
    cost_amount: float
    turnover: float
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MasterPortfolioBacktestResult:
    starting_capital: float
    ending_value: float
    parameters: MasterPortfolioParameters
    rebalance_results: tuple[MasterRebalancePeriodResult, ...]
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    cost_amount: float
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float


def run_master_portfolio_quarterly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    master_parameters: MasterPortfolioParameters | None = None,
    child_parameters: MasterChildStrategyParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> MasterPortfolioBacktestResult:
    """Run a quarterly Master Portfolio backtest.

    At each supplied signal date (treated as a calendar quarter end in the fixture), the Master
    consumes each implemented child's then-current target weights, routes satellite stub
    planning weights to the defensive asset, aggregates per-asset portfolio weights, and
    executes at T+1 open. Capital chains across periods with cost/slippage friction applied to
    weight turnover.
    """

    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if master_parameters is None:
        master_parameters = default_master_portfolio_parameters()
    else:
        validate_master_portfolio_parameters(master_parameters)
    if child_parameters is None:
        child_parameters = MasterChildStrategyParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    momentum_params = child_parameters.momentum or MomentumParameters()
    risk_parity_params = child_parameters.risk_parity or RiskParityParameters()

    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))

    current_capital = backtest_parameters.starting_capital
    previous_portfolio_weights: dict[str, float] = {}
    periods: list[MasterRebalancePeriodResult] = []
    equity_points: list[EquityPoint] = [EquityPoint(signal_dates[0], current_capital)]
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []
    friction_rate = (
        backtest_parameters.cost_bps + backtest_parameters.slippage_bps
    ) / 10_000.0

    for signal_date in signal_dates:
        execution_date = _next_trading_date(all_dates, signal_date)
        if execution_date is None:
            raise BacktestError(
                "no trading date exists after signal_date for T+1 open execution"
            )
        valuation_date = _next_trading_date(all_dates, execution_date) or execution_date

        sleeve_contributions, portfolio_target = _build_portfolio_target(
            sleeves=master_parameters.sleeves,
            defensive_asset=master_parameters.defensive_asset,
            records=records,
            signal_date=signal_date,
            momentum_params=momentum_params,
            risk_parity_params=risk_parity_params,
        )

        turnover = _weight_turnover(previous_portfolio_weights, portfolio_target)
        period_cost = current_capital * turnover * friction_rate

        fills, ending_value, period_flags = _execute_master_period(
            by_symbol_date=by_symbol_date,
            capital=current_capital,
            signal_date=signal_date,
            execution_date=execution_date,
            valuation_date=valuation_date,
            portfolio_target=portfolio_target,
        )
        ending_value -= period_cost

        periods.append(
            MasterRebalancePeriodResult(
                signal_date=signal_date,
                execution_date=execution_date,
                valuation_date=valuation_date,
                portfolio_target_weights=portfolio_target,
                sleeve_contributions=sleeve_contributions,
                fills=fills,
                starting_value=current_capital,
                ending_value=ending_value,
                cost_amount=period_cost,
                turnover=turnover,
                risk_flags=tuple(period_flags),
            )
        )
        equity_points.append(EquityPoint(valuation_date, ending_value))
        total_turnover += turnover
        total_cost += period_cost
        risk_flags.extend(period_flags)
        previous_portfolio_weights = portfolio_target
        current_capital = ending_value

    return MasterPortfolioBacktestResult(
        starting_capital=backtest_parameters.starting_capital,
        ending_value=current_capital,
        parameters=master_parameters,
        rebalance_results=tuple(periods),
        equity_curve=tuple(equity_points),
        turnover=total_turnover,
        cost_amount=total_cost,
        risk_flags=tuple(risk_flags),
        cost_bps=backtest_parameters.cost_bps,
        slippage_bps=backtest_parameters.slippage_bps,
    )


def _build_portfolio_target(
    *,
    sleeves: tuple[MasterSleeveConfig, ...],
    defensive_asset: str,
    records: tuple[PriceBar, ...],
    signal_date: date,
    momentum_params: MomentumParameters,
    risk_parity_params: RiskParityParameters,
) -> tuple[tuple[MasterSleeveContribution, ...], dict[str, float]]:
    contributions: list[MasterSleeveContribution] = []
    portfolio_target: dict[str, float] = {}
    for sleeve in sleeves:
        child_weights = _resolve_child_weights(
            sleeve,
            records=records,
            signal_date=signal_date,
            defensive_asset=defensive_asset,
            momentum_params=momentum_params,
            risk_parity_params=risk_parity_params,
        )
        contribution_weights = {
            symbol: round(sleeve.planning_weight * weight, WEIGHT_ROUND_DIGITS)
            for symbol, weight in child_weights.items()
        }
        contributions.append(
            MasterSleeveContribution(
                sleeve_id=sleeve.sleeve_id,
                sleeve_type=sleeve.sleeve_type,
                strategy_id=sleeve.strategy_id,
                planning_weight=sleeve.planning_weight,
                child_target_weights=dict(child_weights),
                contribution_weights=contribution_weights,
            )
        )
        for symbol, weight in contribution_weights.items():
            portfolio_target[symbol] = round(
                portfolio_target.get(symbol, 0.0) + weight, WEIGHT_ROUND_DIGITS
            )
    return tuple(contributions), portfolio_target


def _resolve_child_weights(
    sleeve: MasterSleeveConfig,
    *,
    records: tuple[PriceBar, ...],
    signal_date: date,
    defensive_asset: str,
    momentum_params: MomentumParameters,
    risk_parity_params: RiskParityParameters,
) -> dict[str, float]:
    if sleeve.sleeve_type == SLEEVE_TYPE_SATELLITE_STUB:
        return {defensive_asset: 1.0}
    if sleeve.sleeve_type != SLEEVE_TYPE_IMPLEMENTED:
        raise BacktestError(f"unsupported sleeve_type for backtest: {sleeve.sleeve_type}")
    if sleeve.strategy_id == "global_etf_momentum":
        momentum_signal = generate_momentum_signal(records, momentum_params, signal_date)
        return dict(momentum_signal.target_weights)
    if sleeve.strategy_id == "risk_parity_vol_target":
        risk_parity_signal = generate_risk_parity_signal(
            records, risk_parity_params, signal_date
        )
        return dict(risk_parity_signal.target_weights)
    raise BacktestError(
        f"no child signal generator registered for strategy_id: {sleeve.strategy_id}"
    )


def _execute_master_period(
    *,
    by_symbol_date: dict[tuple[str, date], PriceBar],
    capital: float,
    signal_date: date,
    execution_date: date,
    valuation_date: date,
    portfolio_target: dict[str, float],
) -> tuple[tuple[ExecutionFill, ...], float, tuple[str, ...]]:
    fills: list[ExecutionFill] = []
    risk_flags: list[str] = []
    ending_value = 0.0
    for symbol, weight in portfolio_target.items():
        if weight <= 0:
            continue
        signal_record = by_symbol_date.get((symbol, signal_date))
        if signal_record is None:
            flag = f"missing_signal_price:{symbol}:{signal_date.isoformat()}"
            risk_flags.append(flag)
            continue
        execution_record = by_symbol_date.get((symbol, execution_date))
        if execution_record is None:
            flag = f"missing_t_plus_1_open:{symbol}:{execution_date.isoformat()}"
            risk_flags.append(flag)
            execution_price = signal_record.close
            execution_price_field = "close"
            execution_assumption = "fallback_to_signal_close_due_to_missing_t_plus_1_open"
            valuation_record = by_symbol_date.get((symbol, valuation_date), signal_record)
            fill_flags: tuple[str, ...] = (flag,)
        else:
            execution_price = execution_record.open
            execution_price_field = "open"
            execution_assumption = "t_plus_1_open"
            valuation_record = by_symbol_date.get((symbol, valuation_date), execution_record)
            fill_flags = ()

        shares = (capital * weight) / execution_price
        ending_value += shares * valuation_record.close
        fills.append(
            ExecutionFill(
                symbol=symbol,
                target_weight=weight,
                signal_date=signal_date,
                execution_date=execution_date,
                signal_price=signal_record.close,
                execution_price=execution_price,
                execution_price_field=execution_price_field,
                execution_assumption=execution_assumption,
                risk_flags=fill_flags,
            )
        )
    return tuple(fills), ending_value, tuple(risk_flags)


def _next_trading_date(all_dates: tuple[date, ...], current: date) -> date | None:
    for candidate in all_dates:
        if candidate > current:
            return candidate
    return None


def _weight_turnover(previous: dict[str, float], current: dict[str, float]) -> float:
    symbols = set(previous) | set(current)
    return sum(
        abs(current.get(symbol, 0.0) - previous.get(symbol, 0.0)) for symbol in symbols
    )
