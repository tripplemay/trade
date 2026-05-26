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
    slips into the real-tickers tuple. This is the consistency
    assert the unit test calls.
    """

    fixture = load_b025_universe_from_fixture()
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


if __name__ == "__main__":
    tickers = us_quality_universe()
    print(f"B025 us_quality universe size: {len(tickers)}")
    for t in tickers:
        marker = "(synthetic — skip in SEC backfill)" if t.startswith("ZQ") else ""
        print(f"  {t} {marker}")
