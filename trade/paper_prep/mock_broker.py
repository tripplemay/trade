"""MockBroker: journal-only research-paper-prep adapter.

The MockBroker validates incoming Target Positions, appends one JSON Lines record per
submission to a local journal file, and returns a deterministic journal entry. It never
opens a socket, never reads ``os.environ``, never imports any real broker SDK, and never
claims a paper or live execution. The default account state holds USD 250000 of cash and
no open positions; it is purely a research-only artifact intended to feed downstream
research review, not a trading instruction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trade.paper_prep.broker_adapter import BrokerAdapter, JournalEntry, OpenOrder
from trade.paper_prep.target_positions import (
    AccountState,
    TargetPositions,
    target_positions_to_dict,
    validate_target_positions,
)

DEFAULT_ACCOUNT_STATE_ID = "research-account-default"
DEFAULT_CASH = 250_000.0
DEFAULT_JOURNAL_PATH = Path("data") / "paper-prep" / "mock-broker-journal.jsonl"


def default_account_state() -> AccountState:
    """Return the fixed research account state used by default."""

    return AccountState(
        account_state_id=DEFAULT_ACCOUNT_STATE_ID,
        cash=DEFAULT_CASH,
        equity_value=0.0,
        open_positions={},
    )


def _system_clock() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class _Config:
    account_state: AccountState
    journal_path: Path
    clock: Callable[[], datetime]


class MockBroker(BrokerAdapter):
    """Research-only Mock Broker that journals submitted target positions."""

    _config: _Config

    def __init__(
        self,
        *,
        account_state: AccountState,
        journal_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = _Config(
            account_state=account_state,
            journal_path=journal_path,
            clock=clock if clock is not None else _system_clock,
        )

    def submit_target_positions(self, positions: TargetPositions) -> JournalEntry:
        validate_target_positions(positions, self._config.account_state)
        recorded_at = self._config.clock()
        journal_entry_id = _build_journal_entry_id(positions, recorded_at)
        entry = JournalEntry(
            journal_entry_id=journal_entry_id,
            recorded_at=recorded_at,
            target_positions=positions,
        )
        self._append_journal_line(entry)
        return entry

    def get_account_state(self) -> AccountState:
        return self._config.account_state

    def get_open_orders(self) -> Sequence[OpenOrder]:
        return ()

    def _append_journal_line(self, entry: JournalEntry) -> None:
        path = self._config.journal_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "journal_entry_id": entry.journal_entry_id,
            "recorded_at": entry.recorded_at.isoformat(),
            "target_positions": target_positions_to_dict(entry.target_positions),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")


def _build_journal_entry_id(positions: TargetPositions, recorded_at: datetime) -> str:
    digest_payload = json.dumps(
        {
            "target_positions_id": positions.target_positions_id,
            "recorded_at": recorded_at.isoformat(),
            "signal_date": positions.signal_date.isoformat(),
            "schema_version": positions.schema_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(digest_payload).hexdigest()[:32]
