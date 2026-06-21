"""B071 F002 — freeze the golden real-data fixture (carve, NOT generate).

This script *carves* a committed, deterministic subset out of the **real**
market-data snapshots that live (gitignored) under ``data/snapshots/``:

* prices    ← ``data/snapshots/prices/unified/prices_daily.csv``      (real Tiingo OHLCV)
* fundamentals ← ``data/snapshots/fundamentals/unified/fundamentals.csv`` (real SEC EDGAR XBRL)

It is the deliberate opposite of the synthetic ``_generate.py`` fixtures
(``data/fixtures/us_quality_momentum/_generate.py`` etc.): those *synthesise*
plausible numbers from a seed and run anywhere; this script can **only**
reproduce the golden files on a checkout that already holds the real
snapshots (which are gitignored and not on a fresh CI clone). That is the
whole point — the golden CSVs are a frozen photograph of real history, and
``_freeze.py`` is the committed provenance record of *how* the photograph
was cropped, not a CI-runnable regenerator. See ``README.md`` for the
non-regenerability note.

Determinism: every value column is read and written as a **raw string**
(``dtype=str``, ``keep_default_na=False``) so the carved numbers are
byte-for-byte identical to the real snapshot — no float re-parsing, no
re-formatting. Rows are sorted by ``(ticker, date)`` / ``(ticker,
report_date)`` so a re-run on the same snapshot produces a bit-identical
file (the F003 deterministic-backtest acceptance depends on this).

Run (only on a checkout WITH the real snapshots present)::

    .venv/bin/python data/fixtures/golden/_freeze.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# --- Repo geometry -----------------------------------------------------------
# ``data/fixtures/golden/_freeze.py`` → parents[3] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "data" / "fixtures" / "golden"

SNAPSHOT_PRICES = REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv"
SNAPSHOT_FUNDAMENTALS = (
    REPO_ROOT / "data" / "snapshots" / "fundamentals" / "unified" / "fundamentals.csv"
)
# universe metadata (real-world GICS classifications) is carried over from the
# B025 us_quality fixture, subset to the golden equity names. market_cap_initial
# is a synthetic placeholder there (see that fixture's README) — see golden
# README for the honest provenance tiering.
B025_UNIVERSE = REPO_ROOT / "data" / "fixtures" / "us_quality_momentum" / "universe.csv"

# --- Golden universe (B071 F002, per the data-consumption survey) -------------
# 25 quality names: real Tiingo prices AND ≥1 PIT-visible real SEC fundamental
# within the 2019-2023 window. This is the canonical B025 us_quality universe
# (== workbench equity_universe) MINUS CAT + GOOGL: the committed SEC snapshot
# holds no 10-K/10-Q for CAT before 2026-04 nor GOOGL before 2024-07, so neither
# has any fundamental visible during 2019-2023 and they cannot participate in
# the quality factor pipeline (a stale-but-real filing is fine; *zero* visible
# filings is a degenerate column). Dropping them loses no GICS sector — HON/UPS
# still cover Industrials, META still covers Communication Services. The
# remaining 25 each have real prices + real fundamentals, driving us_quality
# multi-factor selection, the master us_quality sleeve, and the equity slice of
# the recommendation universe. See README §provenance for the per-ticker
# sparsity table.
QUALITY_TICKERS = [
    "AAPL", "AMT", "AMZN", "APD", "BAC", "CVX", "DUK", "ECL", "HD", "HON",
    "JNJ", "JPM", "KO", "LIN", "META", "MSFT", "NEE", "NVDA", "PG", "PLD",
    "UNH", "UPS", "V", "WMT", "XOM",
]
# 13 ETF / defensive: real Tiingo prices, NO fundamentals (price-only engines).
# Covers risk_parity 5-tuple (SPY/VEA/AGG/GLD/SGOV) + momentum breadth
# (QQQ/VWO/EEM) + hk_china proxies (MCHI/FXI/KWEB) + regime stabilisers
# (IEF/TLT) + master defensive (SGOV). Every one is present in the real
# 52-ticker snapshot.
ETF_TICKERS = [
    "SPY", "QQQ", "VEA", "VWO", "EEM", "AGG", "IEF", "TLT", "GLD", "SGOV",
    "MCHI", "FXI", "KWEB",
]
PRICE_TICKERS = sorted(set(QUALITY_TICKERS) | set(ETF_TICKERS))

# --- Windows -----------------------------------------------------------------
# Prices: 2019-2023 covers the 2020 COVID crash and the 2022 bear market
# (regime/crisis assertions). Fundamentals reach back to the snapshot's start
# (2014) so the PIT loader always has a visible filing during the price window —
# the SEC snapshot is sparse for some names (e.g. META: 2014-2017 then 2023+;
# ECL: 2014 then 2023+), so a wide lower bound lets the latest pre-window filing
# stay visible (stale-but-real) instead of leaving an early-window blank. The
# loader's effective_date filter still enforces PIT visibility at each as_of.
PRICE_START, PRICE_END = "2019-01-01", "2023-12-31"
FUND_START, FUND_END = "2014-01-01", "2023-12-31"

# Schemas the loaders require (mirror trade.data.us_quality_universe +
# trade.data.loader). Kept here so the freeze fails loud on a schema drift.
PRICES_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
FUNDAMENTALS_COLUMNS = [
    "report_date", "ticker", "fiscal_quarter", "fiscal_quarter_end", "roe",
    "gross_margin", "fcf_yield", "debt_to_assets", "pe", "pb", "ev_ebitda",
    "earnings_yield",
]
UNIVERSE_COLUMNS = [
    "ticker", "name", "exchange", "gics_sector", "gics_industry",
    "listing_date", "market_cap_initial",
]
EARNINGS_COLUMNS = ["ticker", "earnings_date", "fiscal_quarter", "fiscal_quarter_end"]


def _read_raw(path: Path) -> pd.DataFrame:
    """Read a CSV preserving every cell as the exact source string."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _require(path: Path, what: str) -> None:
    if not path.is_file():
        sys.exit(
            f"ERROR: {what} not found at {path}.\n"
            "  _freeze.py carves from the REAL gitignored snapshots under "
            "data/snapshots/.\n"
            "  It is a provenance record, not a fresh-checkout regenerator — "
            "the golden CSVs are committed; you do NOT need to re-run this to "
            "use them. Re-run only on a machine that holds the real snapshots."
        )


