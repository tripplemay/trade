"""FillJournalEntry model — append-only per-fill journal (B023 F001).

Each row is one execution leg the user reports after manually trading in
their broker app. Reconciliation matches by ``(ticket_id, order_seq)``
first, then falls back to ``(ticket_id, symbol, side)``. ``source``
distinguishes CSV upload from per-row manual entry so the UI can show
provenance without re-parsing.

``shares`` is unsigned; ``side`` carries the direction. ``commission`` +
``fees`` are kept separate for slippage analytics (commissions vs market
impact).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class FillJournalEntry(Base):
    __tablename__ = "fill_journal_entry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_seq: Mapped[int | None] = mapped_column(nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    shares: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    fill_price: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    fees: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"FillJournalEntry(id={self.id!r}, ticket_id={self.ticket_id!r}, "
            f"symbol={self.symbol!r}, side={self.side!r})"
        )
