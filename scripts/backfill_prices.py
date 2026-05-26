#!/usr/bin/env python
"""B028 F002 — historical price backfill driver (Tiingo → vendor + unified).

One-shot script. For each ticker in the supplied universe:

1. Fetch daily OHLCV bars from Tiingo via
   :class:`workbench_api.data.tiingo_loader.TiingoSnapshotLoader`. The
   B027 cost guard auto-activates so the monthly $10 cap stays
   enforced.
2. Write a vendor-raw CSV to
   ``data/snapshots/prices/tiingo/{ticker}-{from}-{to}.csv``.
3. Append into the unified CSV
   ``data/snapshots/prices/unified/prices_daily.csv``, sort + dedupe
   by ``(ticker, date)`` and atomic-write so a Ctrl-C in the middle
   never leaves a partial file.

Usage::

    python scripts/backfill_prices.py \\
        --from 2014-01-01 --to 2026-05-26 \\
        --universe master

    python scripts/backfill_prices.py \\
        --from 2024-01-01 --to 2024-06-30 \\
        --tickers SPY,QQQ

Exit codes:

* ``0`` — every ticker fetched + persisted.
* ``1`` — at least one ticker failed (vendor error, schema violation,
  cap exceeded). Existing on-disk data is preserved; the unified
  file is not rewritten unless every fetch succeeded.

The script is **not** in CI (fixture-first offline invariant). Run
manually after a Tiingo API key is in scope, then commit the README
update (the produced CSVs are git-ignored — see
``data/snapshots/.gitignore``).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path

# Resolve repo root + workbench backend on the import path so this script
# can run from the repo root without an editable install.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_PKG = REPO_ROOT / "workbench" / "backend"
if str(BACKEND_PKG) not in sys.path:
    sys.path.insert(0, str(BACKEND_PKG))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from universe_master import master_universe  # noqa: E402
from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader  # noqa: E402
from workbench_api.data.tiingo_loader import TiingoSnapshotLoader  # noqa: E402

# Column order must match the B025 us_quality_momentum fixture so the
# unified file is a drop-in once B030 flips the loader read path.
UNIFIED_COLUMNS: tuple[str, ...] = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)


def _bar_to_row(bar: PriceBar) -> dict[str, str]:
    return {
        "date": bar.bar_date.isoformat(),
        "ticker": bar.ticker,
        "open": f"{bar.open:.6f}",
        "high": f"{bar.high:.6f}",
        "low": f"{bar.low:.6f}",
        "close": f"{bar.close:.6f}",
        "adj_close": f"{bar.adj_close:.6f}",
        "volume": str(int(bar.volume)),
    }


def validate_bars(ticker: str, bars: list[PriceBar]) -> None:
    """Sanity-check the vendor response before persisting.

    Catches the obvious schema violations that would otherwise
    silently corrupt the unified file: negative OHLCV, mismatched
    ticker, empty result. The cost-guard 0.5 % cross-check belongs
    to ``scripts/validate_snapshot.py``, not here.
    """

    if not bars:
        raise ValueError(f"{ticker}: vendor returned empty bar list")
    for bar in bars:
        if bar.ticker != ticker:
            raise ValueError(
                f"{ticker}: bar ticker mismatch ({bar.ticker!r}) on {bar.bar_date}"
            )
        if any(
            v < 0 for v in (bar.open, bar.high, bar.low, bar.close, bar.adj_close)
        ):
            raise ValueError(
                f"{ticker}: negative OHLC on {bar.bar_date}: "
                f"o={bar.open} h={bar.high} l={bar.low} c={bar.close} "
                f"adj={bar.adj_close}"
            )
        if bar.volume < 0:
            raise ValueError(
                f"{ticker}: negative volume on {bar.bar_date}: {bar.volume}"
            )


def write_vendor_csv(ticker: str, bars: list[PriceBar], destination: Path) -> None:
    """Write the vendor-raw CSV for ``ticker`` atomically.

    ``tempfile.NamedTemporaryFile`` + ``os.replace`` so a kill in the
    middle of a write leaves the previous good file in place. Caller
    is expected to ``mkdir -p`` the parent directory.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False, newline=""
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=UNIFIED_COLUMNS)
        writer.writeheader()
        for bar in bars:
            writer.writerow(_bar_to_row(bar))
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, destination)


