"""B049 F001 — read the real on-disk data state into a snapshot manifest.

The Snapshots page's refresh used to stream a *synthetic* 5-stage animation
(fixed ``0.05s`` sleeps) and persist a constant ``quality_status="ok"``
placeholder row (milestone-C close-out residue). This module replaces the
synthetic data source with a real read of what the B045 data-refresh job
actually wrote: the unified prices + fundamentals CSVs. The snapshots refresh
streams the real read as progress and records a ``SnapshotMeta`` row whose
``manifest_path`` / ``quality_status`` reflect the real coverage instead of a
placeholder.

Pure file read — no ``trade`` import, no DB, no execution (§12.10.2). The
relpath constants mirror ``data_refresh/refresh.py`` but are kept local so the
snapshots request path stays off the data-fetch import chain (same separation
``data_refresh/window.py`` already keeps).
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_DATA_ROOT = "/var/lib/workbench/data"

# Mirrors data_refresh/refresh.py PRICES_RELPATH / FUNDAMENTALS_RELPATH; kept
# local so importing this module never pulls the data-fetch (loader) stack onto
# the request path.
PRICES_RELPATH = ("snapshots", "prices", "unified", "prices_daily.csv")
FUNDAMENTALS_RELPATH = ("snapshots", "fundamentals", "unified", "fundamentals.csv")


def data_root() -> Path:
    """Resolve the data root the same way the data-refresh CLI does."""

    return Path(os.environ.get("WORKBENCH_DATA_ROOT", DEFAULT_DATA_ROOT))


@dataclass(frozen=True, slots=True)
class CsvInventory:
    """Real coverage of one unified CSV the data-refresh job wrote."""

    path: Path
    present: bool
    symbols: int
    rows: int
    data_start: date | None
    data_end: date | None


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def read_inventory(path: Path, *, ticker_col: int = 1, date_col: int = 0) -> CsvInventory:
    """Read row count, distinct symbols and the date window from one unified CSV.

    An absent file yields an empty inventory (``present=False``) so the caller
    can grade it as degraded rather than raise — the page must still render a
    snapshot row describing the (missing) data state.
    """

    if not path.is_file():
        return CsvInventory(
            path=path, present=False, symbols=0, rows=0, data_start=None, data_end=None
        )
    symbols: set[str] = set()
    rows = 0
    earliest: date | None = None
    latest: date | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return CsvInventory(
                path=path, present=True, symbols=0, rows=0, data_start=None, data_end=None
            )
        for row in reader:
            if not row:
                continue
            rows += 1
            if len(row) > ticker_col and row[ticker_col].strip():
                symbols.add(row[ticker_col].strip())
            if len(row) > date_col:
                parsed = _parse_iso(row[date_col])
                if parsed is not None:
                    if earliest is None or parsed < earliest:
                        earliest = parsed
                    if latest is None or parsed > latest:
                        latest = parsed
    return CsvInventory(
        path=path,
        present=True,
        symbols=len(symbols),
        rows=rows,
        data_start=earliest,
        data_end=latest,
    )


def prices_inventory(root: Path) -> CsvInventory:
    return read_inventory(root.joinpath(*PRICES_RELPATH))


def fundamentals_inventory(root: Path) -> CsvInventory:
    return read_inventory(root.joinpath(*FUNDAMENTALS_RELPATH))


def grade_quality(prices: CsvInventory, fundamentals: CsvInventory) -> str:
    """Grade the snapshot from real coverage — never a constant placeholder.

    ``ok`` requires both unified CSVs to carry rows; a missing/empty prices CSV
    is the most severe (the Master universe has no priced history at all), a
    missing/empty fundamentals CSV degrades to a prices-only snapshot.
    """

    if not prices.present or prices.rows == 0:
        return "degraded:no-prices"
    if not fundamentals.present or fundamentals.rows == 0:
        return "degraded:no-fundamentals"
    return "ok"
