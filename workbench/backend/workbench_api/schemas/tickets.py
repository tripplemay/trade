"""Schemas for ``/api/execution/tickets/*`` (B023 F003).

The OrderTicket DB row (B023 F001) carries the canonical state; this
module ships the wire shapes the FastAPI handlers and the Next.js
frontend trade in. The rendered Markdown body travels alongside the
row so the ticket page can preview without a second round-trip.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TicketSummary(BaseModel):
    """One row in the ticket list (no rendered Markdown body)."""

    id: str
    ticket_date: date
    snapshot_id: str
    target_positions_id: str
    markdown_path: str
    status: Literal["generated", "executed", "voided"]
    created_at: datetime
    executed_at: datetime | None = None


class TicketDetail(TicketSummary):
    """A ticket summary + its rendered Markdown body."""

    markdown_body: str = Field(
        description="The Markdown checklist served from disk (or re-rendered if missing).",
    )
    disclaimer: str = Field(
        description=(
            "Always 'research-only; this is a manual review checklist, "
            "not a trading instruction'."
        ),
    )


class TicketListResponse(BaseModel):
    items: list[TicketSummary]
    total: int
    limit: int
    offset: int


class GenerateTicketRequest(BaseModel):
    """POST /api/execution/tickets body.

    Both fields optional: ``as_of_date`` defaults to today, and
    ``notes`` is reserved for the user-supplied free-form annotation
    surfaced in the Markdown header (F003 keeps it empty by default).
    """

    as_of_date: str | None = None
    notes: str | None = None


class GenerateTicketResponse(TicketDetail):
    """POST /api/execution/tickets response — same shape as a detail
    GET so the frontend can drop the response straight into its
    cached state without a follow-up fetch."""
