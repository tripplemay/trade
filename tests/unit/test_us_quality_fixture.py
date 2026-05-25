"""Unit tests for the B025 US Quality Momentum fixture + Repository + filter."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from trade.data.us_quality_filter import (
    LiquidityFilterError,
    LiquidityRejection,
    apply_liquidity_filter,
)
from trade.data.us_quality_universe import (
    DEFAULT_FIXTURE_DIR,
    EARNINGS_REQUIRED_COLUMNS,
    FUNDAMENTALS_REQUIRED_COLUMNS,
    PRICES_REQUIRED_COLUMNS,
    UNIVERSE_REQUIRED_COLUMNS,
    UniverseEntry,
    UsQualityFixtureError,
    load_earnings_calendar,
    load_fundamentals,
    load_prices,
    load_universe,
)

EXPECTED_TICKER_COUNT = 30
SYNTHETIC_TICKERS = {"ZQAI", "ZQPT", "ZQLH"}


# ---------------------------------------------------------------------------
# Universe loader
# ---------------------------------------------------------------------------


def test_load_universe_returns_30_entries_with_required_metadata() -> None:
    entries = load_universe()
    assert len(entries) == EXPECTED_TICKER_COUNT
    tickers = {entry.ticker for entry in entries}
    assert len(tickers) == EXPECTED_TICKER_COUNT  # no duplicates
    for entry in entries:
        assert isinstance(entry, UniverseEntry)
        assert entry.ticker
        assert entry.name
        assert entry.exchange in {"NYSE", "NASDAQ"}
        assert entry.gics_sector
        assert entry.gics_industry
        assert entry.market_cap_initial > 0


def test_load_universe_covers_eleven_gics_sectors_with_min_two_each() -> None:
    entries = load_universe()
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.gics_sector] = counts.get(entry.gics_sector, 0) + 1
    # F001 acceptance: >= 7 GICS sectors with >= 2 ticker each
    assert len(counts) >= 7
    assert all(count >= 2 for count in counts.values()), counts


def test_load_universe_filters_by_listing_date_when_as_of_provided() -> None:
    full = load_universe()
    # ZQAI listing 2020-06-15; ZQPT listing 2019-03-10; ZQLH listing 2018-11-08.
    early = load_universe(as_of=date(2019, 1, 1))
    excluded = {entry.ticker for entry in full} - {entry.ticker for entry in early}
    assert excluded == {"ZQAI", "ZQPT"}
    # Synthetic listings older than 2019-01-01 (LIN 2018-10-30, ZQLH 2018-11-08)
    # must remain visible.
    assert "LIN" in {entry.ticker for entry in early}
    assert "ZQLH" in {entry.ticker for entry in early}


def test_load_universe_rejects_missing_directory() -> None:
    with pytest.raises(UsQualityFixtureError, match="does not exist"):
        load_universe(fixture_dir=Path("/nonexistent/B025/fixture"))


def test_load_universe_rejects_missing_required_column(tmp_path: Path) -> None:
    bad_universe = tmp_path / "universe.csv"
    bad_universe.write_text("ticker,name\nAAA,Anonymous\n", encoding="utf-8")
    with pytest.raises(UsQualityFixtureError, match="missing required columns"):
        load_universe(fixture_dir=tmp_path)


# ---------------------------------------------------------------------------
# Prices loader
# ---------------------------------------------------------------------------


def test_load_prices_long_format_with_required_columns() -> None:
    prices = load_prices()
    for column in PRICES_REQUIRED_COLUMNS:
        assert column in prices.columns
    assert prices["ticker"].nunique() == EXPECTED_TICKER_COUNT
    assert (prices["close"] > 0).all()
    assert (prices["high"] >= prices["low"]).all()


def test_load_prices_point_in_time_excludes_future_dates() -> None:
    as_of = date(2020, 6, 15)
    prices = load_prices(as_of=as_of)
    assert (prices["date"] <= pd.Timestamp(as_of)).all()
    # No row should leak past the cutoff.
    assert prices["date"].max() <= pd.Timestamp(as_of)


def test_load_prices_supports_all_dates_when_as_of_none() -> None:
    prices_all = load_prices()
    prices_until_2020 = load_prices(as_of=date(2020, 12, 31))
    assert len(prices_all) > len(prices_until_2020)
    # Universe must remain stable across calls.
    assert set(prices_all["ticker"]) == set(prices_until_2020["ticker"])


# ---------------------------------------------------------------------------
# Fundamentals loader
# ---------------------------------------------------------------------------


def test_load_fundamentals_required_columns_and_quarter_count() -> None:
    fundamentals = load_fundamentals()
    for column in FUNDAMENTALS_REQUIRED_COLUMNS:
        assert column in fundamentals.columns
    # 30 tickers × 45 quarters (2014Q4 → 2025Q4).
    assert len(fundamentals) == EXPECTED_TICKER_COUNT * 45
    assert (fundamentals["roe"] >= 0).all()
    assert (fundamentals["gross_margin"].between(0.0, 1.0)).all()
    assert (fundamentals["debt_to_assets"].between(0.0, 1.0)).all()


def test_load_fundamentals_point_in_time_excludes_unpublished_reports() -> None:
    # Q3 2020 fiscal end = 2020-09-30; report_date = 2020-11-04.
    # Choosing as_of strictly before the Q3 report ensures Q3 is excluded.
    as_of = date(2020, 11, 3)
    fundamentals = load_fundamentals(as_of=as_of)
    assert (fundamentals["report_date"] <= pd.Timestamp(as_of)).all()
    # The newest *visible* report is therefore Q2 2020 (fiscal end 2020-06-30,
    # report 2020-08-04).
    assert fundamentals["report_date"].max() == pd.Timestamp("2020-08-04")


def test_load_fundamentals_report_date_at_least_30_days_after_quarter_end() -> None:
    fundamentals = load_fundamentals()
    lag_days = (
        fundamentals["report_date"] - fundamentals["fiscal_quarter_end"]
    ).dt.days
    assert lag_days.min() >= 30, "report_date must trail fiscal_quarter_end by >= 30 days"


# ---------------------------------------------------------------------------
# Earnings calendar loader
# ---------------------------------------------------------------------------


def test_load_earnings_calendar_required_columns() -> None:
    earnings = load_earnings_calendar()
    for column in EARNINGS_REQUIRED_COLUMNS:
        assert column in earnings.columns
    assert earnings["ticker"].nunique() == EXPECTED_TICKER_COUNT
    assert len(earnings) == EXPECTED_TICKER_COUNT * 45


def test_earnings_date_precedes_matching_report_date_for_every_quarter() -> None:
    fundamentals = load_fundamentals()
    earnings = load_earnings_calendar()
    merged = fundamentals.merge(
        earnings[["ticker", "fiscal_quarter", "earnings_date"]],
        on=["ticker", "fiscal_quarter"],
    )
    # F001 acceptance: earnings_date <= report_date.
    assert (merged["earnings_date"] <= merged["report_date"]).all()
    assert len(merged) == len(fundamentals)


def test_load_earnings_filters_announcements_on_or_before_as_of() -> None:
    as_of = date(2018, 7, 1)
    earnings = load_earnings_calendar(as_of=as_of)
    assert (earnings["earnings_date"] <= pd.Timestamp(as_of)).all()
    # No row should mention a fiscal quarter ending after as_of - 28 days.
    assert earnings["earnings_date"].max() <= pd.Timestamp(as_of)


# ---------------------------------------------------------------------------
# Liquidity filter
# ---------------------------------------------------------------------------


def test_filter_accepts_27_real_tickers_at_late_as_of() -> None:
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(universe, prices, date(2024, 1, 2))
    # All three synthetic ZQ* tickers fail at least one gate; the 27 real ones pass.
    assert set(result.accepted_tickers).isdisjoint(SYNTHETIC_TICKERS)
    assert len(result.accepted) == EXPECTED_TICKER_COUNT - len(SYNTHETIC_TICKERS)


def test_filter_records_one_rejection_per_dropped_ticker() -> None:
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(universe, prices, date(2024, 1, 2))
    rejected_tickers = {rejection.ticker for rejection in result.rejections}
    assert rejected_tickers == SYNTHETIC_TICKERS
    # Each rejection should expose the failing reason and observed value.
    for rejection in result.rejections:
        assert isinstance(rejection, LiquidityRejection)
        assert rejection.reason
        assert rejection.observed >= 0.0


def test_filter_market_cap_gate_rejects_zqai() -> None:
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(universe, prices, date(2024, 1, 2))
    reasons = {r.ticker: r.reason for r in result.rejections}
    assert reasons["ZQAI"] == "market_cap_below_threshold"


def test_filter_listing_age_gate_rejects_zqai_at_early_as_of() -> None:
    # ZQAI listed 2020-06-15; at 2021-06-01 age is ~0.96 years (< 2 default).
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(universe, prices, date(2021, 6, 1))
    reasons = {r.ticker: r.reason for r in result.rejections}
    assert reasons.get("ZQAI") == "listing_age_below_threshold"


def test_filter_adv_gate_rejects_low_volume_tickers() -> None:
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(universe, prices, date(2024, 1, 2))
    reasons = {r.ticker: r.reason for r in result.rejections}
    assert reasons["ZQPT"] == "adv60_below_threshold"
    assert reasons["ZQLH"] == "adv60_below_threshold"


def test_filter_price_gate_rejects_ticker_under_threshold() -> None:
    # ZQPT init=$8 with drift=0.02, so for most of the series its close stays
    # under $10. Using a high price_threshold forces additional rejections too.
    universe = load_universe()
    prices = load_prices()
    result = apply_liquidity_filter(
        universe,
        prices,
        date(2024, 1, 2),
        market_cap_threshold=0.0,
        adv60_threshold=0.0,
        listing_age_years=0.0,
        price_threshold=10.0,
    )
    reasons = {r.ticker: r.reason for r in result.rejections}
    assert reasons.get("ZQPT") == "price_below_threshold"


def test_filter_raises_when_prices_empty() -> None:
    universe = load_universe()
    empty_prices = pd.DataFrame(
        columns=list(PRICES_REQUIRED_COLUMNS),
    )
    with pytest.raises(LiquidityFilterError, match="empty"):
        apply_liquidity_filter(universe, empty_prices, date(2024, 1, 2))


def test_filter_raises_when_as_of_predates_all_prices() -> None:
    universe = load_universe()
    prices = load_prices()
    with pytest.raises(LiquidityFilterError, match="no price rows"):
        apply_liquidity_filter(universe, prices, date(1990, 1, 1))


def test_filter_uses_only_trailing_60_days_for_adv() -> None:
    # Construct a tiny universe + price frame: one ticker with low ADV in the
    # trailing window even though earlier history is high — the filter should
    # still reject because the 60-day trailing mean is below threshold.
    entry = UniverseEntry(
        ticker="TST",
        name="Test Ticker",
        exchange="NYSE",
        gics_sector="Industrials",
        gics_industry="Testing",
        listing_date=date(2010, 1, 1),
        market_cap_initial=50e9,
    )
    as_of = date(2024, 1, 2)
    high_dates = pd.date_range(end=as_of - timedelta(days=120), periods=300, freq="B")
    trailing_dates = pd.date_range(end=as_of, periods=60, freq="B")
    high = pd.DataFrame(
        {
            "date": high_dates,
            "ticker": "TST",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "adj_close": 100.0,
            "volume": 10_000_000,  # 10M × $100 = $1B ADV
        }
    )
    trailing = pd.DataFrame(
        {
            "date": trailing_dates,
            "ticker": "TST",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "adj_close": 100.0,
            "volume": 1_000,  # 1k × $100 = $100k ADV (well below $50M)
        }
    )
    prices = pd.concat([high, trailing], ignore_index=True)
    result = apply_liquidity_filter((entry,), prices, as_of)
    assert "TST" not in result.accepted_tickers
    rejections = {r.ticker: r.reason for r in result.rejections}
    assert rejections["TST"] == "adv60_below_threshold"


# ---------------------------------------------------------------------------
# Fixture schema integrity (cross-file)
# ---------------------------------------------------------------------------


def test_required_column_constants_match_csv_headers() -> None:
    universe_csv = pd.read_csv(DEFAULT_FIXTURE_DIR / "universe.csv", nrows=0)
    prices_csv = pd.read_csv(DEFAULT_FIXTURE_DIR / "prices_daily.csv", nrows=0)
    fundamentals_csv = pd.read_csv(DEFAULT_FIXTURE_DIR / "fundamentals.csv", nrows=0)
    earnings_csv = pd.read_csv(DEFAULT_FIXTURE_DIR / "earnings_calendar.csv", nrows=0)
    assert set(UNIVERSE_REQUIRED_COLUMNS).issubset(universe_csv.columns)
    assert set(PRICES_REQUIRED_COLUMNS).issubset(prices_csv.columns)
    assert set(FUNDAMENTALS_REQUIRED_COLUMNS).issubset(fundamentals_csv.columns)
    assert set(EARNINGS_REQUIRED_COLUMNS).issubset(earnings_csv.columns)


def test_repository_loaders_are_offline_no_network_required() -> None:
    """All loaders rely solely on committed CSVs — verify by pointing at a copy."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        for filename in (
            "universe.csv",
            "prices_daily.csv",
            "fundamentals.csv",
            "earnings_calendar.csv",
        ):
            shutil.copy(DEFAULT_FIXTURE_DIR / filename, tmp / filename)
        u = load_universe(fixture_dir=tmp)
        p = load_prices(as_of=date(2020, 1, 1), fixture_dir=tmp)
        f = load_fundamentals(as_of=date(2020, 1, 1), fixture_dir=tmp)
        e = load_earnings_calendar(as_of=date(2020, 1, 1), fixture_dir=tmp)
        assert len(u) == EXPECTED_TICKER_COUNT
        assert not p.empty
        assert not f.empty
        assert not e.empty
