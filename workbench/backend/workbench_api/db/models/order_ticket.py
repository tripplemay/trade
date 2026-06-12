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

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base

# B057 F004 — default strategy mode (mirrors account_snapshot). A ticket carries
# the mode it was generated for, so reconcile writes the SAME mode's account and
# the journal can be filtered per mode. Pre-B057 tickets backfill to Master.
DEFAULT_STRATEGY_ID = "master_portfolio"


class OrderTicket(Base):
    __tablename__ = "order_ticket"
    # B057 F004 — per-mode ticket/journal listing.
    __table_args__ = (
        Index("ix_order_ticket_strategy_date", "strategy_id", "ticket_date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_date: Mapped[date] = mapped_column(Date, nullable=False)
    # B057 F004 — which strategy mode this ticket belongs to (default Master).
    strategy_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_STRATEGY_ID,
        server_default=DEFAULT_STRATEGY_ID,
    )
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_positions_id: Mapped[str] = mapped_column(String(64), nullable=False)
    markdown_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"OrderTicket(id={self.id!r}, strategy_id={self.strategy_id!r}, "
            f"status={self.status!r})"
        )
