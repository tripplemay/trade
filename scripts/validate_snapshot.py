#!/usr/bin/env python
"""B028 F001 — cross-check Tiingo snapshot vs yfinance on a random sample.

One-shot validation: assert Tiingo unified data matches yfinance within
0.5 % on a random sample of tickers × dates. Not part of CI (the CI
pipeline is offline-fixture-only); run manually after
``scripts/backfill_prices.py`` completes to confirm the vendor's
prices match an independent source.

Usage::

    python scripts/validate_snapshot.py \\
        --tickers SPY,QQQ,IEF,GLD,TLT \\
        --sample-dates 5

Exit codes:

* ``0`` — every sampled ``(ticker, date)`` pair matched within
  ``--tolerance`` (default 0.005 = 0.5 %).
* ``1`` — at least one discrepancy exceeded ``--tolerance``; a
  detailed table is printed to stderr for review.

The discrepancy threshold is intentionally generous. Tiingo applies
its own split/dividend adjustment policy; yfinance derives a separate
``Adj Close`` from Yahoo's history; small rounding gaps (~0.01 %) are
expected. The 0.5 % floor catches real corporate-action mis-handling
without flagging benign rounding noise.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

# Resolve the workbench backend on the import path so this script can
# run from the repo root without an editable install.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_PKG = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "workbench", "backend"))
if BACKEND_PKG not in sys.path:
    sys.path.insert(0, BACKEND_PKG)

from workbench_api.data.snapshot_loader import SnapshotLoader  # noqa: E402
from workbench_api.data.tiingo_loader import TiingoSnapshotLoader  # noqa: E402
from workbench_api.data.yfinance_loader import YFinanceSnapshotLoader  # noqa: E402


@dataclass(frozen=True, slots=True)
class Discrepancy:
    """One sampled comparison that exceeded the tolerance."""

    ticker: str
    sample_date: date
    tiingo_close: float
    yfinance_close: float
    relative_error: float


def sample_dates(
    earliest: date,
    latest: date,
    count: int,
    rng: random.Random,
) -> list[date]:
    """Pick ``count`` random business days inside ``[earliest, latest]``.

    The sample is not stratified — we trust the comparison logic to
    surface a problem regardless of which day we land on. Weekends
    won't have bars in either source, so they fail with a clear
    ValueError that exits the run with status 1 (caller can re-roll).
    """

    span_days = (latest - earliest).days
    if span_days <= 0:
        raise ValueError(
            f"sample_dates: latest {latest} must be after earliest {earliest}"
        )
    candidates: list[date] = []
    while len(candidates) < count:
        offset = rng.randrange(0, span_days + 1)
        day = earliest + timedelta(days=offset)
        # Drop weekends so we don't sample non-trading days; the
        # vendors return empty for those and the loader raises.
        if day.weekday() < 5 and day not in candidates:
            candidates.append(day)
    return sorted(candidates)


def cross_check(
    tickers: Iterable[str],
    dates: Iterable[date],
    tiingo: SnapshotLoader,
    yf: SnapshotLoader,
    tolerance: float,
) -> tuple[list[Discrepancy], int]:
    """Run every (ticker, date) pair through both vendors and compare.

    Returns ``(discrepancies, total_comparisons)``. A blocked sample
    (vendor raised before returning a bar) counts as a discrepancy
    with ``relative_error = float('inf')`` so the caller still sees
    it in the summary.
    """

    discrepancies: list[Discrepancy] = []
    total = 0
    for ticker in tickers:
        for sample_date in dates:
            total += 1
            try:
                tiingo_bars = tiingo.fetch_daily_bars(ticker, sample_date, sample_date)
                yf_bars = yf.fetch_daily_bars(ticker, sample_date, sample_date)
            except Exception as exc:
                discrepancies.append(
                    Discrepancy(
                        ticker=ticker,
                        sample_date=sample_date,
                        tiingo_close=float("nan"),
                        yfinance_close=float("nan"),
                        relative_error=float("inf"),
                    )
                )
                print(
                    f"  fetch failed for {ticker} {sample_date}: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                continue
            if not tiingo_bars or not yf_bars:
                discrepancies.append(
                    Discrepancy(
                        ticker=ticker,
                        sample_date=sample_date,
                        tiingo_close=float("nan"),
                        yfinance_close=float("nan"),
                        relative_error=float("inf"),
                    )
                )
                continue
            t_close = tiingo_bars[0].adj_close
            y_close = yf_bars[0].adj_close
            rel = abs(t_close - y_close) / y_close if y_close else float("inf")
            if rel >= tolerance:
                discrepancies.append(
                    Discrepancy(
                        ticker=ticker,
                        sample_date=sample_date,
                        tiingo_close=t_close,
                        yfinance_close=y_close,
                        relative_error=rel,
                    )
                )
    return discrepancies, total


def render_summary(
    total: int,
    discrepancies: list[Discrepancy],
    tolerance: float,
) -> str:
    """Format the cross-check result as a human-readable string."""

    passed = total - len(discrepancies)
    pct = (passed / total * 100) if total else 0.0
    header = (
        f"Cross-check summary: {passed}/{total} samples within "
        f"{tolerance:.2%} tolerance ({pct:.1f}%)"
    )
    if not discrepancies:
        return header + "\nRESULT: PASS"
    lines = [header, "", "Discrepancies (sorted by relative error desc):"]
    lines.append(
        f"  {'ticker':<8} {'date':<10} {'tiingo_adj':>12} {'yf_adj':>12} {'rel_err':>10}"
    )
    for d in sorted(discrepancies, key=lambda x: -x.relative_error):
        if d.relative_error == float("inf"):
            err_repr = "fetch_fail"
        else:
            err_repr = f"{d.relative_error:.4%}"
        lines.append(
            f"  {d.ticker:<8} {d.sample_date.isoformat():<10} "
            f"{d.tiingo_close:>12.4f} {d.yfinance_close:>12.4f} {err_repr:>10}"
        )
    lines.append("")
    lines.append("RESULT: FAIL")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--tickers",
        default="SPY,QQQ,IEF,GLD,TLT",
        help="Comma-separated tickers to sample (default: %(default)s)",
    )
    parser.add_argument(
        "--sample-dates",
        type=int,
        default=5,
        help="Number of random trading-day dates per ticker (default: 5)",
    )
    parser.add_argument(
        "--earliest",
        type=date.fromisoformat,
        default=date(2018, 1, 2),
        help="Earliest sample date in ISO-8601 (default: 2018-01-02)",
    )
    parser.add_argument(
        "--latest",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=7),
        help="Latest sample date in ISO-8601 (default: today - 7 days)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.005,
        help="Relative error threshold for PASS (default: 0.005 = 0.5%%)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible samples (default: time-based)",
    )
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    dates = sample_dates(args.earliest, args.latest, args.sample_dates, rng)

    print(f"Tickers: {tickers}")
    print(f"Sample dates: {[d.isoformat() for d in dates]}")
    print(f"Tolerance: {args.tolerance:.2%}")
    print()

    tiingo = TiingoSnapshotLoader()
    yf = YFinanceSnapshotLoader()
    discrepancies, total = cross_check(tickers, dates, tiingo, yf, args.tolerance)

    summary = render_summary(total, discrepancies, args.tolerance)
    print(summary)
    return 0 if not discrepancies else 1


if __name__ == "__main__":
    raise SystemExit(main())
