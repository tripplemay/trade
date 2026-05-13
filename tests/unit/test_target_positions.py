import json
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from trade.paper_prep.target_positions import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AccountState,
    DefensiveAllocation,
    TargetPositionEntry,
    TargetPositions,
    TargetPositionsValidationError,
    target_positions_from_dict,
    target_positions_to_dict,
    validate_target_positions,
)


def _account() -> AccountState:
    return AccountState(
        account_state_id="research-account-default",
        cash=250_000.0,
        equity_value=0.0,
        open_positions={},
    )


def _valid_target_positions(
    *,
    entries: tuple[TargetPositionEntry, ...] | None = None,
    defensive: DefensiveAllocation | None = None,
) -> TargetPositions:
    account = _account()
    entries = entries or (
        TargetPositionEntry(symbol="SPY", target_weight=0.4, target_dollar_exposure=100_000.0),
        TargetPositionEntry(symbol="AGG", target_weight=0.3, target_dollar_exposure=75_000.0),
    )
    defensive = defensive or DefensiveAllocation(
        symbol="SGOV", weight=0.3, dollar_exposure=75_000.0
    )
    return TargetPositions(
        schema_version=SCHEMA_VERSION,
        target_positions_id="deadbeef",
        strategy_id=None,
        portfolio_id="master_portfolio_mvp",
        signal_date=date(2024, 6, 30),
        generation_timestamp=datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
        snapshot_id="fixture:test",
        snapshot_manifest_path=None,
        account_state_reference=account.account_state_id,
        entries=entries,
        defensive_allocation=defensive,
        research_limitations=("research-only fixture",),
        disclaimer=DISCLAIMER,
    )


def test_target_positions_schema_constants_match_spec() -> None:
    assert SCHEMA_VERSION == "target-positions/v1"
    assert "research-only" in DISCLAIMER.lower()
    assert "trading instruction" in DISCLAIMER.lower()


def test_validate_target_positions_accepts_valid_payload() -> None:
    validate_target_positions(_valid_target_positions(), _account())


def test_validate_target_positions_requires_either_strategy_or_portfolio_id() -> None:
    positions = replace(_valid_target_positions(), strategy_id=None, portfolio_id=None)
    with pytest.raises(TargetPositionsValidationError, match="strategy_id"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_both_strategy_and_portfolio_id_set() -> None:
    positions = replace(
        _valid_target_positions(),
        strategy_id="global_etf_momentum",
        portfolio_id="master_portfolio_mvp",
    )
    with pytest.raises(TargetPositionsValidationError, match="strategy_id"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_negative_weight() -> None:
    bad_entries = (
        TargetPositionEntry(symbol="SPY", target_weight=-0.1, target_dollar_exposure=-25_000.0),
        TargetPositionEntry(symbol="AGG", target_weight=0.8, target_dollar_exposure=200_000.0),
    )
    positions = _valid_target_positions(
        entries=bad_entries,
        defensive=DefensiveAllocation(symbol="SGOV", weight=0.3, dollar_exposure=75_000.0),
    )
    with pytest.raises(TargetPositionsValidationError, match="non-negative"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_weights_not_summing_to_one() -> None:
    bad_entries = (
        TargetPositionEntry(symbol="SPY", target_weight=0.4, target_dollar_exposure=100_000.0),
        TargetPositionEntry(symbol="AGG", target_weight=0.2, target_dollar_exposure=50_000.0),
    )
    positions = _valid_target_positions(
        entries=bad_entries,
        defensive=DefensiveAllocation(symbol="SGOV", weight=0.3, dollar_exposure=75_000.0),
    )
    with pytest.raises(TargetPositionsValidationError, match="sum to 1.0"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_leverage_against_account_state() -> None:
    bad_entries = (
        TargetPositionEntry(symbol="SPY", target_weight=0.7, target_dollar_exposure=200_000.0),
        TargetPositionEntry(symbol="AGG", target_weight=0.3, target_dollar_exposure=200_000.0),
    )
    positions = _valid_target_positions(
        entries=bad_entries,
        defensive=DefensiveAllocation(symbol="SGOV", weight=0.0, dollar_exposure=0.0),
    )
    with pytest.raises(TargetPositionsValidationError, match="leverage"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_duplicate_symbols() -> None:
    bad_entries = (
        TargetPositionEntry(symbol="SPY", target_weight=0.35, target_dollar_exposure=87_500.0),
        TargetPositionEntry(symbol="SPY", target_weight=0.35, target_dollar_exposure=87_500.0),
    )
    positions = _valid_target_positions(
        entries=bad_entries,
        defensive=DefensiveAllocation(symbol="SGOV", weight=0.3, dollar_exposure=75_000.0),
    )
    with pytest.raises(TargetPositionsValidationError, match="duplicate"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_defensive_symbol_colliding_with_entry() -> None:
    bad_entries = (
        TargetPositionEntry(symbol="SGOV", target_weight=0.4, target_dollar_exposure=100_000.0),
    )
    positions = _valid_target_positions(
        entries=bad_entries,
        defensive=DefensiveAllocation(symbol="SGOV", weight=0.6, dollar_exposure=150_000.0),
    )
    with pytest.raises(TargetPositionsValidationError, match="duplicate"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_account_state_reference_mismatch() -> None:
    other_account = AccountState(
        account_state_id="another-account",
        cash=250_000.0,
        equity_value=0.0,
        open_positions={},
    )
    with pytest.raises(TargetPositionsValidationError, match="account_state_reference"):
        validate_target_positions(_valid_target_positions(), other_account)


def test_validate_target_positions_rejects_missing_disclaimer() -> None:
    positions = replace(_valid_target_positions(), disclaimer="go ahead and trade")
    with pytest.raises(TargetPositionsValidationError, match="disclaimer"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_empty_research_limitations() -> None:
    positions = replace(_valid_target_positions(), research_limitations=())
    with pytest.raises(TargetPositionsValidationError, match="research_limitations"):
        validate_target_positions(positions, _account())


def test_validate_target_positions_rejects_unsupported_schema_version() -> None:
    positions = replace(_valid_target_positions(), schema_version="target-positions/v999")
    with pytest.raises(TargetPositionsValidationError, match="schema_version"):
        validate_target_positions(positions, _account())


def test_target_positions_to_dict_roundtrips() -> None:
    positions = _valid_target_positions()

    payload = target_positions_to_dict(positions)
    serialized = json.dumps(payload, sort_keys=True)
    restored = target_positions_from_dict(json.loads(serialized))

    assert restored == positions
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["entries"][0]["symbol"] == "SPY"
    assert payload["defensive_allocation"]["symbol"] == "SGOV"


def test_target_positions_serialization_keys_match_schema() -> None:
    positions = _valid_target_positions()
    payload = target_positions_to_dict(positions)

    assert set(payload) == {
        "schema_version",
        "target_positions_id",
        "strategy_id",
        "portfolio_id",
        "signal_date",
        "generation_timestamp",
        "snapshot_id",
        "snapshot_manifest_path",
        "account_state_reference",
        "entries",
        "defensive_allocation",
        "research_limitations",
        "disclaimer",
    }


def test_target_positions_dollar_exposures_match_weights() -> None:
    positions = _valid_target_positions()

    total_exposure = sum(entry.target_dollar_exposure for entry in positions.entries) + (
        positions.defensive_allocation.dollar_exposure
    )
    assert total_exposure == pytest.approx(250_000.0)
