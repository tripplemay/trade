"""Repository layer — thin SQLAlchemy wrappers, zero business logic.

Each repository exposes the same five-method surface (``get_by_id``,
``list_all``, ``upsert``, ``delete``, ``count``) so route handlers and the
bootstrap CLI can swap models without learning new ergonomics. B023 F001
adds the execution-workflow trio (OrderTicket, FillJournalEntry,
AccountSnapshot) with a few bespoke helpers (``latest`` /
``list_by_ticket`` / ``reconcile``) on top of the shared base.
"""

from workbench_api.db.repositories.account import AccountRepository
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.backlog import BacklogRepository
from workbench_api.db.repositories.base import Repository
from workbench_api.db.repositories.fill_journal_entry import FillJournalEntryRepository
from workbench_api.db.repositories.llm_budget_log import LLMBudgetLogRepository
from workbench_api.db.repositories.order_ticket import OrderTicketRepository
from workbench_api.db.repositories.snapshot import SnapshotMetaRepository

__all__ = [
    "AccountRepository",
    "AccountSnapshotRepository",
    "BacklogRepository",
    "FillJournalEntryRepository",
    "LLMBudgetLogRepository",
    "OrderTicketRepository",
    "Repository",
    "SnapshotMetaRepository",
]