def merge_into_unified(
    new_rows: Iterable[dict[str, str]],
    unified_path: Path,
) -> int:
    """Sort + dedupe + atomic-write the unified CSV.

    Existing rows are loaded first so a partial backfill on a fresh
    ticker doesn't clobber the rows already on disk for the rest of
    the universe. Dedup key is ``(ticker, date)`` — re-running the
    same range collapses to a single set of rows.

    Returns the row count after the merge.
    """

    unified_path.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[tuple[str, str], dict[str, str]] = {}
    if unified_path.exists():
        with unified_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                seen[(row["ticker"], row["date"])] = row
    for row in new_rows:
        seen[(row["ticker"], row["date"])] = row
    ordered = sorted(seen.values(), key=lambda r: (r["ticker"], r["date"]))
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=unified_path.parent, delete=False, newline=""
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=UNIFIED_COLUMNS)
        writer.writeheader()
        writer.writerows(ordered)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, unified_path)
    return len(ordered)


def backfill(
    tickers: list[str],
    from_date: date,
    to_date: date,
    loader: SnapshotLoader,
    *,
    snapshots_root: Path,
) -> tuple[int, list[str]]:
    """Run the per-ticker fetch loop. Returns ``(row_count, failures)``."""

    vendor_dir = snapshots_root / "prices" / "tiingo"
    unified_path = snapshots_root / "prices" / "unified" / "prices_daily.csv"

    new_rows: list[dict[str, str]] = []
    failures: list[str] = []
    for ticker in tickers:
        try:
            bars = loader.fetch_daily_bars(ticker, from_date, to_date)
            validate_bars(ticker, bars)
        except Exception as exc:
            failures.append(f"{ticker}: {type(exc).__name__}: {exc}")
            print(
                f"  ✗ {ticker} failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        vendor_path = (
            vendor_dir / f"{ticker}-{from_date.isoformat()}-{to_date.isoformat()}.csv"
        )
        write_vendor_csv(ticker, bars, vendor_path)
        ticker_rows = [_bar_to_row(b) for b in bars]
        new_rows.extend(ticker_rows)
        print(f"  ✓ {ticker} fetched {len(bars)} bars → {vendor_path.name}")
    if failures:
        print(
            f"refusing to rewrite unified file — {len(failures)} ticker(s) "
            "failed; vendor partial files retained on disk for diagnosis",
            file=sys.stderr,
        )
        # Still return the row count of the existing unified file (if any).
        existing = 0
        if unified_path.exists():
            with unified_path.open(encoding="utf-8") as fh:
                existing = sum(1 for _ in fh) - 1  # subtract header
        return existing, failures
    total = merge_into_unified(new_rows, unified_path)
    return total, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=date(2014, 1, 1),
        help="Earliest date to fetch in ISO-8601 (default: 2014-01-01)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=date.today(),
        help="Latest date to fetch in ISO-8601 (default: today)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tickers",
        help="Comma-separated list of tickers (overrides --universe)",
    )
    group.add_argument(
        "--universe",
        default="master",
        choices=["master"],
        help="Named universe (default: master)",
    )
    parser.add_argument(
        "--snapshots-root",
        type=Path,
        default=REPO_ROOT / "data" / "snapshots",
        help="Where to write the vendor + unified files (default: data/snapshots)",
    )
    args = parser.parse_args(argv)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = master_universe()

    print(
        f"Backfilling {len(tickers)} ticker(s) from {args.from_date.isoformat()} "
        f"to {args.to_date.isoformat()} (Tiingo)..."
    )
    loader = TiingoSnapshotLoader()
    row_count, failures = backfill(
        tickers,
        args.from_date,
        args.to_date,
        loader,
        snapshots_root=args.snapshots_root,
    )
    print(f"Unified prices_daily.csv now holds {row_count} rows")
    if failures:
        print(f"\n{len(failures)} ticker(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
