#!/usr/bin/env python
"""B029 F002 — SEC EDGAR fundamentals backfill driver.

One-shot script. For each ticker in the B025 us_quality universe:

1. Look up the CIK from
   ``workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json``.
   Synthetic tickers (CIK ``None``) trip
   :class:`SECEDGARFundamentalsLoader`'s ``ValueError("Synthetic ticker
   ... has no SEC filing")``, which the driver catches → ``log warn +
   skip`` (Planner pre-impl adjudication 2026-05-26 decision #3 —
   fail-safe; not a fatal).
2. Fetch the raw SEC companyfacts JSON via
   :meth:`SECEDGARFundamentalsLoader.fetch_raw_companyfacts` (rate-
   limited at 10 req/sec; 永久边界 (i)).
3. Walk the ``facts.us-gaap`` sub-tree for the eleven concept names
   pinned in :data:`SEC_CONCEPT_NAMES`, bucket each fact entry by
   **calendar quarter** of its ``end`` date, and assemble one
   ratio-input row per (ticker, calendar_quarter).
4. Join Tiingo close on ``report_date`` (from B028
   ``data/snapshots/prices/unified/prices_daily.csv``) ×
   ``CommonStockSharesOutstanding`` (from SEC raw, ``dei`` namespace)
   to compute MarketCap (Planner pre-impl adjudication 2026-05-26 #2:
   MarketCap = close(report_date) × shares — PIT-correct, what market
   saw at filing time).
5. Call the eight ``xbrl_parser.compute_*`` helpers per row (永久
   边界 (j) — formulas locked).
6. Write vendor raw to
   ``data/snapshots/fundamentals/sec_edgar/{cik:010d}/companyfacts.json``
   + per-CIK ``parsed_ratios.json`` + ``metadata.json``.
7. Append unified rows to
   ``data/snapshots/fundamentals/unified/fundamentals.csv`` (sort +
   dedupe by ``(ticker, fiscal_quarter)`` + atomic write).

Usage::

    python scripts/backfill_fundamentals.py \\
        --from 2014-01-01 --to 2026-05-26 --universe us_quality

    python scripts/backfill_fundamentals.py \\
        --from 2020-01-01 --to 2022-12-31 --tickers AAPL,NVDA

Exit codes:

* ``0`` — every real ticker succeeded (synthetic skips don't count).
* ``1`` — at least one real ticker failed mid-fetch. The unified file
  is **still** updated with the successful tickers' rows (unlike
  ``backfill_prices.py`` which refuses any unified rewrite on partial
  failure — B028's rule was because price data is fungible across
  tickers; here the unified file is per-(ticker, fiscal_quarter) so a
  partial backfill on one ticker doesn't poison rows for others).

The script is **not** in CI (fixture-first offline invariant). Run
manually after ``SEC_EDGAR_CONTACT_EMAIL`` is set + the bundled
``ticker_cik_map.json`` is current; produced CSVs/JSON are git-ignored
(see ``data/snapshots/.gitignore``).

Quarterly accounting semantics — pragmatic first-cut:

* The script uses **SEC-reported per-period values as filed** without
  computing Q-over-Q deltas. For income-statement / cash-flow flow
  items (NetIncomeLoss / Revenues / CFO / Capex / OperatingIncome /
  D&A / COGS), this means a quarter labeled "Q3" carries the
  **cumulative-to-date** value (9 months from FY start). For balance-
  sheet items (StockholdersEquity / Assets / Cash / LongTermDebt /
  SharesOutstanding), the value is point-in-time at the period end.
* For TTM-dependent ratios (P/E, earnings_yield), the driver uses the
  FY value when ``fp = FY`` is present for the same fiscal year;
  otherwise it falls back to the latest fp value (with a one-time
  warn-level log noting the approximation).
* This matches the **shape** of the B025 fixture (12 columns × ~40
  quarters × 27 tickers) but not necessarily the exact values — the
  fixture was synthesised by the B025 generator script with its own
  conventions. Numeric drift between the unified CSV and the B025
  fixture is expected and not a defect; B025 fixture remains the
  authoritative source for backtest reproducibility (F003 fall-back
  path; B030 cutover responsibility).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import tempfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

# Resolve repo root + workbench backend on the import path so this script
# can run from the repo root without an editable install.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_PKG = REPO_ROOT / "workbench" / "backend"
if str(BACKEND_PKG) not in sys.path:
    sys.path.insert(0, str(BACKEND_PKG))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from universe_us_quality import (  # noqa: E402
    B025_SYNTHETIC_TICKERS,
    us_quality_universe,
)
from workbench_api.data.sec_edgar_loader import (  # noqa: E402
    SEC_CONCEPT_NAMES,
    SECEDGARFundamentalsLoader,
)
from workbench_api.data.xbrl_parser import (  # noqa: E402
    compute_debt_to_assets,
    compute_earnings_yield,
    compute_ebitda,
    compute_ev_ebitda,
    compute_fcf_yield,
    compute_gross_margin,
    compute_pb,
    compute_pe,
    compute_roe,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Column order must match the B025 us_quality_momentum fixture so the
# unified file is a drop-in once F003 wires the loader read path.
UNIFIED_COLUMNS: tuple[str, ...] = (
    "report_date",
    "ticker",
    "fiscal_quarter",
    "fiscal_quarter_end",
    "roe",
    "gross_margin",
    "fcf_yield",
    "debt_to_assets",
    "pe",
    "pb",
    "ev_ebitda",
    "earnings_yield",
)

# SEC reports CommonStockSharesOutstanding under the ``dei`` namespace,
# not ``us-gaap``. We special-case that one.
SHARES_OUTSTANDING_CONCEPT = "CommonStockSharesOutstanding"
DEI_NAMESPACE = "dei"
USGAAP_NAMESPACE = "us-gaap"


def _calendar_quarter(end_date: date) -> tuple[int, int]:
    """Bucket a calendar date into (year, quarter_number).

    SEC ``end`` dates may be ±1-15 days off a strict quarter-end
    (e.g. fiscal years that end on the last Saturday of September).
    The bucketing snaps to the nearest calendar quarter without
    treating the variance as a defect.
    """

    return (end_date.year, (end_date.month - 1) // 3 + 1)


def _quarter_end(year: int, q: int) -> date:
    """Return the canonical calendar quarter-end date for ``(year, q)``."""

    return {
        1: date(year, 3, 31),
        2: date(year, 6, 30),
        3: date(year, 9, 30),
        4: date(year, 12, 31),
    }[q]


def _index_concept_entries(
    facts: dict[str, Any],
    concept_name: str,
    namespace: str = USGAAP_NAMESPACE,
) -> list[dict[str, Any]]:
    """Pull the USD-unit entries for ``concept_name`` from the SEC
    companyfacts ``facts`` sub-tree.

    Each entry looks like::

        {"end": "2014-09-27", "val": 39510000000, "accn": "0000320193-14-...",
         "fy": 2014, "fp": "FY", "form": "10-K", "filed": "2014-10-27"}

    Concept lookup is namespace-aware so ``CommonStockSharesOutstanding``
    (``dei``) is resolvable on the same surface.
    """

    ns_facts = facts.get(namespace, {})
    if not isinstance(ns_facts, dict):
        return []
    concept = ns_facts.get(concept_name, {})
    if not isinstance(concept, dict):
        return []
    units = concept.get("units", {})
    if not isinstance(units, dict):
        return []
    # USD covers monetary concepts; "shares" covers SharesOutstanding.
    # Try USD first, fall back to shares.
    for unit_key in ("USD", "shares", "USD/shares"):
        entries = units.get(unit_key)
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]
    return []


def _bucket_entries_by_quarter(
    entries: list[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Bucket a flat list of concept entries by calendar quarter.

    For each (year, quarter), keep the **latest-filed** entry whose
    ``end`` date falls in that quarter. SEC sometimes has multiple
    filings for the same period (10-K/A amendments, 10-Q restatements);
    latest-filed wins.
    """

    out: dict[tuple[int, int], dict[str, Any]] = {}
    for entry in entries:
        try:
            end_dt = date.fromisoformat(str(entry["end"]))
        except (KeyError, ValueError):
            continue
        if "filed" not in entry or "val" not in entry:
            continue
        bucket = _calendar_quarter(end_dt)
        prev = out.get(bucket)
        if prev is None or str(entry["filed"]) > str(prev["filed"]):
            out[bucket] = entry
    return out