def freeze_prices() -> pd.DataFrame:
    _require(SNAPSHOT_PRICES, "real unified prices snapshot")
    frame = _read_raw(SNAPSHOT_PRICES)
    if list(frame.columns) != PRICES_COLUMNS:
        sys.exit(f"ERROR: prices snapshot schema drift: {list(frame.columns)} != {PRICES_COLUMNS}")
    mask = (
        frame["ticker"].isin(PRICE_TICKERS)
        & (frame["date"] >= PRICE_START)  # ISO YYYY-MM-DD → lexicographic == chronological
        & (frame["date"] <= PRICE_END)
    )
    out = frame[mask].sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    return out


def freeze_fundamentals() -> pd.DataFrame:
    _require(SNAPSHOT_FUNDAMENTALS, "real unified fundamentals snapshot")
    frame = _read_raw(SNAPSHOT_FUNDAMENTALS)
    if list(frame.columns) != FUNDAMENTALS_COLUMNS:
        sys.exit(
            "ERROR: fundamentals snapshot schema drift: "
            f"{list(frame.columns)} != {FUNDAMENTALS_COLUMNS}"
        )
    mask = (
        frame["ticker"].isin(QUALITY_TICKERS)
        & (frame["report_date"] >= FUND_START)
        & (frame["report_date"] <= FUND_END)
    )
    out = frame[mask].sort_values(["ticker", "report_date"], kind="stable").reset_index(drop=True)
    return out


def freeze_universe() -> pd.DataFrame:
    _require(B025_UNIVERSE, "B025 us_quality universe.csv (GICS metadata source)")
    frame = _read_raw(B025_UNIVERSE)
    if list(frame.columns) != UNIVERSE_COLUMNS:
        sys.exit(f"ERROR: universe schema drift: {list(frame.columns)} != {UNIVERSE_COLUMNS}")
    out = (
        frame[frame["ticker"].isin(QUALITY_TICKERS)]
        .sort_values("ticker", kind="stable")
        .reset_index(drop=True)
    )
    return out


def derive_earnings(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """earnings_calendar derived from the REAL fundamentals filings.

    earnings_date = report_date (the SEC filing date) as a conservative proxy:
    the actual earnings announcement precedes the 10-K/10-Q filing by days, so
    using the filing date errs late (PIT-safe). Documented in the README.
    """
    out = pd.DataFrame(
        {
            "ticker": fundamentals["ticker"],
            "earnings_date": fundamentals["report_date"],
            "fiscal_quarter": fundamentals["fiscal_quarter"],
            "fiscal_quarter_end": fundamentals["fiscal_quarter_end"],
        }
    )
    return out.sort_values(["ticker", "earnings_date"], kind="stable").reset_index(drop=True)


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    prices = freeze_prices()
    fundamentals = freeze_fundamentals()
    universe = freeze_universe()
    earnings = derive_earnings(fundamentals)

    # Sanity: every quality name must have both prices and fundamentals; every
    # ETF must have prices. A degenerate carve (missing ticker) would silently
    # weaken the F003/F004 assertions, so fail loud here instead.
    price_names = set(prices["ticker"].unique())
    fund_names = set(fundamentals["ticker"].unique())
    missing_prices = set(PRICE_TICKERS) - price_names
    missing_funds = set(QUALITY_TICKERS) - fund_names
    if missing_prices:
        sys.exit(f"ERROR: golden prices missing tickers: {sorted(missing_prices)}")
    if missing_funds:
        sys.exit(f"ERROR: golden fundamentals missing tickers: {sorted(missing_funds)}")

    prices.to_csv(GOLDEN_DIR / "prices_daily.csv", index=False)
    fundamentals.to_csv(GOLDEN_DIR / "fundamentals.csv", index=False)
    universe.to_csv(GOLDEN_DIR / "universe.csv", index=False)
    earnings.to_csv(GOLDEN_DIR / "earnings_calendar.csv", index=False)

    csv_names = ("prices_daily.csv", "fundamentals.csv", "universe.csv", "earnings_calendar.csv")
    total_bytes = sum((GOLDEN_DIR / name).stat().st_size for name in csv_names)
    p_lo, p_hi = prices["date"].min(), prices["date"].max()
    f_lo, f_hi = fundamentals["report_date"].min(), fundamentals["report_date"].max()
    print(f"prices      : {len(prices):>7} rows, {len(price_names)} tickers, {p_lo}..{p_hi}")
    print(f"fundamentals: {len(fundamentals):>7} rows, {len(fund_names)} tickers, {f_lo}..{f_hi}")
    print(f"universe    : {len(universe):>7} rows")
    print(f"earnings    : {len(earnings):>7} rows")
    print(f"total golden size     : {total_bytes / 1_000_000:.2f} MB (budget < 5 MB)")
    if total_bytes >= 5_000_000:
        sys.exit("ERROR: golden fixture exceeds the 5 MB budget — trim tickers or window.")


if __name__ == "__main__":
    main()
