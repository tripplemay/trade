"""Backtest-to-Paper Trading prep bridge.

Convert a B011 Master Portfolio backtest result or a B006/B010 single-strategy backtest
result into a research-only :class:`TargetPositions` payload. Each bridge function picks
the latest rebalance period by default and accepts an optional ``signal_date`` to target a
specific period. A request for a ``signal_date`` not present in the backtest result fails
closed with :class:`BridgeError`; account capacity guards against leverage through the
shared :func:`validate_target_positions` checks. The bridge does not enforce cadence and
can be triggered manually at any time; all output remains research-only and never
authorizes a paper or live trading action.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from trade.backtest.master_portfolio import MasterPortfolioBacktestResult
from trade.backtest.monthly import MonthlyBacktestResult
from trade.backtest.risk_parity import RiskParityBacktestResult
from trade.paper_prep.target_positions import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AccountState,
    DefensiveAllocation,
    TargetPositionEntry,
    TargetPositions,
    validate_target_positions,
)

DEFAULT_RESEARCH_LIMITATIONS: tuple[str, ...] = (
    "research-only artifact; this is not a trading instruction",
    "no_paper_or_live_execution_authorized",
    "fixture_or_research_snapshot_only",
)


class BridgeError(ValueError):
    """Raised when a backtest result cannot be bridged into TargetPositions."""


def _system_clock() -> datetime:
    return datetime.now(UTC)


def generate_target_positions_from_master(
    result: MasterPortfolioBacktestResult,
    *,
    account_state: AccountState,
    snapshot_id: str,
    signal_date: date | None = None,
    snapshot_manifest_path: str | None = None,
    research_limitations: tuple[str, ...] = DEFAULT_RESEARCH_LIMITATIONS,
    clock: Callable[[], datetime] | None = None,
) -> TargetPositions:
    if not result.rebalance_results:
        raise BridgeError("master backtest has no rebalance periods to bridge")
    period = _locate_master_period(result, signal_date)
    defensive_symbol = result.parameters.defensive_asset
    entries, defensive_allocation = _split_weights(
        weights=dict(period.portfolio_target_weights),
        defensive_symbol=defensive_symbol,
        account_state=account_state,
    )
    generation_timestamp = (clock or _system_clock)()
    positions = TargetPositions(
        schema_version=SCHEMA_VERSION,
        target_positions_id=_build_target_positions_id(
            kind="master",
            identifier=result.parameters.portfolio_id,
            signal_date=period.signal_date,
            snapshot_id=snapshot_id,
            account_state_reference=account_state.account_state_id,
            entries=entries,
            defensive_allocation=defensive_allocation,
        ),
        strategy_id=None,
        portfolio_id=result.parameters.portfolio_id,
        signal_date=period.signal_date,
        generation_timestamp=generation_timestamp,
        snapshot_id=snapshot_id,
        snapshot_manifest_path=snapshot_manifest_path,
        account_state_reference=account_state.account_state_id,
        entries=entries,
        defensive_allocation=defensive_allocation,
        research_limitations=research_limitations,
        disclaimer=DISCLAIMER,
    )
    validate_target_positions(positions, account_state)
    return positions


def generate_target_positions_from_strategy(
    result: MonthlyBacktestResult | RiskParityBacktestResult,
    *,
    account_state: AccountState,
    snapshot_id: str,
    signal_date: date | None = None,
    snapshot_manifest_path: str | None = None,
    research_limitations: tuple[str, ...] = DEFAULT_RESEARCH_LIMITATIONS,
    clock: Callable[[], datetime] | None = None,
) -> TargetPositions:
    selected_signal_date, target_weights, defensive_symbol, strategy_id = (
        _extract_strategy_period(result, signal_date)
    )
    entries, defensive_allocation = _split_weights(
        weights=dict(target_weights),
        defensive_symbol=defensive_symbol,
        account_state=account_state,
    )
    generation_timestamp = (clock or _system_clock)()
    positions = TargetPositions(
        schema_version=SCHEMA_VERSION,
        target_positions_id=_build_target_positions_id(
            kind="strategy",
            identifier=strategy_id,
            signal_date=selected_signal_date,
            snapshot_id=snapshot_id,
            account_state_reference=account_state.account_state_id,
            entries=entries,
            defensive_allocation=defensive_allocation,
        ),
        strategy_id=strategy_id,
        portfolio_id=None,
        signal_date=selected_signal_date,
        generation_timestamp=generation_timestamp,
        snapshot_id=snapshot_id,
        snapshot_manifest_path=snapshot_manifest_path,
        account_state_reference=account_state.account_state_id,
        entries=entries,
        defensive_allocation=defensive_allocation,
        research_limitations=research_limitations,
        disclaimer=DISCLAIMER,
    )
    validate_target_positions(positions, account_state)
    return positions


def _locate_master_period(
    result: MasterPortfolioBacktestResult, signal_date: date | None
) -> Any:
    if signal_date is None:
        return result.rebalance_results[-1]
    for period in result.rebalance_results:
        if period.signal_date == signal_date:
            return period
    available = [period.signal_date.isoformat() for period in result.rebalance_results]
    raise BridgeError(
        f"signal_date {signal_date.isoformat()} is not present in master rebalance_results; "
        f"available: {available}"
    )


def _extract_strategy_period(
    result: Any, signal_date: date | None
) -> tuple[date, dict[str, float], str, str]:
    signals: tuple[Any, ...]
    if isinstance(result, MonthlyBacktestResult):
        signals = (
            tuple(period.signal for period in result.rebalance_results)
            if result.rebalance_results
            else (result.signal,)
        )
        defensive_symbol = result.signal.parameters.defensive_asset
        strategy_id = result.signal.parameters.strategy_id
    elif isinstance(result, RiskParityBacktestResult):
        if not result.rebalance_results:
            raise BridgeError("risk parity backtest has no rebalance periods to bridge")
        signals = tuple(period.signal for period in result.rebalance_results)
        defensive_symbol = result.parameters.defensive_asset
        strategy_id = result.parameters.strategy_id
    else:
        raise BridgeError(
            f"unsupported strategy result type: {type(result).__name__}"
        )

    if signal_date is None:
        selected: Any = signals[-1]
    else:
        match = next(
            (signal for signal in signals if signal.signal_date == signal_date), None
        )
        if match is None:
            available = [signal.signal_date.isoformat() for signal in signals]
            raise BridgeError(
                f"signal_date {signal_date.isoformat()} is not present in strategy "
                f"rebalance_results; available: {available}"
            )
        selected = match
    return selected.signal_date, dict(selected.target_weights), defensive_symbol, strategy_id


def _split_weights(
    *,
    weights: dict[str, float],
    defensive_symbol: str,
    account_state: AccountState,
) -> tuple[tuple[TargetPositionEntry, ...], DefensiveAllocation]:
    capacity = account_state.cash + account_state.equity_value
    defensive_weight = weights.pop(defensive_symbol, 0.0)
    entries: list[TargetPositionEntry] = []
    for symbol, weight in weights.items():
        if weight <= 0:
            continue
        entries.append(
            TargetPositionEntry(
                symbol=symbol,
                target_weight=weight,
                target_dollar_exposure=weight * capacity,
            )
        )
    defensive_allocation = DefensiveAllocation(
        symbol=defensive_symbol,
        weight=defensive_weight,
        dollar_exposure=defensive_weight * capacity,
    )
    return tuple(entries), defensive_allocation


def _build_target_positions_id(
    *,
    kind: str,
    identifier: str | None,
    signal_date: date,
    snapshot_id: str,
    account_state_reference: str,
    entries: tuple[TargetPositionEntry, ...],
    defensive_allocation: DefensiveAllocation,
) -> str:
    payload = {
        "account_state_reference": account_state_reference,
        "defensive_allocation": {
            "symbol": defensive_allocation.symbol,
            "weight": defensive_allocation.weight,
        },
        "entries": [
            {"symbol": entry.symbol, "weight": entry.target_weight}
            for entry in sorted(entries, key=lambda item: item.symbol)
        ],
        "identifier": identifier,
        "kind": kind,
        "signal_date": signal_date.isoformat(),
        "snapshot_id": snapshot_id,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:32]
