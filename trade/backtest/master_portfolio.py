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
KILL_SWITCH_TRIGGERED = "triggered"
KILL_SWITCH_CLEARED = "cleared"


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
class MasterAccountRiskState:
    high_water_mark: float
    drawdown: float
    kill_switch_active: bool
    kill_switch_triggered_at: date | None
    kill_switch_trigger_drawdown: float | None
    human_review_required: bool


@dataclass(frozen=True, slots=True)
class MasterKillSwitchEvent:
    event_kind: str
    signal_date: date
    drawdown: float
    high_water_mark: float


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
    pre_rebalance_account_risk_state: MasterAccountRiskState
    weights_capped_by_kill_switch: dict[str, float]


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
    account_risk_state: MasterAccountRiskState
    kill_switch_events: tuple[MasterKillSwitchEvent, ...]


def drawdown_against_hwm(equity: float, high_water_mark: float) -> float:
    """Return equity/HWM - 1, clamped to 0 when HWM is non-positive."""

    if high_water_mark <= 0:
        return 0.0
    return equity / high_water_mark - 1.0


def identify_quarter_end_signal_dates(all_dates: tuple[date, ...]) -> tuple[date, ...]:
    """Return the last trading date of each calendar quarter that is confirmed complete.

    A calendar quarter is considered confirmed when the supplied ``all_dates`` contain at
    least one trading date in the following calendar quarter; otherwise the data may simply
    be truncated mid-quarter and the latest trading date is not a true quarter-end. This
    guarantees that the returned signal dates have at least one trading date available for
    T+1 open execution.
    """

    if not all_dates:
        return ()
    by_quarter: dict[tuple[int, int], date] = {}
    quarters_present: set[tuple[int, int]] = set()
    for trading_date in all_dates:
        quarter_index = (trading_date.month - 1) // 3 + 1
        key = (trading_date.year, quarter_index)
        quarters_present.add(key)
        existing = by_quarter.get(key)
        if existing is None or trading_date > existing:
            by_quarter[key] = trading_date
    confirmed_quarter_ends: list[date] = []
    for (year, quarter), end_date in by_quarter.items():
        next_quarter = (year, quarter + 1) if quarter < 4 else (year + 1, 1)
        if next_quarter in quarters_present:
            confirmed_quarter_ends.append(end_date)
    return tuple(sorted(confirmed_quarter_ends))


def _validate_quarter_end_signal_dates(
    signal_dates: tuple[date, ...], all_dates: tuple[date, ...]
) -> None:
    quarter_end_dates = identify_quarter_end_signal_dates(all_dates)
    quarter_end_set = set(quarter_end_dates)
    seen: set[date] = set()
    for signal_date in signal_dates:
        if signal_date not in quarter_end_set:
            raise BacktestError(
                f"signal_date {signal_date.isoformat()} is not a calendar quarter-end in the "
                f"supplied records; expected one of: "
                f"{[d.isoformat() for d in quarter_end_dates]}"
            )
        if signal_date in seen:
            raise BacktestError(
                f"duplicate quarter-end signal_date: {signal_date.isoformat()}"
            )
        seen.add(signal_date)


def apply_kill_switch_constraint(
    *,
    new_weights: dict[str, float],
    prior_weights: dict[str, float],
    defensive_asset: str,
) -> tuple[dict[str, float], dict[str, float]]:
    """Cap each non-defensive asset's new weight at its prior weight.

    Excess weight (capped reduction) is rerouted to the defensive asset. Decreases relative to
    prior are preserved untouched. Returns the capped weights plus a mapping of asset to the
    reduction amount applied.
    """

    capped: dict[str, float] = dict(new_weights)
    reductions: dict[str, float] = {}
    excess = 0.0
    for asset, weight in new_weights.items():
        if asset == defensive_asset:
            continue
        prior = prior_weights.get(asset, 0.0)
        if weight > prior:
            capped[asset] = prior
            reduction = weight - prior
            reductions[asset] = round(reduction, WEIGHT_ROUND_DIGITS)
            excess += reduction
    if excess > 0:
        capped[defensive_asset] = capped.get(defensive_asset, 0.0) + excess
    capped = {asset: round(weight, WEIGHT_ROUND_DIGITS) for asset, weight in capped.items()}
    return capped, reductions


