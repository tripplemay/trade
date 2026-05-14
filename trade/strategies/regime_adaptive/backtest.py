"""Regime-adaptive monthly backtest with tolerance-band rebalancing.

Drives the L1 → L2 → L3 pipeline at each supplied monthly signal date, applies a
tolerance-band rule to suppress small per-asset weight drifts, forces a full rebalance
whenever the regime label changes between periods, executes at T+1 open, chains equity
across periods, and exposes a B011-compatible account-level drawdown kill-switch payload.
All outputs are research-only and never authorize any paper or production order flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade.backtest.master_portfolio import (
    KILL_SWITCH_CLEARED,
    KILL_SWITCH_TRIGGERED,
    MasterAccountRiskState,
    MasterKillSwitchEvent,
    apply_kill_switch_constraint,
    drawdown_against_hwm,
)
from trade.backtest.monthly import (
    BacktestError,
    BacktestParameters,
    EquityPoint,
    ExecutionFill,
)
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    RegimeAdaptiveConfig,
    validate_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.regime import (
    RegimeState,
    apply_regime_exposure_adjustment,
    detect_regime,
)
from trade.strategies.regime_adaptive.trend_gating import (
    TrendGatingResult,
    apply_trend_gating,
    build_policy_skipped_trend_result,
    should_l1_gate_run,
)
from trade.strategies.regime_adaptive.weighting import (
    RegimeAdaptiveWeightAllocation,
    derive_regime_adaptive_weights,
)


@dataclass(frozen=True, slots=True)
class RegimeAdaptivePeriodResult:
    signal_date: date
    execution_date: date
    valuation_date: date
    target_weights: dict[str, float]
    effective_weights: dict[str, float]
    sleeve_allocation: RegimeAdaptiveWeightAllocation
    gating_result: TrendGatingResult
    regime_state: RegimeState
    fills: tuple[ExecutionFill, ...]
    starting_value: float
    ending_value: float
    cost_amount: float
    turnover: float
    suppressed_by_tolerance: tuple[str, ...]
    forced_rebalance_by_regime_transition: bool
    pre_rebalance_account_risk_state: MasterAccountRiskState
    weights_capped_by_kill_switch: dict[str, float]
    risk_flags: tuple[str, ...]
    l1_active: bool


@dataclass(frozen=True, slots=True)
class RegimeAdaptiveBacktestResult:
    starting_capital: float
    ending_value: float
    config: RegimeAdaptiveConfig
    rebalance_results: tuple[RegimeAdaptivePeriodResult, ...]
    equity_curve: tuple[EquityPoint, ...]
    turnover: float
    cost_amount: float
    risk_flags: tuple[str, ...]
    cost_bps: float
    slippage_bps: float
    account_risk_state: MasterAccountRiskState
    kill_switch_events: tuple[MasterKillSwitchEvent, ...]


def run_regime_adaptive_monthly_backtest(
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    config: RegimeAdaptiveConfig | None = None,
    backtest_parameters: BacktestParameters | None = None,
    kill_switch_clearance_signal_dates: tuple[date, ...] = (),
) -> RegimeAdaptiveBacktestResult:
    if not signal_dates:
        raise BacktestError("signal_dates must not be empty")
    if config is None:
        config = RegimeAdaptiveConfig()
    validate_regime_adaptive_config(config)
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()
    if backtest_parameters.starting_capital <= 0:
        raise BacktestError("starting_capital must be positive")

    by_symbol_date = {(record.symbol, record.date): record for record in records}
    all_dates = tuple(sorted({record.date for record in records}))
    clearance_set = set(kill_switch_clearance_signal_dates)
    drawdown_threshold = config.account_drawdown_threshold
    defensive_symbol = config.defensive_symbol

    current_capital = backtest_parameters.starting_capital
    high_water_mark = current_capital
    drawdown = 0.0
    kill_switch_active = False
    kill_switch_triggered_at: date | None = None
    kill_switch_trigger_drawdown: float | None = None
    previous_effective_weights: dict[str, float] = {}
    previous_regime: str | None = None
    periods: list[RegimeAdaptivePeriodResult] = []
    equity_points: list[EquityPoint] = [EquityPoint(signal_dates[0], current_capital)]
    kill_switch_events: list[MasterKillSwitchEvent] = []
    total_turnover = 0.0
    total_cost = 0.0
    risk_flags: list[str] = []
    friction_rate = (
        backtest_parameters.cost_bps + backtest_parameters.slippage_bps
    ) / 10_000.0

    for index, signal_date in enumerate(signal_dates):
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

        regime_state = detect_regime(
            records, previous_effective_weights, config, signal_date
        )
        l1_active = should_l1_gate_run(
            regime_state.regime, config.regime_activation_policy
        )
        if l1_active:
            gating_result = apply_trend_gating(records, config, signal_date)
        else:
            gating_result = build_policy_skipped_trend_result(records, config, signal_date)
        allocation = derive_regime_adaptive_weights(records, config, signal_date, gating_result)
        target_weights = apply_regime_exposure_adjustment(
            allocation.target_weights, regime_state, config
        )

        forced_full_rebalance = (
            previous_regime is not None and regime_state.regime != previous_regime
        )
        effective_weights, suppressed = _apply_tolerance_band(
            target_weights=target_weights,
            prior_weights=previous_effective_weights,
            tolerance=config.tolerance_band,
            defensive_symbol=defensive_symbol,
            forced_full_rebalance=forced_full_rebalance,
        )

        if kill_switch_active:
            effective_weights, weights_capped_by_kill_switch = apply_kill_switch_constraint(
                new_weights=effective_weights,
                prior_weights=previous_effective_weights,
                defensive_asset=defensive_symbol,
            )
        else:
            weights_capped_by_kill_switch = {}

        execution_date = _next_trading_date(all_dates, signal_date)
        if execution_date is None:
            raise BacktestError(
                "no trading date exists after signal_date for T+1 open execution"
            )
        valuation_date = (
            signal_dates[index + 1] if index + 1 < len(signal_dates) else all_dates[-1]
        )

        turnover = _weight_turnover(previous_effective_weights, effective_weights)
        period_cost = current_capital * turnover * friction_rate

        fills, ending_value, period_flags = _execute_period(
            by_symbol_date=by_symbol_date,
            capital=current_capital,
            signal_date=signal_date,
            execution_date=execution_date,
            valuation_date=valuation_date,
            target=effective_weights,
        )
        ending_value -= period_cost

        periods.append(
            RegimeAdaptivePeriodResult(
                signal_date=signal_date,
                execution_date=execution_date,
                valuation_date=valuation_date,
                target_weights=target_weights,
                effective_weights=effective_weights,
                sleeve_allocation=allocation,
                gating_result=gating_result,
                regime_state=regime_state,
                fills=fills,
                starting_value=current_capital,
                ending_value=ending_value,
                cost_amount=period_cost,
                turnover=turnover,
                suppressed_by_tolerance=suppressed,
                forced_rebalance_by_regime_transition=forced_full_rebalance,
                pre_rebalance_account_risk_state=pre_rebalance_state,
                weights_capped_by_kill_switch=weights_capped_by_kill_switch,
                risk_flags=tuple(period_flags),
                l1_active=l1_active,
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

        previous_effective_weights = effective_weights
        previous_regime = regime_state.regime
        current_capital = ending_value

    final_account_risk_state = MasterAccountRiskState(
        high_water_mark=high_water_mark,
        drawdown=drawdown,
        kill_switch_active=kill_switch_active,
        kill_switch_triggered_at=kill_switch_triggered_at,
        kill_switch_trigger_drawdown=kill_switch_trigger_drawdown,
        human_review_required=kill_switch_active,
    )

    return RegimeAdaptiveBacktestResult(
        starting_capital=backtest_parameters.starting_capital,
        ending_value=current_capital,
        config=config,
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


def _apply_tolerance_band(
    *,
    target_weights: dict[str, float],
    prior_weights: dict[str, float],
    tolerance: float,
    defensive_symbol: str,
    forced_full_rebalance: bool,
) -> tuple[dict[str, float], tuple[str, ...]]:
    if forced_full_rebalance or not prior_weights:
        return dict(target_weights), ()
    all_symbols = set(target_weights) | set(prior_weights)
    effective: dict[str, float] = {}
    suppressed: list[str] = []
    for symbol in all_symbols:
        target = target_weights.get(symbol, 0.0)
        prior = prior_weights.get(symbol, 0.0)
        if abs(target - prior) > tolerance:
            effective[symbol] = target
        else:
            effective[symbol] = prior
            if abs(target - prior) > 0:
                suppressed.append(symbol)
    total = sum(effective.values())
    residual = 1.0 - total
    if abs(residual) > 1e-12:
        effective[defensive_symbol] = effective.get(defensive_symbol, 0.0) + residual
    return effective, tuple(sorted(suppressed))


def _execute_period(
    *,
    by_symbol_date: dict[tuple[str, date], PriceBar],
    capital: float,
    signal_date: date,
    execution_date: date,
    valuation_date: date,
    target: dict[str, float],
) -> tuple[tuple[ExecutionFill, ...], float, tuple[str, ...]]:
    fills: list[ExecutionFill] = []
    risk_flags: list[str] = []
    ending_value = 0.0
    for symbol, weight in target.items():
        if weight <= 0:
            continue
        signal_record = by_symbol_date.get((symbol, signal_date))
        if signal_record is None:
            risk_flags.append(f"missing_signal_price:{symbol}:{signal_date.isoformat()}")
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
