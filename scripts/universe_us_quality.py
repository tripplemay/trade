"""B029 F002 — B025 us_quality_momentum ticker universe for SEC EDGAR backfill.

Single source of truth for the ticker set ``scripts/backfill_fundamentals.py``
walks through SEC EDGAR. Mirrors the structure of B028's
``scripts/universe_master.py`` but for the fundamentals batch — the
universe is **exactly** the B025
``data/fixtures/us_quality_momentum/universe.csv`` 30-ticker set,
including the three synthetic ``ZQ*`` fixture tickers that have no
real SEC filings.

The synthetic tickers stay in the universe list so the F003 PIT
loader and the B025 deterministic backtest still see them; the
backfill driver (``scripts/backfill_fundamentals.py``) catches the
``ValueError("Synthetic ticker ... has no SEC filing")`` raised by
:class:`SECEDGARFundamentalsLoader` and ``log warn + skip`` per
Planner pre-impl adjudication 2026-05-26 decision #3.

Maintenance:

* If B025 fixture adds a real ticker, mirror it in
  :data:`US_QUALITY_REAL_TICKERS` here. The
  :func:`assert_us_quality_universe_consistent_with_fixture` helper
  fails CI when the two sides drift.
* If B025 fixture adds a synthetic ``ZQ*`` ticker, mirror it in
  :data:`B025_SYNTHETIC_TICKERS`. Synthetic tickers go through the
  same universe iteration but skip the SEC fetch path.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

# B025 us_quality_momentum real-listed tickers — 27 entries that have
# valid SEC CIKs and 10+ years of quarterly XBRL filings.
US_QUALITY_REAL_TICKERS: tuple[str, ...] = (
    "AAPL", "AMT", "AMZN", "APD", "BAC", "CAT", "CVX", "DUK", "ECL",
    "GOOGL", "HD", "HON", "JNJ", "JPM", "KO", "LIN", "META", "MSFT",
    "NEE", "NVDA", "PG", "PLD", "UNH", "UPS", "V", "WMT", "XOM",
)

# B025 us_quality_momentum synthetic fixture tickers — 3 virtual
# companies (industrial smallcap / penny tech / light-volume health)
# that only exist in the fixture for backtest robustness tests. They
# have no real SEC filings and the backfill driver skips them with a
# warn log (Planner pre-impl adjudication 2026-05-26 decision #3).
B025_SYNTHETIC_TICKERS: tuple[str, ...] = (
    "ZQAI",  # Synthetic Industrial Smallcap Co.
    "ZQPT",  # Synthetic Penny Tech Holdings
    "ZQLH",  # Synthetic Light Volume Health Inc.
)


# B030 F001 — GICS sector per ticker, mirrors the ``gics_sector``
# column of ``data/fixtures/us_quality_momentum/universe.csv``. The
# F002 backfill driver looks up the sector for each ticker and threads
# it through :func:`workbench_api.data.xbrl_parser.get_concept_alias_chain`
# so per-sector overrides (Financials / Utilities / Real Estate) front-
# load the sector-idiomatic SEC concepts — the fix for the B029
# Soft-watch S1 (6 sector tickers BAC/JPM/V/LIN/NEE/PLD producing 0
# rows on the first-run backfill).
#
# LIN (Linde plc) is GICS Materials but uses Utilities-style XBRL
# (``LongTermDebtNoncurrent`` as primary, ``OperatingExpenses`` rather
# than COGS). The B030 spec §4.2 documents this dialect grouping; the
# mapping below records LIN's **GICS sector** ("Materials") faithfully
# and the alias resolver falls back to the default chain — which
# happens to include the Utilities-style concepts as later positions,
# so LIN still resolves. Force-aliasing LIN to "Utilities" was
# considered and rejected (it would let the dialect leak into reports
# and confuse downstream sector breakdowns).
US_QUALITY_TICKER_SECTORS: dict[str, str] = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "JNJ": "Health Care",
    "UNH": "Health Care",
    "JPM": "Financials",
    "BAC": "Financials",
    "V": "Financials",
    "AMZN": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "HON": "Industrials",
    "UPS": "Industrials",
    "CAT": "Industrials",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "WMT": "Consumer Staples",
    "XOM": "Energy",
    "CVX": "Energy",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "PLD": "Real Estate",
    "AMT": "Real Estate",
    "LIN": "Materials",
    "APD": "Materials",
    "ECL": "Materials",
    # Synthetic tickers are skipped in the SEC backfill but kept here
    # so :func:`get_ticker_sector` returns the B025 fixture value for
    # consistency in non-backfill code paths.
    "ZQAI": "Industrials",
    "ZQPT": "Information Technology",
    "ZQLH": "Health Care",
}


def get_ticker_sector(ticker: str) -> str | None:
    """Return the GICS sector string for ``ticker``, or ``None`` if the
    ticker is not in the B025 us_quality universe.

    Used by the F002 backfill driver to thread sector into
    :func:`workbench_api.data.xbrl_parser.get_concept_alias_chain` so
    per-sector concept overrides apply when the filer's XBRL dialect
    drifts from the default. Returning ``None`` (rather than raising)
    matches the loose-coupling pattern the driver uses elsewhere —
    callers can pass ``None`` straight through to the alias resolver,
    which falls back to the default chain.
    """

    return US_QUALITY_TICKER_SECTORS.get(ticker)


def us_quality_universe() -> list[str]:
    """Return the 30-ticker B025 us_quality universe in stable order.

    Real tickers first (alphabetical-ish, matching the B025 fixture
    row order), then synthetic ``ZQ*`` tickers appended. The order
    is deterministic so the F002 backfill driver iterates the same
    sequence on every run.
    """

    return list(US_QUALITY_REAL_TICKERS) + list(B025_SYNTHETIC_TICKERS)


def load_b025_universe_from_fixture(
    fixture_path: Path | None = None,
) -> list[str]:
    """Re-resolve the B025 universe by reading the on-disk fixture.

    Returns the **full 30-ticker** set (real + synthetic) in the same
    order they appear in the fixture row sequence. Used by the
    consistency assertion below.
    """

    repo_root = Path(__file__).resolve().parents[1]
    target = fixture_path or (
        repo_root / "data" / "fixtures" / "us_quality_momentum" / "universe.csv"
    )
    df = pd.read_csv(target)
    return list(df["ticker"].astype(str))


def assert_us_quality_universe_consistent_with_fixture() -> None:
    """Pin the static lists against the on-disk fixture.

    Raises ``AssertionError`` if the two drift — e.g. the fixture
    adds a ticker we forgot to mirror here, or a synthetic ticker
    slips into the real-tickers tuple, or :data:`US_QUALITY_TICKER_SECTORS`
    drifts from the fixture's ``gics_sector`` column. This is the
    consistency assert the unit test calls.
    """

    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "data" / "fixtures" / "us_quality_momentum" / "universe.csv"
    df = pd.read_csv(fixture_path)

    fixture = list(df["ticker"].astype(str))
    fixture_real = sorted(t for t in fixture if not t.startswith("ZQ"))
    fixture_synthetic = sorted(t for t in fixture if t.startswith("ZQ"))
    declared_real = sorted(US_QUALITY_REAL_TICKERS)
    declared_synthetic = sorted(B025_SYNTHETIC_TICKERS)

    if fixture_real != declared_real:
        raise AssertionError(
            "scripts/universe_us_quality.py US_QUALITY_REAL_TICKERS drifted "
            "from data/fixtures/us_quality_momentum/universe.csv (real subset). "
            f"Fixture only: {sorted(set(fixture_real) - set(declared_real))}; "
            f"declared only: {sorted(set(declared_real) - set(fixture_real))}. "
            "Reconcile both sides."
        )
    if fixture_synthetic != declared_synthetic:
        raise AssertionError(
            "scripts/universe_us_quality.py B025_SYNTHETIC_TICKERS drifted "
            "from data/fixtures/us_quality_momentum/universe.csv (synthetic "
            f"subset). Fixture only: "
            f"{sorted(set(fixture_synthetic) - set(declared_synthetic))}; "
            f"declared only: "
            f"{sorted(set(declared_synthetic) - set(fixture_synthetic))}. "
            "Reconcile both sides."
        )

    # B030 F001 — sector mapping must match the fixture ``gics_sector``
    # column on every row. Any drift breaks the per-sector alias chain
    # resolution and re-introduces the B029 Soft-watch S1 (sector
    # tickers producing 0 backfill rows).
    fixture_sectors: dict[str, str] = {
        str(r["ticker"]): str(r["gics_sector"]) for _, r in df.iterrows()
    }
    drift: list[str] = []
    for ticker, fixture_sector in fixture_sectors.items():
        declared_sector = US_QUALITY_TICKER_SECTORS.get(ticker)
        if declared_sector != fixture_sector:
            drift.append(
                f"{ticker}: fixture={fixture_sector!r} declared={declared_sector!r}"
            )
    if drift:
        raise AssertionError(
            "scripts/universe_us_quality.py US_QUALITY_TICKER_SECTORS drifted "
            "from data/fixtures/us_quality_momentum/universe.csv (gics_sector "
            "column). " + "; ".join(drift) + ". Reconcile both sides."
        )


if __name__ == "__main__":
    tickers = us_quality_universe()
    print(f"B025 us_quality universe size: {len(tickers)}")
    for t in tickers:
        marker = "(synthetic — skip in SEC backfill)" if t.startswith("ZQ") else ""
        print(f"  {t} {marker}")