def run_master_portfolio_quarterly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    master_parameters: MasterPortfolioParameters | None = None,
    child_parameters: MasterChildStrategyParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
    kill_switch_clearance_signal_dates: tuple[date, ...] = (),
) -> MasterPortfolioBacktestResult:
    """Run a quarterly Master Portfolio backtest with account-level kill-switch."""

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
    _validate_quarter_end_signal_dates(signal_dates, all_dates)
    clearance_set = set(kill_switch_clearance_signal_dates)
    drawdown_threshold = master_parameters.drawdown_threshold
    defensive_asset = master_parameters.defensive_asset

    current_capital = backtest_parameters.starting_capital
    high_water_mark = current_capital
    drawdown = 0.0
    kill_switch_active = False
    kill_switch_triggered_at: date | None = None
    kill_switch_trigger_drawdown: float | None = None
    previous_portfolio_weights: dict[str, float] = {}
    periods: list[MasterRebalancePeriodResult] = []
    equity_points: list[EquityPoint] = [EquityPoint(signal_dates[0], current_capital)]
    kill_switch_events: list[MasterKillSwitchEvent] = []
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []
    friction_rate = (
        backtest_parameters.cost_bps + backtest_parameters.slippage_bps
    ) / 10_000.0

    for period_index, signal_date in enumerate(signal_dates):
        if kill_switch_active and signal_date in clearance_set:
            kill_switch_active = False
            kill_switch_triggered_at = None
            kill_switch_trigger_drawdown = None
            kill_switch_events.append(
                MasterKillSwitchEvent(
                    event_kind=KILL_SWITCH_CLEARED,
                    signal_date=signal_date,
                    drawdown=drawdown,
                    high_water_mark=high_water_mark,
                )
            )

        pre_rebalance_state = MasterAccountRiskState(
            high_water_mark=high_water_mark,
            drawdown=drawdown,
            kill_switch_active=kill_switch_active,
            kill_switch_triggered_at=kill_switch_triggered_at,
            kill_switch_trigger_drawdown=kill_switch_trigger_drawdown,
            human_review_required=kill_switch_active,
        )

        execution_date = _next_trading_date(all_dates, signal_date)
        if execution_date is None:
            raise BacktestError(
                "no trading date exists after signal_date for T+1 open execution"
            )
        if period_index + 1 < len(signal_dates):
            valuation_date = signal_dates[period_index + 1]
        else:
            valuation_date = all_dates[-1]

        sleeve_contributions, raw_portfolio_target = _build_portfolio_target(
            sleeves=master_parameters.sleeves,
            defensive_asset=defensive_asset,
            records=records,
            signal_date=signal_date,
            momentum_params=momentum_params,
            risk_parity_params=risk_parity_params,
        )

        if kill_switch_active:
            portfolio_target, weights_capped_by_kill_switch = apply_kill_switch_constraint(
                new_weights=raw_portfolio_target,
                prior_weights=previous_portfolio_weights,
                defensive_asset=defensive_asset,
            )
        else:
            portfolio_target = raw_portfolio_target
            weights_capped_by_kill_switch = {}

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
                pre_rebalance_account_risk_state=pre_rebalance_state,
                weights_capped_by_kill_switch=weights_capped_by_kill_switch,
            )
        )
        equity_points.append(EquityPoint(valuation_date, ending_value))
        total_turnover += turnover
        total_cost += period_cost
        risk_flags.extend(period_flags)

        high_water_mark = max(high_water_mark, ending_value)
        drawdown = drawdown_against_hwm(ending_value, high_water_mark)
        if not kill_switch_active and drawdown <= -drawdown_threshold:
            kill_switch_active = True
            kill_switch_triggered_at = signal_date
            kill_switch_trigger_drawdown = drawdown
            kill_switch_events.append(
                MasterKillSwitchEvent(
                    event_kind=KILL_SWITCH_TRIGGERED,
                    signal_date=signal_date,
                    drawdown=drawdown,
                    high_water_mark=high_water_mark,
                )
            )

        previous_portfolio_weights = portfolio_target
        current_capital = ending_value

    final_account_risk_state = MasterAccountRiskState(
        high_water_mark=high_water_mark,
        drawdown=drawdown,
        kill_switch_active=kill_switch_active,
        kill_switch_triggered_at=kill_switch_triggered_at,
        kill_switch_trigger_drawdown=kill_switch_trigger_drawdown,
        human_review_required=kill_switch_active,
    )

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
        account_risk_state=final_account_risk_state,
        kill_switch_events=tuple(kill_switch_events),
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
