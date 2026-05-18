"""OrderTicket model — one row per ticket generation (B023 F001).

A ticket records that the user generated an order list from the
Recommendations page and Markdown was emitted to ``docs/runs/<date>/``.
The DB row is the canonical artifact (status transitions live here);
the Markdown file is the human-readable copy.

Status transitions are user-driven:
  ``generated`` → ``executed`` when reconciled with fills
  ``generated`` → ``voided``   when the user decides not to trade

The user remains the execution agent — workbench never sends to a
broker. See B023 spec §Hard boundaries.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class OrderTicket(Base):
    __tablename__ = "order_ticket"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_positions_id: Mapped[str] = mapped_column(String(64), nullable=False)
    markdown_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"OrderTicket(id={self.id!r}, status={self.status!r})"
