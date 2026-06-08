"""B047-OPS2 F001 — compute the backtest data-coverage window from the CSV.

After the data-refresh job writes the unified daily prices CSV, this derives the
coverage window the request path exposes:

- ``data_start`` / ``data_end`` — the earliest / latest ``date`` in the CSV.
- ``first_usable_signal_date`` — the conservative floor a backtest may start
  from and still satisfy the sleeves' lookbacks.

**first_usable mechanism (generator decision):** a *documented conservative
constant* — ``data_start + FIRST_USABLE_LOOKBACK_DAYS`` — rather than importing
``trade`` to compute the exact first lookback-satisfied quarter-end. Rationale:

- The data-refresh job stays light (no heavy ``trade`` engine import, fewer
  failure surfaces) and the value is robust to engine internals changing.
- The momentum sleeve's ~9-month window is the binding lookback (risk_parity
  needs 120 trading days ≈ 6 months); ``FIRST_USABLE_LOOKBACK_DAYS`` = 305 days
  (~10 months) clears it with a buffer.
- Erring *later* is the safe direction: the frontend clamps the picker to
  ``min_usable_start = first_usable_signal_date`` and floors the default start
  there, so a conservative value can only prevent a marginal-edge range that
  might fail — never admit one. The worker's runtime drop-earliest retry remains
  the precise mechanism for the exact boundary.

Pure CSV read — no ``trade`` import, no DB.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# ~10 months past data_start: momentum's ~9-month window is binding; the buffer
# absorbs calendar-vs-trading-day slack so the floor is request-path-safe.
FIRST_USABLE_LOOKBACK_DAYS = 305


@dataclass(frozen=True, slots=True)
class DataWindow:
    data_start: date
    data_end: date
    first_usable_signal_date: date


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def compute_data_window(prices_path: Path) -> DataWindow | None:
    """Derive the coverage window from the unified prices CSV.

    Returns ``None`` when the CSV is absent or has no parseable date rows (an
    empty refresh) so the caller skips the DB write gracefully."""

    if not prices_path.is_file():
        return None
    earliest: date | None = None
    latest: date | None = None
    with prices_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return None
        for row in reader:
            if not row:
                continue
            parsed = _parse_iso(row[0])
            if parsed is None:
                continue
            if earliest is None or parsed < earliest:
                earliest = parsed
            if latest is None or parsed > latest:
                latest = parsed
    if earliest is None or latest is None:
        return None
    first_usable = earliest + timedelta(days=FIRST_USABLE_LOOKBACK_DAYS)
    # Never report a floor past the data end (a too-short refresh) — clamp so the
    # window stays internally consistent (start ≤ first_usable ≤ end).
    if first_usable > latest:
        first_usable = latest
    return DataWindow(
        data_start=earliest,
        data_end=latest,
        first_usable_signal_date=first_usable,
    )