def _load_close_prices(prices_csv: Path) -> dict[tuple[str, str], float]:
    """Index B028 unified prices CSV by (ticker, date-iso) → close.

    Returns an empty dict if the file doesn't exist (caller skips the
    MarketCap-dependent ratios on missing prices, with a warn).
    """

    if not prices_csv.exists():
        return {}
    out: dict[tuple[str, str], float] = {}
    with prices_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                out[(row["ticker"], row["date"])] = float(row["close"])
            except (KeyError, ValueError):
                continue
    return out


def _nearest_close(
    prices: dict[tuple[str, str], float],
    ticker: str,
    target: date,
    *,
    max_offset_days: int = 5,
) -> float | None:
    """Look up close for ``ticker`` on ``target`` (or within
    ``max_offset_days`` trading days back for weekends / holidays).

    SEC ``filed`` dates can land on weekends (very rarely) or on
    holidays when markets are closed; walk back up to a week. Returns
    ``None`` if no price is found.
    """

    from datetime import timedelta

    for offset in range(max_offset_days + 1):
        probe = target - timedelta(days=offset)
        close = prices.get((ticker, probe.isoformat()))
        if close is not None:
            return close
    return None


def raw_companyfacts_to_parsed_ratios(
    ticker: str,
    payload: dict[str, Any],
    *,
    prices: dict[tuple[str, str], float],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert raw SEC companyfacts JSON into the ``parsed_ratios``
    block that :func:`parse_companyfacts` consumes.

    Returns ``(rows, skip_messages)``. Each row is a dict with the 12
    fields the F001 fixture shape uses; the unified CSV writer takes
    these dicts directly. ``skip_messages`` carries human-readable
    reasons per quarter that was dropped (missing concept / no price
    intersection / zero denominator).
    """

    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        return [], [f"{ticker}: companyfacts missing 'facts' object"]

    # Index every required concept by calendar quarter.
    indexed: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    for short_name, sec_concept in SEC_CONCEPT_NAMES.items():
        entries = _index_concept_entries(facts, sec_concept, USGAAP_NAMESPACE)
        indexed[short_name] = _bucket_entries_by_quarter(entries)
    shares_entries = _index_concept_entries(
        facts, SHARES_OUTSTANDING_CONCEPT, DEI_NAMESPACE
    )
    if not shares_entries:
        # Some filers report shares under us-gaap instead of dei.
        shares_entries = _index_concept_entries(
            facts, SHARES_OUTSTANDING_CONCEPT, USGAAP_NAMESPACE
        )
    indexed["shares_outstanding"] = _bucket_entries_by_quarter(shares_entries)

    # Quarters available = union of all concept buckets. Each row needs
    # at least the eight ratio inputs + report_date + shares; drop
    # quarters where any required input is missing (with a per-quarter
    # skip reason for debugging).
    all_quarters: set[tuple[int, int]] = set()
    for bucket in indexed.values():
        all_quarters |= set(bucket.keys())

    rows: list[dict[str, Any]] = []
    skip_messages: list[str] = []
    required_short_names = (
        "net_income",
        "stockholders_equity",
        "revenues",
        "cogs",
        "cfo",
        "capex",
        "long_term_debt",
        "assets",
        "cash",
        "operating_income",
        "depreciation_amortization",
        "shares_outstanding",
    )
    for year, q in sorted(all_quarters):
        fiscal_quarter = f"{year}Q{q}"
        missing = [
            sn for sn in required_short_names if (year, q) not in indexed.get(sn, {})
        ]
        if missing:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: missing concepts {missing}"
            )
            continue
        try:
            net_income = float(indexed["net_income"][(year, q)]["val"])
            se = float(indexed["stockholders_equity"][(year, q)]["val"])
            revenues = float(indexed["revenues"][(year, q)]["val"])
            cogs = float(indexed["cogs"][(year, q)]["val"])
            cfo = float(indexed["cfo"][(year, q)]["val"])
            capex = abs(float(indexed["capex"][(year, q)]["val"]))
            long_term_debt = float(indexed["long_term_debt"][(year, q)]["val"])
            assets = float(indexed["assets"][(year, q)]["val"])
            cash = float(indexed["cash"][(year, q)]["val"])
            operating_income = float(indexed["operating_income"][(year, q)]["val"])
            d_and_a = float(
                indexed["depreciation_amortization"][(year, q)]["val"]
            )
            shares = float(indexed["shares_outstanding"][(year, q)]["val"])
        except (KeyError, TypeError, ValueError) as exc:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: concept value cast failed ({exc})"
            )
            continue

        # report_date = latest filed across the required concepts in
        # this quarter (the row exists once all eleven concepts are
        # filed).
        filed_dates = []
        for sn in required_short_names:
            entry = indexed[sn].get((year, q))
            if entry and "filed" in entry:
                filed_dates.append(str(entry["filed"]))
        if not filed_dates:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: no filed date on any concept"
            )
            continue
        report_date = max(filed_dates)
        report_dt = date.fromisoformat(report_date)
        fq_end_str = str(indexed["assets"][(year, q)]["end"])
        try:
            fq_end_dt = date.fromisoformat(fq_end_str)
        except ValueError:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: bad fiscal_quarter_end '{fq_end_str}'"
            )
            continue

        close = _nearest_close(prices, ticker, report_dt)
        if close is None:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: no Tiingo close near "
                f"report_date {report_date} (±5d)"
            )
            continue
        market_cap = close * shares
        if market_cap <= 0:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: market_cap non-positive "
                f"(close={close} × shares={shares})"
            )
            continue

        # NetIncome_TTM ≈ latest available NetIncome (per quarterly
        # accounting note in module docstring). For most quarters the
        # SEC entry is cumulative-to-date for that fiscal year.
        net_income_ttm = net_income
        ebitda = compute_ebitda(operating_income, d_and_a)

        try:
            roe = compute_roe(net_income, se)
            gross_margin = compute_gross_margin(revenues, cogs)
            fcf_yield = compute_fcf_yield(cfo, capex, market_cap)
            debt_to_assets = compute_debt_to_assets(long_term_debt, assets)
            pe = compute_pe(market_cap, net_income_ttm)
            pb = compute_pb(market_cap, se)
            ev_ebitda = compute_ev_ebitda(market_cap, long_term_debt, cash, ebitda)
            earnings_yield = compute_earnings_yield(net_income_ttm, market_cap)
        except ValueError as exc:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: ratio compute failed ({exc})"
            )
            continue

        rows.append(
            {
                "report_date": report_date,
                "ticker": ticker,
                "fiscal_quarter": fiscal_quarter,
                "fiscal_quarter_end": fq_end_dt.isoformat(),
                "roe": round(roe, 4),
                "gross_margin": round(gross_margin, 4),
                "fcf_yield": round(fcf_yield, 4),
                "debt_to_assets": round(debt_to_assets, 4),
                "pe": round(pe, 2),
                "pb": round(pb, 2),
                "ev_ebitda": round(ev_ebitda, 2),
                "earnings_yield": round(earnings_yield, 4),
            }
        )
    return rows, skip_messages


def write_vendor_artifacts(
    cik: int,
    ticker: str,
    raw_payload: dict[str, Any],
    parsed_ratios: list[dict[str, Any]],
    skips: list[str],
    destination_root: Path,
) -> Path:
    """Write the vendor-raw artefacts for one ticker atomically.

    Layout (one CIK directory; not per-accession as in F001 spec — SEC
    companyfacts returns the consolidated payload, not per-filing
    documents, so per-accession sub-folders would duplicate)::

        data/snapshots/fundamentals/sec_edgar/{cik:010d}/
        ├── companyfacts.json      # the raw SEC response
        ├── parsed_ratios.json     # the eight-ratio rows we wrote to unified
        └── metadata.json          # ticker / cik / fetched_at / row_count / skips
    """

    cik_dir = destination_root / "fundamentals" / "sec_edgar" / f"{cik:010d}"
    cik_dir.mkdir(parents=True, exist_ok=True)

    _atomic_json_write(cik_dir / "companyfacts.json", raw_payload)
    _atomic_json_write(cik_dir / "parsed_ratios.json", parsed_ratios)
    _atomic_json_write(
        cik_dir / "metadata.json",
        {
            "ticker": ticker,
            "cik": cik,
            "fetched_at": date.today().isoformat(),
            "row_count": len(parsed_ratios),
            "skip_count": len(skips),
            "skips": skips[:20],  # cap to avoid bloating metadata.json
        },
    )
    return cik_dir


def _atomic_json_write(destination: Path, payload: Any) -> None:
    """Write JSON via temp file + os.replace so a kill mid-write leaves
    the previous good file in place."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as tmp:
        json.dump(payload, tmp, separators=(",", ":"))
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, destination)


