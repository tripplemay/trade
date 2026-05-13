"""Abstract BrokerAdapter interface for B012 Paper Trading prep.

B012 only defines this abstract interface and the Mock implementation that journals intent
to a local JSON Lines file. Real paper or live broker adapters are explicitly out of scope
and will be addressed in a later batch (B013+). Every artifact produced through this
interface remains research-only and never authorizes any paper or live trading action.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from trade.paper_prep.target_positions import AccountState, TargetPositions

FORBIDDEN_BROKER_SDK_MODULES: tuple[str, ...] = (
    "alpaca",
    "alpaca_trade_api",
    "futu",
    "futu_api",
    "ib_insync",
    "polygon",
    "tiger",
    "tiger_api",
    "tradier",
)


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Single append-only journal record produced by submit_target_positions."""

    journal_entry_id: str
    recorded_at: datetime
    target_positions: TargetPositions


@dataclass(frozen=True, slots=True)
class OpenOrder:
    """Placeholder open-order record. B012 never produces any of these."""

    order_id: str
    symbol: str
    target_weight: float
    target_dollar_exposure: float


class BrokerAdapter(ABC):
    """Research-only adapter interface bridging Target Positions to a downstream broker.

    Concrete adapters must remain side-effect-free at construction time, must never call
    out to a paper or live trading network, and must never claim a real account balance.
    B012 ships only the MockBroker implementation.
    """

    @abstractmethod
    def submit_target_positions(self, positions: TargetPositions) -> JournalEntry:
        """Persist a research-only journal entry for the supplied target positions."""

    @abstractmethod
    def get_account_state(self) -> AccountState:
        """Return the fixed research account state associated with this adapter."""

    @abstractmethod
    def get_open_orders(self) -> Sequence[OpenOrder]:
        """Return the open order list. The B012 Mock implementation always returns ()."""
