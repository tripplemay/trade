"""Schemas for ``/api/execution/*`` endpoints (B023 F002+).

F002 ships the read-only position-diff view + the account-snapshot
read/write surface. Later features (F003 tickets, F004 fills, F005
reconcile) add to this module without touching the F002 shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PositionEntry(BaseModel):
    """One entry in an AccountSnapshot's ``positions`` list.

    ``sleeve`` (B048 F002) is the optional strategy-registry sleeve the
    holding belongs to. B037 added the read side (Home / risk per-sleeve
    grouping reads ``positions[].sleeve``), but the execution write paths
    dropped the tag — so it could never round-trip. It is optional + the
    reader treats a missing / null tag as ``unclassified`` (home.py
    semantics), keeping the schema tolerant of pre-B048 snapshots.
    """

    symbol: str = Field(min_length=1, max_length=16)
    shares: float = Field(ge=0.0)
    avg_cost: float = Field(ge=0.0)
    sleeve: str | None = Field(
        default=None,
        max_length=64,
        description="Strategy-registry sleeve; null/missing → unclassified.",
    )


class AccountSnapshotPayload(BaseModel):
    """Wire shape for an ``account_snapshot`` row.

    ``id`` and ``snapshot_at`` are server-assigned (the bootstrap or PUT
    handler writes them); clients can leave them ``None`` when posting.
    """

    id: str | None = None
    snapshot_at: datetime | None = None
    cash: float = Field(ge=0.0)
    base_currency: str = Field(min_length=2, max_length=8)
    positions: list[PositionEntry] = Field(default_factory=list)
    source: Literal["bootstrap", "ui_edit", "fill_reconcile"] = "ui_edit"


class AccountUpdateRequest(BaseModel):
    """PUT /api/execution/account body.

    The handler inserts a fresh ``account_snapshot`` row with
    ``source=ui_edit``; the request itself omits ``id`` / ``snapshot_at``
    so the wire format matches what the React form posts.

    ``cash`` deliberately omits the ``ge=0.0`` constraint that lives on
    ``AccountSnapshotPayload``: the route handler enforces ``cash >= 0``
    manually so the rejection can flow through the locale-aware
    ``HTTPException`` path (B024 F006 fix). Pydantic's default 422 is
    not user-translatable.
    """

    cash: float
    base_currency: str = Field(min_length=2, max_length=8)
    positions: list[PositionEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_symbols(self) -> AccountUpdateRequest:
        seen: set[str] = set()
        for p in self.positions:
            sym = p.symbol.upper()
            if sym in seen:
                raise ValueError(f"duplicate symbol in positions: {sym}")
            seen.add(sym)
        return self


class PositionDiffEntry(BaseModel):
    """One row in the position-diff table.

    ``delta_*`` are signed so a positive value means "buy" and a negative
    value means "sell". Reference price is the per-symbol ``avg_cost``
    from the latest snapshot — workbench is research-only and does not
    fetch live market data; F002 uses the cost basis as a placeholder
    price reference. When the symbol has no current price reference
    (target-only symbol with no prior position), ``reference_price`` is
    ``None`` and the row is mirrored into ``unmatched`` so the frontend
    can flag it.
    """

    symbol: str
    current_shares: float
    target_shares: float
    delta_shares: float
    current_weight: float
    target_weight: float
    delta_weight: float
    delta_dollar: float
    reference_price: float | None
    reason: str | None = None


class PositionDiffResponse(BaseModel):
    """GET /api/execution/position-diff payload."""

    as_of_date: str
    total_equity: float
    current: AccountSnapshotPayload | None = Field(
        default=None,
        description="Latest AccountSnapshot, or None if no snapshot is on file.",
    )
    target: list[PositionEntry] = Field(
        default_factory=list,
        description=(
            "Snapshot-equivalent shape for the target portfolio (shares "
            "computed from target_weight × total_equity ÷ reference_price)."
        ),
    )
    diff: list[PositionDiffEntry] = Field(default_factory=list)
    unmatched: list[PositionDiffEntry] = Field(
        default_factory=list,
        description=(
            "Target rows with no current price reference (target-only "
            "symbols whose share calculation falls back to the cash basis)."
        ),
    )
