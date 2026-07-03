"""Schemas for ``/api/execution/fills`` (B023 F004).

The wire shape is intentionally narrow: the route accepts either a
multipart CSV file OR a JSON ``FillSubmitRequest`` carrying the same
per-row fields. Each row is validated independently so the frontend
can render row-level errors without disrupting the rest of the
upload (acceptance pin: 400 with ``{row: N, error: '...'}``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FillRowIn(BaseModel):
    """One incoming fill — common shape regardless of CSV or JSON entry."""

    order_seq: int | None = Field(
        default=None,
        description=(
            "1-indexed row from the ticket Markdown. Null means the user did "
            "not map this fill back to a specific ticket line."
        ),
    )
    symbol: str = Field(min_length=1, max_length=16)
    side: Literal["buy", "sell"]
    shares: float = Field(gt=0.0)
    fill_price: float = Field(gt=0.0)
    commission: float = Field(ge=0.0, default=0.0)
    fees: float = Field(ge=0.0, default=0.0)
    currency: str = Field(min_length=2, max_length=8, default="USD")
    filled_at: datetime
    notes: str | None = None


class FillSubmitRequest(BaseModel):
    """JSON body for POST /api/execution/fills."""

    ticket_id: str = Field(min_length=1)
    fills: list[FillRowIn] = Field(min_length=1)
    allow_unmatched: bool = Field(
        default=False,
        description=(
            "When false, fills whose order_seq is null AND whose (symbol, side) "
            "is not in the ticket are 400'd; when true, they are accepted with "
            "source='manual_entry'."
        ),
    )


class FillRowError(BaseModel):
    row: int = Field(ge=0, description="0-indexed row in the input (CSV or JSON list).")
    error: str
    source_row: dict[str, Any] | None = Field(
        default=None,
        description="The original row (raw CSV fields or JSON dict) for the frontend to highlight.",
    )


class FillRowOut(BaseModel):
    """A persisted ``fill_journal_entry`` row in wire form."""

    id: str
    ticket_id: str
    order_seq: int | None = None
    symbol: str
    name: str | None = None  # B079 — display name; null → frontend shows raw code
    side: Literal["buy", "sell"]
    shares: float
    fill_price: float
    commission: float
    fees: float
    currency: str
    filled_at: datetime
    source: Literal["csv_upload", "manual_entry"]
    notes: str | None = None
    created_at: datetime
    matched: bool = Field(
        description=(
            "Whether this fill matched a ticket line at insert time. False = "
            "the row was accepted under allow_unmatched=true."
        ),
    )


class FillSubmitResponse(BaseModel):
    """Successful POST response: ``inserted`` is the new rows, ``errors``
    is empty (any error in any row aborts the insert)."""

    ticket_id: str
    inserted: list[FillRowOut]
    unmatched_count: int = 0
    accepted_under_allow_unmatched: bool = False


class FillsListResponse(BaseModel):
    ticket_id: str
    items: list[FillRowOut]
