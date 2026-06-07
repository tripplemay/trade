"""B048 F001 — price-history backfill core.

Reads the B045 unified prices CSV (the deep daily history the data-refresh
job already materialises for the Master universe) and writes each
``(ticker, date, close)`` into the ``price_history`` table, idempotently by
``(symbol, obs_date)``.

The CSV path + column schema mirror ``data_refresh.refresh`` exactly
(``date,ticker,open,high,low,close,adj_close,volume``); the ``close``
column is stored verbatim so ``price_history.close`` carries the same
valuation semantics the B037 ``price_snapshot`` / B046 mark-to-market
arithmetic already use.

Boundary (r): this is a job, not a request handler — it reads a CSV and
writes the DB (§12.10). It never fetches from the network and never
imports a trade-execution surface.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.repositories.price_history import PriceHistoryRepository

logger = logging.getLogger(__name__)

# Mirror the B045 unified prices CSV location + the columns the backfill
# reads. Kept local (not imported from data_refresh) so the backfill's
# contract is explicit and independent of the refresh job's internals.
PRICES_RELPATH: tuple[str, ...] = ("snapshots", "prices", "unified", "prices_daily.csv")
DATE_COLUMN = "date"
TICKER_COLUMN = "ticker"
CLOSE_COLUMN = "close"

# Provenance recorded on every backfilled row.
BACKFILL_SOURCE = "b045_unified_csv"

# Commit every N rows so a long backfill doesn't hold one giant transaction
# (and a failure midway keeps the rows already written).
_COMMIT_EVERY = 500


@dataclass(frozen=True, slots=True)
class BackfillSummary:
    """Aggregate result of one backfill run."""

    rows_read: int
    saved: int
    skipped_existing: int
    skipped_malformed: int
    symbols: int
    csv_path: str


def _parse_row(row: dict[str, str]) -> tuple[str, date, float] | None:
    """Project one CSV row to ``(symbol, obs_date, close)`` or ``None``
    when a required field is missing / unparseable (counted as malformed,
    never fabricated)."""

    symbol_raw = (row.get(TICKER_COLUMN) or "").strip().upper()
    date_raw = (row.get(DATE_COLUMN) or "").strip()
    close_raw = (row.get(CLOSE_COLUMN) or "").strip()
    if not symbol_raw or not date_raw or not close_raw:
        return None
    try:
        obs_date = date.fromisoformat(date_raw)
        close = float(close_raw)
    except ValueError:
        return None
    return symbol_raw, obs_date, close


def run_backfill(
    *,
    session: Session,
    data_root: Path,
    fetched_at: datetime | None = None,
) -> BackfillSummary:
    """Materialise the deep price history from the unified CSV under
    ``data_root`` into ``price_history``.

    Idempotent: a re-run skips ``(symbol, obs_date)`` rows already stored.
    Malformed rows are counted + logged, never written. Returns
    aggregate counts.
    """

    csv_path = data_root.joinpath(*PRICES_RELPATH)
    stamp = fetched_at or datetime.now(UTC)
    repo = PriceHistoryRepository(session)

    rows_read = 0
    saved = 0
    skipped_existing = 0
    skipped_malformed = 0
    symbols: set[str] = set()

    if not csv_path.is_file():
        logger.warning("price_history_backfill_no_csv", extra={"csv_path": str(csv_path)})
        return BackfillSummary(
            rows_read=0,
            saved=0,
            skipped_existing=0,
            skipped_malformed=0,
            symbols=0,
            csv_path=str(csv_path),
        )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        pending = 0
        for raw in reader:
            rows_read += 1
            parsed = _parse_row(raw)
            if parsed is None:
                skipped_malformed += 1
                continue
            symbol, obs_date, close = parsed
            symbols.add(symbol)
            row = repo.save_if_new(
                symbol=symbol,
                obs_date=obs_date,
                close=close,
                source=BACKFILL_SOURCE,
                fetched_at=stamp,
            )
            if row is None:
                skipped_existing += 1
            else:
                saved += 1
                pending += 1
            if pending >= _COMMIT_EVERY:
                session.commit()
                pending = 0
        session.commit()

    summary = BackfillSummary(
        rows_read=rows_read,
        saved=saved,
        skipped_existing=skipped_existing,
        skipped_malformed=skipped_malformed,
        symbols=len(symbols),
        csv_path=str(csv_path),
    )
    logger.info(
        "price_history_backfill_done",
        extra={
            "rows_read": rows_read,
            "saved": saved,
            "skipped_existing": skipped_existing,
            "skipped_malformed": skipped_malformed,
            "symbols": len(symbols),
        },
    )
    return summary
