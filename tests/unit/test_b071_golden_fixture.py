"""B071 F002 — golden real-data fixture integrity guard.

Guards the committed ``data/fixtures/golden/`` artifact itself: schema
(headers match the loader contracts exactly), size budget (< 5 MB),
crisis-window coverage (2020 COVID + 2022 bear), ticker counts, and that
all four CSVs load through the real ``trade.data`` loaders without error.

Scope boundary: this is a *data-artifact* guard, distinct from F003
(deterministic backtest output) and F004 (strategy invariants). A red test
here means the fixture itself was corrupted / mis-carved, not that a
strategy regressed.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trade.data import us_quality_universe as uq
from trade.data.loader import (
    UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS,
    UNIFIED_REQUIRED_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "data" / "fixtures" / "golden"

EXPECTED_PRICE_TICKERS = 38  # 25 quality + 13 ETF
EXPECTED_QUALITY_TICKERS = 25
QUALITY_NAMES = {
    "AAPL", "AMT", "AMZN", "APD", "BAC", "CVX", "DUK", "ECL", "HD", "HON",
    "JNJ", "JPM", "KO", "LIN", "META", "MSFT", "NEE", "NVDA", "PG", "PLD",
    "UNH", "UPS", "V", "WMT", "XOM",
}
ETF_NAMES = {
    "SPY", "QQQ", "VEA", "VWO", "EEM", "AGG", "IEF", "TLT", "GLD", "SGOV",
    "MCHI", "FXI", "KWEB",
}

PRICES_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
FUNDAMENTALS_HEADER = [
    "report_date", "ticker", "fiscal_quarter", "fiscal_quarter_end", "roe",
    "gross_margin", "fcf_yield", "debt_to_assets", "pe", "pb", "ev_ebitda",
    "earnings_yield",
]
UNIVERSE_HEADER = [
    "ticker", "name", "exchange", "gics_sector", "gics_industry",
    "listing_date", "market_cap_initial",
]
EARNINGS_HEADER = ["ticker", "earnings_date", "fiscal_quarter", "fiscal_quarter_end"]


def _header(name: str) -> list[str]:
    with (GOLDEN_DIR / name).open(encoding="utf-8") as handle:
        return next(csv.reader(handle))


def test_all_four_files_exist() -> None:
    for name in ("prices_daily.csv", "fundamentals.csv", "universe.csv", "earnings_calendar.csv"):
        assert (GOLDEN_DIR / name).is_file(), f"golden fixture missing {name}"
    assert (GOLDEN_DIR / "README.md").is_file()
    assert (GOLDEN_DIR / "_freeze.py").is_file()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("prices_daily.csv", PRICES_HEADER),
        ("fundamentals.csv", FUNDAMENTALS_HEADER),
        ("universe.csv", UNIVERSE_HEADER),
        ("earnings_calendar.csv", EARNINGS_HEADER),
    ],
)
def test_headers_match_loader_contract(name: str, expected: list[str]) -> None:
    assert _header(name) == expected


def test_prices_schema_superset_of_unified_loader_requirement() -> None:
    assert set(_header("prices_daily.csv")) >= UNIFIED_REQUIRED_COLUMNS


def test_fundamentals_schema_superset_of_unified_loader_requirement() -> None:
    assert set(_header("fundamentals.csv")) >= set(UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS)


def test_total_size_under_5mb() -> None:
    names = ("prices_daily.csv", "fundamentals.csv", "universe.csv", "earnings_calendar.csv")
    total = sum((GOLDEN_DIR / name).stat().st_size for name in names)
    assert total < 5_000_000, f"golden fixture is {total / 1e6:.2f} MB (budget < 5 MB)"


def test_price_universe_is_25_quality_plus_13_etf() -> None:
    prices = uq.load_prices(fixture_dir=GOLDEN_DIR)
    tickers = set(prices["ticker"].unique())
    assert len(tickers) == EXPECTED_PRICE_TICKERS
    assert tickers >= QUALITY_NAMES
    assert tickers >= ETF_NAMES
    # CAT/GOOGL deliberately excluded (no in-window SEC filing); guard the call.
    assert "CAT" not in tickers
    assert "GOOGL" not in tickers


def test_fundamentals_cover_the_25_quality_names() -> None:
    funds = uq.load_fundamentals(fixture_dir=GOLDEN_DIR)
    names = set(funds["ticker"].unique())
    assert names == QUALITY_NAMES
    assert len(names) == EXPECTED_QUALITY_TICKERS


def test_prices_cover_2020_covid_and_2022_bear_windows() -> None:
    prices = uq.load_prices(fixture_dir=GOLDEN_DIR)
    dates = prices["date"]
    # COVID crash bottom region (Mar 2020) and 2022 bear must be present.
    assert ((dates.dt.year == 2020) & (dates.dt.month == 3)).any()
    assert (dates.dt.year == 2022).any()
    assert dates.min().year == 2019
    assert dates.max().year == 2023


def test_all_four_loaders_read_golden_without_error() -> None:
    # Exercises the schema validation inside each loader (a misshapen CSV
    # raises before returning).
    assert len(uq.load_prices(fixture_dir=GOLDEN_DIR)) > 0
    assert len(uq.load_fundamentals(fixture_dir=GOLDEN_DIR)) > 0
    assert len(uq.load_universe(fixture_dir=GOLDEN_DIR)) == EXPECTED_QUALITY_TICKERS
    assert len(uq.load_earnings_calendar(fixture_dir=GOLDEN_DIR)) > 0
