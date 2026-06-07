"""B048 F001 — price-history backfill (unified CSV → price_history).

Drives ``run_backfill`` against a fake unified prices CSV written into a
tmp data-root (no network, no real data file). Pins: correct rows land in
the table with the backfill source, idempotent re-run skips existing rows,
malformed rows are counted but never written, and a missing CSV degrades
to an empty summary rather than crashing.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_history import PriceHistoryRepository
from workbench_api.price_history.backfill import (
    BACKFILL_SOURCE,
    PRICES_RELPATH,
    run_backfill,
)

_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def _write_csv(data_root: Path, rows: list[list[object]]) -> Path:
    csv_path = data_root.joinpath(*PRICES_RELPATH)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        writer.writerows(rows)
    return csv_path


def test_backfill_writes_rows_with_source(initialised_db: str, tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            ["2026-06-02", "AAPL", 1, 1, 1, 190.0, 190.0, 100],
            ["2026-06-03", "AAPL", 1, 1, 1, 192.0, 192.0, 100],
            ["2026-06-03", "MSFT", 1, 1, 1, 410.0, 410.0, 100],
        ],
    )
    with Session(get_engine()) as session:
        summary = run_backfill(session=session, data_root=tmp_path)
        assert summary.rows_read == 3
        assert summary.saved == 3
        assert summary.skipped_existing == 0
        assert summary.skipped_malformed == 0
        assert summary.symbols == 2

        repo = PriceHistoryRepository(session)
        assert repo.count() == 3
        assert repo.close_on_or_before("AAPL", date(2026, 6, 3)) == 192.0
        row = repo.get_by_symbol_and_date("MSFT", date(2026, 6, 3))
        assert row is not None
        assert row.source == BACKFILL_SOURCE


def test_backfill_is_idempotent_on_rerun(initialised_db: str, tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            ["2026-06-02", "AAPL", 1, 1, 1, 190.0, 190.0, 100],
            ["2026-06-03", "AAPL", 1, 1, 1, 192.0, 192.0, 100],
        ],
    )
    with Session(get_engine()) as session:
        first = run_backfill(session=session, data_root=tmp_path)
        assert first.saved == 2
        second = run_backfill(session=session, data_root=tmp_path)
        assert second.rows_read == 2
        assert second.saved == 0
        assert second.skipped_existing == 2
        assert PriceHistoryRepository(session).count() == 2


def test_backfill_skips_malformed_rows(initialised_db: str, tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        [
            ["2026-06-02", "AAPL", 1, 1, 1, 190.0, 190.0, 100],  # good
            ["not-a-date", "AAPL", 1, 1, 1, 191.0, 191.0, 100],  # bad date
            ["2026-06-03", "AAPL", 1, 1, 1, "", "", 100],         # empty close
            ["2026-06-04", "", 1, 1, 1, 195.0, 195.0, 100],       # missing ticker
            ["2026-06-05", "AAPL", 1, 1, 1, "nan-ish-x", 0, 100],  # unparseable close
        ],
    )
    with Session(get_engine()) as session:
        summary = run_backfill(session=session, data_root=tmp_path)
        assert summary.rows_read == 5
        assert summary.saved == 1
        assert summary.skipped_malformed == 4
        assert PriceHistoryRepository(session).count() == 1


def test_backfill_missing_csv_returns_empty_summary(
    initialised_db: str, tmp_path: Path
) -> None:
    # No CSV written under tmp_path.
    with Session(get_engine()) as session:
        summary = run_backfill(session=session, data_root=tmp_path)
        assert summary.rows_read == 0
        assert summary.saved == 0
        assert summary.symbols == 0
        assert PriceHistoryRepository(session).count() == 0
