"""Schemas for ``/api/execution/reconcile/{ticket_id}`` + journal-history
+ slippage-analytics (B023 F005).

Slippage is reported in basis points (1 bps = 0.01%). Sign convention:
positive = unfavorable for the user (paid more on a buy, received less
on a sell); negative = favorable. ``per_side_bps`` lets the
journal-history detail break the aggregate into buy/sell halves.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FillSlippage(BaseModel):
    fill_id: str
    symbol: str
    name: str | None = None  # B079 — display name; null → frontend shows raw code
    side: Literal["buy", "sell"]
    shares: float
    fill_price: float
    reference_price: float | None
    slippage_bps: float | None = Field(
        default=None,
        description=(
            "Signed basis-points slippage vs reference_price. None when the "
            "reference price could not be sourced from the ticket's snapshot."
        ),
    )


class SlippageSummary(BaseModel):
    """Per-ticket aggregate used by both reconcile and journal-history."""

    ticket_id: str
    fill_count: int
    avg_bps: float | None = Field(
        default=None,
        description="Equally-weighted average bps across fills with a reference price.",
    )
    total_dollar: float = Field(
        default=0.0,
        description="Sum of signed dollar slippage = sum(slippage_bps/10000 × fill_dollar).",
    )


class ReconcileResponse(BaseModel):
    snapshot_id: str
    ticket_id: str
    slippage_summary: SlippageSummary
    fill_slippages: list[FillSlippage]
    unmatched_lines: list[str] = Field(
        default_factory=list,
        description=(
            "Symbols present in the ticket diff but never filled. Surfaced "
            "so the journal-history viewer can flag missing executions."
        ),
    )
    already_reconciled: bool = Field(
        default=False,
        description=(
            "True when the ticket was already in `executed` status; the "
            "response then describes the existing post-reconcile snapshot "
            "without inserting a duplicate (idempotency guarantee per "
            "F005 acceptance #2)."
        ),
    )


class JournalHistoryItem(BaseModel):
    ticket_id: str
    ticket_date: _date
    status: Literal["generated", "executed", "voided"]
    snapshot_id: str
    markdown_path: str
    created_at: datetime
    executed_at: datetime | None = None
    fill_count: int
    avg_bps: float | None = None
    total_dollar: float = 0.0


class JournalHistoryResponse(BaseModel):
    since: str | None = None
    items: list[JournalHistoryItem]


class SlippageTrendPoint(BaseModel):
    month: str = Field(description="ISO year-month, e.g. '2026-04'.")
    avg_bps: float
    fill_count: int


class SlippageOutlier(BaseModel):
    ticket_id: str
    ticket_date: _date
    avg_bps: float


class SlippageAnalyticsResponse(BaseModel):
    window: Literal["3m", "6m", "1y"]
    rolling_avg_bps: float | None
    outliers: list[SlippageOutlier]
    trend: list[SlippageTrendPoint]
