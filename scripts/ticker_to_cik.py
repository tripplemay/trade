"""B029 F002 — ticker → SEC CIK lookup + fixture cache rebuilder.

The day-to-day path reads
``workbench/backend/workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json``
(committed in B029 F001) — the 30-ticker B025 us_quality cache with
27 real CIKs + 3 synthetic ``None`` entries. The cache file is the
authoritative source for the backfill driver and the unit tests.

The optional ``--rebuild`` mode fetches the public SEC
``company_tickers.json`` index
(``https://www.sec.gov/files/company_tickers.json``), resolves any
real ticker in the B025 universe whose CIK changed (or any new
addition), and rewrites the fixture file. The rebuild requires the
SEC User-Agent header same as the main loader (永久边界 (h)) — pass
``--contact-email`` or set ``SEC_EDGAR_CONTACT_EMAIL`` in the env.

Synthetic tickers (``ZQ*``) are preserved as ``null`` across rebuilds
because they have no SEC presence and never will (decision #3).

Usage::

    # Default: just read the cached fixture and print mapping.
    python scripts/ticker_to_cik.py

    # Optional: re-resolve real tickers from SEC ticker index.
    python scripts/ticker_to_cik.py --rebuild --contact-email research@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_PKG = REPO_ROOT / "workbench" / "backend"
if str(BACKEND_PKG) not in sys.path:
    sys.path.insert(0, str(BACKEND_PKG))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from universe_us_quality import (  # noqa: E402
    B025_SYNTHETIC_TICKERS,
    US_QUALITY_REAL_TICKERS,
    us_quality_universe,
)

CIK_MAP_PATH = (
    BACKEND_PKG
    / "workbench_api"
    / "data"
    / "fixtures"
    / "sec_edgar_responses"
    / "ticker_cik_map.json"
)

SEC_TICKER_INDEX_URL = "https://www.sec.gov/files/company_tickers.json"


def load_cached_ticker_cik_map() -> dict[str, int | None]:
    """Read the committed fixture as a typed ``ticker → CIK | None`` dict.

    Skips the ``_doc`` sentinel key (and any future underscore-prefixed
    inline-documentation keys) consistent with
    :func:`workbench_api.data.sec_edgar_loader._load_default_ticker_cik_map`.
    """

    raw: dict[str, object] = json.loads(CIK_MAP_PATH.read_text(encoding="utf-8"))
    out: dict[str, int | None] = {}
    for ticker, cik in raw.items():
        if str(ticker).startswith("_"):
            continue
        if cik is None:
            out[str(ticker)] = None
        else:
            out[str(ticker)] = int(cik)  # type: ignore[arg-type]
    return out


def rebuild_ticker_cik_map(contact_email: str) -> dict[str, int | None]:
    """Re-resolve all 27 real B025 tickers against SEC's public ticker
    index. Synthetic ``ZQ*`` tickers are preserved as ``None``.

    Network round-trip happens once for the full SEC index (a single
    ~2MB JSON). The output is **not** written to disk — the caller
    (``main()``) is responsible for the atomic file write so this
    function stays unit-testable without filesystem touches.
    """

    if not contact_email:
        raise RuntimeError(
            "rebuild_ticker_cik_map needs SEC_EDGAR_CONTACT_EMAIL "
            "(arg or env) — SEC fair-access policy requires a contact "
            "in the User-Agent header (永久边界 (h))."
        )
    headers = {
        "User-Agent": f"Workbench Trade research-only {contact_email}",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30.0, headers=headers) as client:
        response = client.get(SEC_TICKER_INDEX_URL)
        response.raise_for_status()
        index = response.json()
    # SEC index shape: {"0": {"cik_str": ..., "ticker": ..., "title": ...}, ...}
    ticker_to_cik: dict[str, int] = {}
    for _row_key, entry in index.items():
        if isinstance(entry, dict):
            t = str(entry.get("ticker", "")).upper()
            c = entry.get("cik_str")
            if t and isinstance(c, int):
                ticker_to_cik[t] = c
    out: dict[str, int | None] = {}
    missing: list[str] = []
    for t in US_QUALITY_REAL_TICKERS:
        cik = ticker_to_cik.get(t)
        if cik is None:
            missing.append(t)
            out[t] = None
        else:
            out[t] = cik
    for t in B025_SYNTHETIC_TICKERS:
        out[t] = None
    if missing:
        print(
            f"warning: {len(missing)} real B025 ticker(s) not resolved against "
            f"SEC public index: {missing} (set to null in rebuilt map; "
            "verify ticker spellings or SEC index drift)",
            file=sys.stderr,
        )
    return out


def write_ticker_cik_map(mapping: dict[str, int | None], destination: Path) -> None:
    """Atomic-write ``mapping`` back to the fixture path.

    Preserves the ``_doc`` sentinel inline comment for fixture readers
    by re-injecting the same doc block the F001 commit added (so a
    rebuild doesn't drop the inline documentation).
    """

    payload: dict[str, object] = {
        "_doc": (
            "B025 us_quality_momentum 30-ticker universe → SEC CIK (Central "
            "Index Key) cache. 27 real companies with publicly known CIKs + "
            "3 synthetic fixture tickers (ZQAI/ZQPT/ZQLH) mapped to null "
            "because they never have real SEC filings. Per Planner pre-impl "
            "adjudication 2026-05-26 decision #3: SECEDGARFundamentalsLoader "
            "raises ValueError on null-CIK lookup; F002 backfill driver "
            "catches and log-warn-skips without aborting. CIK lookups are "
            "public (https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            "&output=atom) and stable per-entity over the lifetime of the SEC "
            "filer registration. Source-of-truth for universe list: "
            "data/fixtures/us_quality_momentum/universe.csv."
        )
    }
    for ticker, cik in mapping.items():
        payload[ticker] = cik
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Re-resolve real B025 tickers from SEC's public ticker index "
        "and rewrite the fixture file. Requires SEC_EDGAR_CONTACT_EMAIL.",
    )
    parser.add_argument(
        "--contact-email",
        default=os.environ.get("SEC_EDGAR_CONTACT_EMAIL"),
        help="Override SEC_EDGAR_CONTACT_EMAIL env var (rebuild path).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CIK_MAP_PATH,
        help=f"Output path for --rebuild (default: {CIK_MAP_PATH.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args(argv)

    if args.rebuild:
        mapping = rebuild_ticker_cik_map(args.contact_email)
        write_ticker_cik_map(mapping, args.output)
        real = sum(1 for cik in mapping.values() if cik is not None)
        synthetic = sum(1 for cik in mapping.values() if cik is None)
        print(
            f"Rewrote {args.output.relative_to(REPO_ROOT)} — "
            f"{real} real CIK(s) + {synthetic} synthetic null(s)"
        )
        return 0

    # Default: read + print the cached fixture.
    mapping = load_cached_ticker_cik_map()
    print(f"{len(mapping)} ticker(s) in cached map:")
    for t in us_quality_universe():
        cik = mapping.get(t)
        label = f"CIK {cik:010d}" if isinstance(cik, int) else "(synthetic — null)"
        print(f"  {t:<6} {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
