"""Fill journal upload + listing (B023 F004).

The workbench accepts post-execution fills either as a multipart CSV
or as JSON. CSV parsing uses the stdlib ``csv`` module plus three
short broker adapters (Schwab / IBKR / generic) — each adapter
normalises a broker-specific column header to the canonical
``FillRowIn`` shape before Pydantic validation. The acceptance pin
asks for ≤ 5 LOC of glue per broker; the adapters here are mostly
column-rename dicts.

Row-level errors return HTTP 400 with a list of
``{row, error, source_row}`` entries so the frontend can highlight
which CSV rows failed without re-uploading the whole file.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.repositories.fill_journal_entry import FillJournalEntryRepository
from workbench_api.db.repositories.order_ticket import OrderTicketRepository
from workbench_api.i18n import t
from workbench_api.schemas.fills import (
    FillRowError,
    FillRowIn,
    FillRowOut,
    FillsListResponse,
    FillSubmitRequest,
    FillSubmitResponse,
)

_logger = logging.getLogger("workbench.fills")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

# Each broker adapter is a column-name map: broker header → canonical
# key. ``parse_csv`` picks the right map by intersecting the CSV's
# header row with the keys of each map; the map with the largest
# overlap wins. ``side_map`` rewrites broker-specific side labels
# ("Bought" / "Sold") to the canonical "buy" / "sell". 5 LOC per
# broker is the F004 ergonomic ceiling.

_GENERIC_MAP: dict[str, str] = {
    "order_seq": "order_seq",
    "symbol": "symbol",
    "side": "side",
    "shares": "shares",
    "fill_price": "fill_price",
    "commission": "commission",
    "fees": "fees",
    "currency": "currency",
    "filled_at": "filled_at",
}
_SCHWAB_MAP: dict[str, str] = {
    "#": "order_seq",
    "Symbol": "symbol",
    "Action": "side",
    "Quantity": "shares",
    "Price": "fill_price",
    "Commission": "commission",
    "Fees & Taxes": "fees",
    "Date": "filled_at",
}
_IBKR_MAP: dict[str, str] = {
    "OrderID": "order_seq",
    "Symbol": "symbol",
    "Buy/Sell": "side",
    "Quantity": "shares",
    "TradePrice": "fill_price",
    "IBCommission": "commission",
    "Taxes": "fees",
    "CurrencyPrimary": "currency",
    "DateTime": "filled_at",
}
_SIDE_NORMALISE: dict[str, str] = {
    "buy": "buy",
    "bought": "buy",
    "b": "buy",
    "sell": "sell",
    "sold": "sell",
    "s": "sell",
    "sld": "sell",
}


def _detect_adapter(headers: list[str]) -> dict[str, str]:
    headers_set = set(headers)
    candidates = [
        ("generic", _GENERIC_MAP),
        ("schwab", _SCHWAB_MAP),
        ("ibkr", _IBKR_MAP),
    ]
    scored = [
        (name, mapping, len(set(mapping.keys()) & headers_set))
        for name, mapping in candidates
    ]
    scored.sort(key=lambda item: item[2], reverse=True)
    name, mapping, score = scored[0]
    if score < 4:
        # Heuristic: every supported broker shares at least 4 of the canonical
        # columns; if not even four overlap, the file is too far off-format.
        raise HTTPException(
            status_code=400,
            detail=t("csv.adapter_unknown", headers=str(headers)),
        )
    _logger.info("fills csv adapter chosen", extra={"event": "fills_csv_adapter", "adapter": name})
    return mapping


def _normalise_row(raw: dict[str, str], mapping: dict[str, str]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for broker_key, target_key in mapping.items():
        if broker_key not in raw:
            continue
        value = raw[broker_key]
        if value == "":
            continue
        if target_key == "side":
            canonical[target_key] = _SIDE_NORMALISE.get(value.strip().lower(), value)
        else:
            canonical[target_key] = value
    return canonical


def parse_csv(content: bytes | str) -> tuple[list[FillRowIn], list[FillRowError]]:
    """Parse a CSV body into ``(rows, errors)``.

    ``rows`` is the valid rows; ``errors`` is row-level validation
    failures with the original raw dict attached for UI highlighting.
    Headers drive adapter detection; row order is preserved.
    """

    text = content.decode("utf-8") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=400, detail=t("csv.missing_header_row")
        )
    mapping = _detect_adapter(list(reader.fieldnames))

    rows: list[FillRowIn] = []
    errors: list[FillRowError] = []
    for index, raw in enumerate(reader):
        canonical = _normalise_row(raw, mapping)
        try:
            rows.append(FillRowIn(**canonical))
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append(
                FillRowError(
                    row=index,
                    error=f"{'.'.join(str(p) for p in first['loc'])}: {first['msg']}",
                    source_row=dict(raw),
                )
            )
        except Exception as exc:  # defensive: bad numeric parses
            errors.append(
                FillRowError(row=index, error=str(exc), source_row=dict(raw))
            )
    return rows, errors


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _resolve_ticket(session: Session, ticket_id: str) -> OrderTicket:
    repo = OrderTicketRepository(session)
    ticket = repo.get_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=404, detail=t("ticket.not_found", ticket_id=ticket_id)
        )
    if ticket.status not in ("generated", "executed"):
        raise HTTPException(
            status_code=409,
            detail=t(
                "ticket.status_blocks_fills",
                ticket_id=ticket_id,
                status=ticket.status,
            ),
        )
    return ticket


def _row_is_unmatched(row: FillRowIn) -> bool:
    """A row counts as 'unmatched' when the user did not map it back to a
    specific ticket line (``order_seq is None``). The ticket itself does
    not currently persist a queryable list of lines (the Markdown is the
    artifact, see F003), so the workbench trusts the order_seq the user
    typed: present = mapped, missing = needs explicit confirmation via
    ``allow_unmatched=True``. F005 reconcile tightens this with the full
    target_positions context."""

    return row.order_seq is None


def submit_fills(
    session: Session,
    body: FillSubmitRequest,
    *,
    source: str = "manual_entry",
    now: datetime | None = None,
) -> FillSubmitResponse:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    _resolve_ticket(session, body.ticket_id)

    unmatched_rows: list[FillRowIn] = []
    matched_rows: list[FillRowIn] = []
    for row in body.fills:
        if _row_is_unmatched(row):
            unmatched_rows.append(row)
        else:
            matched_rows.append(row)

    if unmatched_rows and not body.allow_unmatched:
        unmatched_errors = [
            FillRowError(
                row=i,
                error=(
                    "fill does not match a ticket line "
                    "(order_seq unknown to this ticket); re-submit with "
                    "allow_unmatched=true to accept anyway"
                ),
                source_row=row.model_dump(mode="json"),
            )
            for i, row in enumerate(unmatched_rows)
        ]
        raise HTTPException(
            status_code=400,
            detail={"errors": [e.model_dump() for e in unmatched_errors]},
        )

    repo = FillJournalEntryRepository(session)
    inserted: list[FillRowOut] = []
    insert_plan: list[tuple[FillRowIn, bool]] = [
        *((row, True) for row in matched_rows),
        *((row, False) for row in unmatched_rows),
    ]
    for row, is_matched in insert_plan:
        fill_id = f"fill-{uuid.uuid4().hex[:12]}"
        orm_row = FillJournalEntry(
            id=fill_id,
            ticket_id=body.ticket_id,
            order_seq=row.order_seq,
            symbol=row.symbol.upper(),
            side=row.side,
            shares=Decimal(str(row.shares)),
            fill_price=Decimal(str(row.fill_price)),
            commission=Decimal(str(row.commission)),
            fees=Decimal(str(row.fees)),
            currency=row.currency.upper(),
            filled_at=row.filled_at.replace(tzinfo=None) if row.filled_at.tzinfo else row.filled_at,
            source=source,
            notes=row.notes,
            created_at=now,
        )
        repo.upsert(orm_row)
        inserted.append(
            FillRowOut(
                id=fill_id,
                ticket_id=body.ticket_id,
                order_seq=row.order_seq,
                symbol=orm_row.symbol,
                side=row.side,
                shares=float(orm_row.shares),
                fill_price=float(orm_row.fill_price),
                commission=float(orm_row.commission),
                fees=float(orm_row.fees),
                currency=orm_row.currency,
                filled_at=orm_row.filled_at,
                source=source,  # type: ignore[arg-type]
                notes=orm_row.notes,
                created_at=now,
                matched=is_matched,
            )
        )
    session.commit()
    return FillSubmitResponse(
        ticket_id=body.ticket_id,
        inserted=inserted,
        unmatched_count=len(unmatched_rows),
        accepted_under_allow_unmatched=bool(unmatched_rows and body.allow_unmatched),
    )


def submit_csv(
    session: Session,
    ticket_id: str,
    csv_bytes: bytes,
    *,
    allow_unmatched: bool = False,
    now: datetime | None = None,
) -> FillSubmitResponse:
    rows, errors = parse_csv(csv_bytes)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"errors": [e.model_dump() for e in errors]},
        )
    if not rows:
        raise HTTPException(
            status_code=400, detail=t("csv.empty_rows")
        )
    body = FillSubmitRequest(ticket_id=ticket_id, fills=rows, allow_unmatched=allow_unmatched)
    return submit_fills(session, body, source="csv_upload", now=now)


def list_fills(session: Session, ticket_id: str) -> FillsListResponse:
    repo = FillJournalEntryRepository(session)
    rows = repo.list_by_ticket(ticket_id)
    return FillsListResponse(
        ticket_id=ticket_id,
        items=[
            FillRowOut(
                id=row.id,
                ticket_id=row.ticket_id,
                order_seq=row.order_seq,
                symbol=row.symbol,
                side=row.side,  # type: ignore[arg-type]
                shares=float(row.shares),
                fill_price=float(row.fill_price),
                commission=float(row.commission),
                fees=float(row.fees),
                currency=row.currency,
                filled_at=row.filled_at,
                source=row.source,  # type: ignore[arg-type]
                notes=row.notes,
                created_at=row.created_at,
                matched=row.order_seq is not None,
            )
            for row in rows
        ],
    )
