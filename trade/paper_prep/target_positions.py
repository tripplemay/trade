"""Target Positions output schema for B012 Paper Trading prep.

This module defines the research-only Target Positions data contract. It exposes both
percentage weights and dollar exposures, declares snapshot / account references, and
includes a fixed disclaimer marking every payload as a research artifact rather than a
trading instruction. The validator rejects negative weights, leverage against the supplied
account state, duplicate symbols, weights that do not sum to one, and unknown schema
versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

SCHEMA_VERSION = "target-positions/v1"
DISCLAIMER = (
    "research-only; not a trading instruction. B012 outputs are produced for research "
    "review and never authorize any paper or live trading action."
)
WEIGHT_SUM_TOLERANCE = 1e-8
LEVERAGE_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class AccountState:
    """Fixed research account state used to convert percentage weights to dollar exposures."""

    account_state_id: str
    cash: float
    equity_value: float
    open_positions: dict[str, float]


@dataclass(frozen=True, slots=True)
class TargetPositionEntry:
    """Single non-defensive Target Positions entry."""

    symbol: str
    target_weight: float
    target_dollar_exposure: float


@dataclass(frozen=True, slots=True)
class DefensiveAllocation:
    """Defensive sleeve allocation routing the residual weight + dollar exposure."""

    symbol: str
    weight: float
    dollar_exposure: float


@dataclass(frozen=True, slots=True)
class TargetPositions:
    """Research-only Target Positions payload."""

    schema_version: str
    target_positions_id: str
    strategy_id: str | None
    portfolio_id: str | None
    signal_date: date
    generation_timestamp: datetime
    snapshot_id: str
    snapshot_manifest_path: str | None
    account_state_reference: str
    entries: tuple[TargetPositionEntry, ...]
    defensive_allocation: DefensiveAllocation
    research_limitations: tuple[str, ...]
    disclaimer: str


class TargetPositionsValidationError(ValueError):
    """Raised when a TargetPositions payload violates the B012 research boundary."""


def validate_target_positions(positions: TargetPositions, account_state: AccountState) -> None:
    if positions.schema_version != SCHEMA_VERSION:
        raise TargetPositionsValidationError(
            f"unsupported schema_version {positions.schema_version!r}; expected {SCHEMA_VERSION!r}"
        )
    if positions.disclaimer != DISCLAIMER:
        raise TargetPositionsValidationError(
            "disclaimer must be the fixed research-only literal"
        )
    if not positions.research_limitations:
        raise TargetPositionsValidationError("research_limitations must not be empty")
    if (positions.strategy_id is None) == (positions.portfolio_id is None):
        raise TargetPositionsValidationError(
            "exactly one of strategy_id or portfolio_id must be set"
        )
    if positions.account_state_reference != account_state.account_state_id:
        raise TargetPositionsValidationError(
            "account_state_reference does not match supplied account state"
        )

    seen_symbols: set[str] = set()
    for entry in positions.entries:
        if entry.symbol in seen_symbols:
            raise TargetPositionsValidationError(f"duplicate symbol in entries: {entry.symbol}")
        seen_symbols.add(entry.symbol)
        if entry.target_weight < 0:
            raise TargetPositionsValidationError(
                f"target_weight must be non-negative for {entry.symbol}"
            )
        if entry.target_dollar_exposure < 0:
            raise TargetPositionsValidationError(
                f"target_dollar_exposure must be non-negative for {entry.symbol}"
            )
    if positions.defensive_allocation.symbol in seen_symbols:
        raise TargetPositionsValidationError(
            f"duplicate symbol between entries and defensive_allocation: "
            f"{positions.defensive_allocation.symbol}"
        )
    if positions.defensive_allocation.weight < 0:
        raise TargetPositionsValidationError("defensive_allocation.weight must be non-negative")
    if positions.defensive_allocation.dollar_exposure < 0:
        raise TargetPositionsValidationError(
            "defensive_allocation.dollar_exposure must be non-negative"
        )

    total_weight = (
        sum(entry.target_weight for entry in positions.entries)
        + positions.defensive_allocation.weight
    )
    if abs(total_weight - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise TargetPositionsValidationError(
            f"entry weights plus defensive_allocation.weight must sum to 1.0 (got {total_weight})"
        )

    total_dollar = (
        sum(entry.target_dollar_exposure for entry in positions.entries)
        + positions.defensive_allocation.dollar_exposure
    )
    capacity = account_state.cash + account_state.equity_value
    if total_dollar > capacity + LEVERAGE_TOLERANCE:
        raise TargetPositionsValidationError(
            f"total target dollar exposure {total_dollar} exceeds account capacity {capacity}; "
            f"leverage is not allowed"
        )


def target_positions_to_dict(positions: TargetPositions) -> dict[str, Any]:
    return {
        "schema_version": positions.schema_version,
        "target_positions_id": positions.target_positions_id,
        "strategy_id": positions.strategy_id,
        "portfolio_id": positions.portfolio_id,
        "signal_date": positions.signal_date.isoformat(),
        "generation_timestamp": positions.generation_timestamp.isoformat(),
        "snapshot_id": positions.snapshot_id,
        "snapshot_manifest_path": positions.snapshot_manifest_path,
        "account_state_reference": positions.account_state_reference,
        "entries": [
            {
                "symbol": entry.symbol,
                "target_weight": entry.target_weight,
                "target_dollar_exposure": entry.target_dollar_exposure,
            }
            for entry in positions.entries
        ],
        "defensive_allocation": {
            "symbol": positions.defensive_allocation.symbol,
            "weight": positions.defensive_allocation.weight,
            "dollar_exposure": positions.defensive_allocation.dollar_exposure,
        },
        "research_limitations": list(positions.research_limitations),
        "disclaimer": positions.disclaimer,
    }


def target_positions_from_dict(payload: dict[str, Any]) -> TargetPositions:
    return TargetPositions(
        schema_version=payload["schema_version"],
        target_positions_id=payload["target_positions_id"],
        strategy_id=payload["strategy_id"],
        portfolio_id=payload["portfolio_id"],
        signal_date=date.fromisoformat(payload["signal_date"]),
        generation_timestamp=datetime.fromisoformat(payload["generation_timestamp"]),
        snapshot_id=payload["snapshot_id"],
        snapshot_manifest_path=payload["snapshot_manifest_path"],
        account_state_reference=payload["account_state_reference"],
        entries=tuple(
            TargetPositionEntry(
                symbol=entry["symbol"],
                target_weight=entry["target_weight"],
                target_dollar_exposure=entry["target_dollar_exposure"],
            )
            for entry in payload["entries"]
        ),
        defensive_allocation=DefensiveAllocation(
            symbol=payload["defensive_allocation"]["symbol"],
            weight=payload["defensive_allocation"]["weight"],
            dollar_exposure=payload["defensive_allocation"]["dollar_exposure"],
        ),
        research_limitations=tuple(payload["research_limitations"]),
        disclaimer=payload["disclaimer"],
    )