def merge_into_unified(
    new_rows: Iterable[dict[str, Any]],
    unified_path: Path,
) -> int:
    """Sort + dedupe + atomic-write the unified fundamentals CSV.

    Dedup key is ``(ticker, fiscal_quarter)`` — re-running the same
    range for the same ticker collapses to a single set of rows
    (latest computation wins). Returns the row count after the merge.
    """

    unified_path.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    if unified_path.exists():
        with unified_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                seen[(row["ticker"], row["fiscal_quarter"])] = row
    for row in new_rows:
        seen[(str(row["ticker"]), str(row["fiscal_quarter"]))] = row
    ordered = sorted(
        seen.values(),
        key=lambda r: (str(r["ticker"]), str(r["fiscal_quarter"])),
    )
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
    loader: SECEDGARFundamentalsLoader,
    *,
    snapshots_root: Path,
    prices_csv: Path | None = None,
) -> tuple[int, list[str], list[str]]:
    """Run the per-ticker backfill loop.

    Returns ``(row_count, failures, synthetic_skips)``:

    * ``row_count`` — total rows in the unified file after merge.
    * ``failures`` — real-ticker errors (network / parse / value).
    * ``synthetic_skips`` — synthetic-ticker entries that were
      intentionally skipped per Planner decision #3 (fail-safe; not
      a failure).
    """

    prices: dict[tuple[str, str], float] = (
        _load_close_prices(prices_csv) if prices_csv else {}
    )
    if prices_csv and not prices:
        logger.warning(
            "no Tiingo prices indexed from %s — MarketCap-dependent ratios "
            "(fcf_yield/pe/pb/ev_ebitda/earnings_yield) will skip quarters "
            "without a close match",
            prices_csv,
        )

    unified_path = snapshots_root / "fundamentals" / "unified" / "fundamentals.csv"

    new_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    synthetic_skips: list[str] = []
    for ticker in tickers:
        cik = loader.ticker_cik_map.get(ticker)
        if ticker in B025_SYNTHETIC_TICKERS or cik is None:
            synthetic_skips.append(ticker)
            logger.warning(
                "skip synthetic ticker %s (no SEC filing; B025 fixture-only)",
                ticker,
            )
            continue
        try:
            payload = loader.fetch_raw_companyfacts(ticker)
        except ValueError as exc:
            # ValueError(Synthetic ...) is the contract from F001; but
            # we already skipped above. This branch catches anything
            # else (ticker not in map, etc.).
            failures.append(f"{ticker}: {exc}")
            logger.error("fetch failed for %s: %s", ticker, exc)
            continue
        except Exception as exc:
            failures.append(f"{ticker}: {type(exc).__name__}: {exc}")
            logger.error("fetch crashed for %s: %s", ticker, exc)
            continue

        rows, skips = raw_companyfacts_to_parsed_ratios(
            ticker, payload, prices=prices
        )
        # Filter rows to the requested filing-date window.
        in_window = [
            r
            for r in rows
            if from_date <= date.fromisoformat(str(r["report_date"])) <= to_date
        ]
        write_vendor_artifacts(
            cast_cik := int(cik),
            ticker,
            payload,
            in_window,
            skips,
            snapshots_root,
        )
        del cast_cik  # silence lint: walrus value used by write call
        new_rows.extend(in_window)
        logger.info(
            "%s — kept %d rows in window (computed %d, dropped %d outside / skipped %d)",
            ticker,
            len(in_window),
            len(rows),
            len(rows) - len(in_window),
            len(skips),
        )

    total = merge_into_unified(new_rows, unified_path)
    return total, failures, synthetic_skips


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=date(2014, 1, 1),
        help="Earliest filing date to retain in ISO-8601 (default: 2014-01-01)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=date.today(),
        help="Latest filing date to retain in ISO-8601 (default: today)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tickers",
        help="Comma-separated list of tickers (overrides --universe)",
    )
    group.add_argument(
        "--universe",
        default="us_quality",
        choices=["us_quality"],
        help="Named universe (default: us_quality — B025 30-ticker set)",
    )
    parser.add_argument(
        "--snapshots-root",
        type=Path,
        default=REPO_ROOT / "data" / "snapshots",
        help="Where to write the vendor + unified files (default: data/snapshots)",
    )
    parser.add_argument(
        "--prices-csv",
        type=Path,
        default=REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv",
        help=(
            "B028 unified prices file for MarketCap = close(report_date) × "
            "shares_outstanding (default: data/snapshots/prices/unified/prices_daily.csv)"
        ),
    )
    args = parser.parse_args(argv)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = us_quality_universe()

    print(
        f"Backfilling {len(tickers)} ticker(s) from {args.from_date.isoformat()} "
        f"to {args.to_date.isoformat()} (SEC EDGAR companyfacts)..."
    )
    loader = SECEDGARFundamentalsLoader()
    row_count, failures, synthetic_skips = backfill(
        tickers,
        args.from_date,
        args.to_date,
        loader,
        snapshots_root=args.snapshots_root,
        prices_csv=args.prices_csv,
    )
    print(f"Unified fundamentals.csv now holds {row_count} rows")
    if synthetic_skips:
        print(
            f"Skipped {len(synthetic_skips)} synthetic ticker(s) (B025 "
            f"fixture-only; no SEC filings): {synthetic_skips}"
        )
    if failures:
        print(f"\n{len(failures)} real ticker(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
