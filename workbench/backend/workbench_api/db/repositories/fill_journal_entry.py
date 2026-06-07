"""FillJournalEntryRepository — append-only fills journal (B023 F001).

Beyond the generic 5-method surface, exposes:

* ``list_by_ticket(ticket_id)`` — every fill recorded against a given
  ticket, ordered by ``order_seq`` (nulls last) then ``filled_at``. The
  F004 fills viewer and the F005 reconcile route both call this.
"""

from __future__ import annotations

from sqlalchemy import select

from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.repositories.base import Repository


class FillJournalEntryRepository(Repository[FillJournalEntry, str]):
    model = FillJournalEntry
    primary_key_attr = "id"

    def list_by_ticket(self, ticket_id: str) -> list[FillJournalEntry]:
        stmt = (
            select(FillJournalEntry)
            .where(FillJournalEntry.ticket_id == ticket_id)
            .order_by(
                FillJournalEntry.order_seq.is_(None),
                FillJournalEntry.order_seq,
                FillJournalEntry.filled_at,
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_all_chronological(self) -> list[FillJournalEntry]:
        """Every fill across all tickets, oldest ``filled_at`` first.

        B048 F004: the wash-sale detector scans the whole fills history to
        pair a loss sale with a repurchase of the same symbol within 30
        days, so it needs the cross-ticket chronological view."""

        stmt = select(FillJournalEntry).order_by(
            FillJournalEntry.filled_at, FillJournalEntry.order_seq
        )
        return list(self._session.execute(stmt).scalars().all())
