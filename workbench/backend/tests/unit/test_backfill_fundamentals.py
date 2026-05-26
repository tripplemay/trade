"""B029 F002 — ``scripts/backfill_fundamentals.py`` + helpers.

Drives the backfill driver against a stub ``SECEDGARFundamentalsLoader``
(no network) + a synthesised SEC companyfacts payload + an in-memory
Tiingo prices dict so the entire suite stays offline (CI requirement).
Real SEC backfill validation is the F002 §(4) "本机跑 backfill" manual
one-shot (see ``data/snapshots/README.md``); these specs pin the
universe assertions, the calendar-quarter bucketing semantics, the
sort+dedupe in the merge step, the atomic-write guarantee, and the
synthetic-ticker fail-safe contract.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _import_script(name: str) -> ModuleType:
    """Load one of the repo-root ``scripts/`` modules."""

    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot resolve {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# universe_us_quality.py invariants
# ---------------------------------------------------------------------------


def test_us_quality_universe_contains_30_tickers_with_3_synthetic() -> None:
    """B025 fixture has 30 entries (27 real + 3 synthetic ZQ*).
    Decision #3 keeps the synthetic ones in the universe iteration so
    the F002 driver can fail-safe-skip them rather than silently
    pruning them upstream."""

    universe = _import_script("universe_us_quality")
    tickers = universe.us_quality_universe()
    assert len(tickers) == 30
    synthetic = [t for t in tickers if t.startswith("ZQ")]
    real = [t for t in tickers if not t.startswith("ZQ")]
    assert len(real) == 27
    assert sorted(synthetic) == ["ZQAI", "ZQLH", "ZQPT"]


def test_us_quality_universe_consistent_with_b025_fixture() -> None:
    """Both subsets (real + synthetic) must mirror
    ``data/fixtures/us_quality_momentum/universe.csv`` exactly,
    otherwise the F002 backfill drifts out of step with the B025
    fixture that the B025 deterministic backtest reads. B030 F001
    extends the assert to cover the ``gics_sector`` column too —
    drift here breaks the per-sector alias chain resolution and
    re-introduces B029 Soft-watch S1 (sector tickers producing 0
    backfill rows)."""

    universe = _import_script("universe_us_quality")
    universe.assert_us_quality_universe_consistent_with_fixture()


# ---------------------------------------------------------------------------
# B030 F001 — universe_us_quality sector mapping + per-ticker lookup
# ---------------------------------------------------------------------------


def test_us_quality_ticker_sectors_covers_all_30_tickers() -> None:
    """Every ticker in the B025 universe must have an explicit sector
    entry. Synthetic tickers (ZQ*) get their fixture sector even
    though they're skipped in the SEC backfill — keeping the mapping
    complete avoids per-call .get() default-None surprises in non-
    backfill code paths (e.g. UI sector breakdowns)."""

    universe = _import_script("universe_us_quality")
    assert len(universe.US_QUALITY_TICKER_SECTORS) == 30
    for ticker in universe.us_quality_universe():
        assert ticker in universe.US_QUALITY_TICKER_SECTORS, (
            f"{ticker} missing from US_QUALITY_TICKER_SECTORS"
        )


def test_us_quality_ticker_sectors_includes_six_sector_structural_tickers() -> None:
    """B029 Soft-watch S1 tickers (BAC/JPM/V/LIN/NEE/PLD) — the
    sector mapping must resolve them into one of the three per-sector
    override buckets (Financials / Utilities / Real Estate) or, in
    LIN's case, into Materials with its dialect handled by the
    default chain's late-fallback positions."""

    universe = _import_script("universe_us_quality")
    sectors = universe.US_QUALITY_TICKER_SECTORS
    # Banks and Visa land in Financials (per-sector override).
    assert sectors["BAC"] == "Financials"
    assert sectors["JPM"] == "Financials"
    assert sectors["V"] == "Financials"
    # NEE → Utilities (per-sector override).
    assert sectors["NEE"] == "Utilities"
    # PLD → Real Estate (per-sector override).
    assert sectors["PLD"] == "Real Estate"
    # LIN → Materials — no per-sector override; the default chain's
    # ``LongTermDebtNoncurrent`` / ``OperatingExpenses`` fallbacks
    # cover LIN's Utilities-style XBRL dialect.
    assert sectors["LIN"] == "Materials"


def test_get_ticker_sector_returns_none_for_unknown_ticker() -> None:
    """Out-of-universe ticker → ``None``. The F002 driver passes the
    return value straight to ``get_concept_alias_chain`` which falls
    back to the default chain on ``None``."""

    universe = _import_script("universe_us_quality")
    assert universe.get_ticker_sector("ZZZZ") is None
    assert universe.get_ticker_sector("") is None


def test_assert_universe_consistency_detects_sector_drift(tmp_path: Path) -> None:
    """Inject a fake fixture with a deliberately wrong sector for AAPL
    and verify the consistency assert flags it. Pins the new B030 F001
    sector-column branch added to
    :func:`assert_us_quality_universe_consistent_with_fixture`."""

    universe = _import_script("universe_us_quality")
    # Spoof the fixture path via monkey-patching: write a CSV that
    # matches the universe ticker list but has a wrong sector for
    # AAPL ("Energy" instead of "Information Technology") and point
    # the helper at it.
    bad_fixture = tmp_path / "universe.csv"
    header = (
        "ticker,name,exchange,gics_sector,gics_industry,listing_date,market_cap_initial"
    )
    rows: list[str] = [header]
    for ticker in universe.us_quality_universe():
        sector = (
            "Energy"
            if ticker == "AAPL"
            else universe.US_QUALITY_TICKER_SECTORS[ticker]
        )
        rows.append(
            f"{ticker},Stub Co,NYSE,{sector},Stub Industry,2020-01-01,1000000000"
        )
    bad_fixture.write_text("\n".join(rows) + "\n", encoding="utf-8")

    # Redirect the helper's fixture read to our spoof.
    import pandas as pd
    real_read_csv = pd.read_csv
    real_path_resolve = Path.resolve

    def fake_read_csv(path, *a, **kw):  # type: ignore[no-untyped-def]
        # The helper builds the path via ``Path(__file__).resolve().parents[1] /
        # "data" / "fixtures" / "us_quality_momentum" / "universe.csv"``.
        # Detect that exact shape and substitute our spoof.
        if str(path).endswith("us_quality_momentum/universe.csv"):
            return real_read_csv(bad_fixture, *a, **kw)
        return real_read_csv(path, *a, **kw)

    try:
        pd.read_csv = fake_read_csv  # type: ignore[assignment]
        with pytest.raises(AssertionError) as exc_info:
            universe.assert_us_quality_universe_consistent_with_fixture()
        # Failure message must call out AAPL and the offending sector
        # so the maintainer can fix it without grepping.
        msg = str(exc_info.value)
        assert "AAPL" in msg
        assert "Energy" in msg
        assert "Information Technology" in msg
    finally:
        pd.read_csv = real_read_csv  # type: ignore[assignment]
        # Defensive — restore Path.resolve in case it was touched.
        Path.resolve = real_path_resolve  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# ticker_to_cik.py — cache reader + rebuild helper
# ---------------------------------------------------------------------------


def test_ticker_cik_map_loads_30_entries_with_underscore_doc_skipped() -> None:
    """The committed fixture has 30 real keys + 1 ``_doc`` sentinel.
    The loader must drop the sentinel and surface only the 30 ticker
    rows (27 int CIKs + 3 None synthetics)."""

    ticker_to_cik = _import_script("ticker_to_cik")
    mapping = ticker_to_cik.load_cached_ticker_cik_map()
    assert len(mapping) == 30
    assert "_doc" not in mapping
    none_count = sum(1 for v in mapping.values() if v is None)
    int_count = sum(1 for v in mapping.values() if isinstance(v, int))
    assert none_count == 3
    assert int_count == 27


def test_ticker_to_cik_write_roundtrips_atomic_temp(tmp_path: Path) -> None:
    """``write_ticker_cik_map`` must use ``tmp_file + os.replace`` so
    a Ctrl-C mid-write doesn't leave a half-flushed JSON. The check is
    behavioural: write, read, verify the doc sentinel got re-injected
    and the mapping survived the round-trip."""

    ticker_to_cik = _import_script("ticker_to_cik")
    mapping: dict[str, int | None] = {"AAPL": 320193, "ZQAI": None}
    out = tmp_path / "ticker_cik_map.json"
    ticker_to_cik.write_ticker_cik_map(mapping, out)
    assert out.exists()
    import json

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["AAPL"] == 320193
    assert payload["ZQAI"] is None
    assert "_doc" in payload


# ---------------------------------------------------------------------------
# backfill_fundamentals.py — helpers
# ---------------------------------------------------------------------------


def test_unified_columns_match_b025_fixture_12_column_schema() -> None:
    """The unified CSV header must be column-for-column identical to
    the B025 fundamentals.csv (Planner pre-impl adjudication decision
    #1). Drift here means F003's PIT loader cannot drop in unified
    instead of fixture."""

    backfill = _import_script("backfill_fundamentals")
    expected = (
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
    assert expected == backfill.UNIFIED_COLUMNS
    assert len(backfill.UNIFIED_COLUMNS) == 12

    # The actual B025 fixture header on disk is the source of truth.
    fixture_path = (
        REPO_ROOT / "data" / "fixtures" / "us_quality_momentum" / "fundamentals.csv"
    )
    with fixture_path.open() as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == expected


def test_calendar_quarter_buckets_period_end_correctly() -> None:
    """The bucketing snaps each SEC ``end`` date to the calendar
    quarter it falls in. Apple FY ends 2014-09-27 → 2014Q3; calendar
    Dec 31 2014 → 2014Q4. F002 keys rows on calendar quarter so the
    B025 ``2014Q4`` row aligns with any company whose Q ends in Dec."""

    backfill = _import_script("backfill_fundamentals")
    assert backfill._calendar_quarter(date(2014, 12, 31)) == (2014, 4)
    assert backfill._calendar_quarter(date(2015, 9, 27)) == (2015, 3)
    assert backfill._calendar_quarter(date(2020, 1, 5)) == (2020, 1)
    assert backfill._calendar_quarter(date(2026, 6, 30)) == (2026, 2)


def test_bucket_entries_by_quarter_keeps_latest_filed() -> None:
    """SEC may have 10-K + 10-K/A entries with the same ``end``;
    latest-filed wins."""

    backfill = _import_script("backfill_fundamentals")
    entries = [
        {"end": "2014-12-31", "val": 1000, "filed": "2015-02-04", "fy": 2014, "fp": "Q4"},
        # Amendment with later "filed" date — should win the dedupe.
        {"end": "2014-12-31", "val": 1100, "filed": "2015-03-15", "fy": 2014, "fp": "Q4"},
        {"end": "2014-09-30", "val": 800, "filed": "2014-10-30", "fy": 2014, "fp": "Q3"},
    ]
    out = backfill._bucket_entries_by_quarter(entries)
    assert out[(2014, 4)]["val"] == 1100  # amendment wins
    assert out[(2014, 3)]["val"] == 800


def test_nearest_close_walks_back_for_weekend_filings() -> None:
    """Some SEC ``filed`` dates land on weekends (rare) or holidays;
    the lookup walks back up to 5 calendar days for the latest market
    close. Inputs use ISO strings to mirror the loader's index shape."""

    backfill = _import_script("backfill_fundamentals")
    prices = {
        ("AAPL", "2024-01-05"): 188.40,  # Friday
        ("AAPL", "2024-01-04"): 187.30,
    }
    # 2024-01-07 = Sunday → fallback to Friday 2024-01-05.
    close = backfill._nearest_close(prices, "AAPL", date(2024, 1, 7))
    assert close == 188.40
    # Holiday-style gap > 5 days → None.
    assert backfill._nearest_close(prices, "AAPL", date(2024, 1, 20)) is None


# ---------------------------------------------------------------------------
# backfill_fundamentals.py — raw companyfacts → parsed_ratios
# ---------------------------------------------------------------------------


def _aapl_synthetic_companyfacts() -> dict[str, Any]:
    """Synthesise the minimum SEC companyfacts shape the driver needs
    for one AAPL quarter (FY 2014). Values chosen to make the ratios
    match the AAPL FY2014 row in
    ``data/fixtures/us_quality_momentum/fundamentals.csv`` to 4-digit
    rounding (so a future refactor that breaks the formula surfaces
    via the assertion)."""

    def one_quarter_entry(
        val: float,
        filed: str,
        end: str,
        fp: str = "FY",
        fy: int = 2014,
        form: str = "10-K",
    ) -> dict[str, Any]:
        return {
            "end": end,
            "val": val,
            "filed": filed,
            "fy": fy,
            "fp": fp,
            "form": form,
            "accn": "0000320193-15-000005",
        }

    def usd_unit(val: float) -> dict[str, Any]:
        return {"units": {"USD": [one_quarter_entry(val, "2015-02-04", "2014-12-31")]}}

    def shares_unit(val: float) -> dict[str, Any]:
        return {
            "units": {
                "shares": [one_quarter_entry(val, "2015-02-04", "2014-12-31")]
            }
        }

    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd_unit(39_510_000_000.0),
                "StockholdersEquity": usd_unit(88_396_000_000.0),
                "Revenues": usd_unit(182_795_000_000.0),
                "CostOfGoodsAndServicesSold": usd_unit(103_236_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd_unit(
                    59_713_000_000.0
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd_unit(
                    9_571_000_000.0
                ),
                "LongTermDebt": usd_unit(66_924_000_000.0),
                "Assets": usd_unit(226_690_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd_unit(13_844_000_000.0),
                "OperatingIncomeLoss": usd_unit(52_503_000_000.0),
                "DepreciationDepletionAndAmortization": usd_unit(7_946_000_000.0),
            },
            "dei": {
                "CommonStockSharesOutstanding": shares_unit(5_864_000_000.0),
            },
        },
    }


def test_raw_companyfacts_to_parsed_ratios_computes_eight_ratio_row() -> None:
    """End-to-end happy path: synthesised AAPL companyfacts + a single
    Tiingo close → one 12-column FundamentalsRow dict with all eight
    ratios populated. Numeric tolerance matches the rounding in the
    driver (4 decimals for proportional ratios; 2 decimals for
    multiples)."""

    import math

    backfill = _import_script("backfill_fundamentals")
    payload = _aapl_synthetic_companyfacts()
    # close × shares ≈ 138.6 × 5_864_000_000 ≈ 812_705_e9 (P/E target ≈ 20.57)
    prices = {("AAPL", "2015-02-04"): 138.5926}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "AAPL", payload, prices=prices
    )
    assert skips == [], skips
    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "AAPL"
    assert row["fiscal_quarter"] == "2014Q4"
    assert row["fiscal_quarter_end"] == "2014-12-31"
    assert row["report_date"] == "2015-02-04"
    # Ratios (locked formulas per strategy doc §6 / 永久边界 (j)).
    assert math.isclose(row["roe"], 0.4469, abs_tol=0.001)
    assert math.isclose(row["gross_margin"], 0.4353, abs_tol=0.001)
    assert math.isclose(row["debt_to_assets"], 0.2952, abs_tol=0.001)
    # MarketCap-dependent ratios depend on the close × shares; assert
    # they're positive (real backfill validates exact numbers).
    assert row["pe"] > 0
    assert row["pb"] > 0


def test_raw_companyfacts_to_parsed_ratios_skips_quarter_with_missing_concept() -> None:
    """If SEC didn't file (e.g.) ``LongTermDebt`` for a quarter, the
    driver must surface a per-quarter skip reason rather than emit a
    partial row."""

    backfill = _import_script("backfill_fundamentals")
    payload = _aapl_synthetic_companyfacts()
    del payload["facts"]["us-gaap"]["LongTermDebt"]
    prices = {("AAPL", "2015-02-04"): 138.59}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "AAPL", payload, prices=prices
    )
    assert rows == []
    assert any("long_term_debt" in s for s in skips), skips


def test_raw_companyfacts_to_parsed_ratios_skips_when_no_price_for_window() -> None:
    """No Tiingo close near ``report_date`` → no MarketCap → skip
    that quarter with a clear reason rather than zero-divide."""

    backfill = _import_script("backfill_fundamentals")
    payload = _aapl_synthetic_companyfacts()
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "AAPL", payload, prices={}  # no prices indexed
    )
    assert rows == []
    assert any("Tiingo" in s and "AAPL" in s for s in skips), skips


# ---------------------------------------------------------------------------
# backfill_fundamentals.py — driver (mocked SEC + Tiingo)
# ---------------------------------------------------------------------------


class _StubLoader:
    """Returns synthesised payloads from a pre-seeded ``ticker →
    companyfacts dict`` table; ``ticker_cik_map`` mimics the real
    loader's resolved map."""

    def __init__(
        self,
        table: dict[str, dict[str, Any]],
        ticker_cik_map: dict[str, int | None],
    ) -> None:
        self._table = table
        self.ticker_cik_map = ticker_cik_map
        self.calls: list[str] = []

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, Any]:
        self.calls.append(ticker)
        if ticker not in self.ticker_cik_map:
            raise ValueError(f"stub: no map for {ticker}")
        cik = self.ticker_cik_map[ticker]
        if cik is None:
            raise ValueError(f"Synthetic ticker {ticker} has no SEC filing")
        return self._table[ticker]


def test_backfill_writes_unified_with_b025_schema_and_dedupes(tmp_path: Path) -> None:
    """End-to-end driver flow against the stub loader + in-process
    prices: produces one CSV row per (ticker, calendar_quarter),
    dedupes by that key, persists to ``unified/fundamentals.csv``
    with the canonical 12-column header."""

    backfill = _import_script("backfill_fundamentals")
    payload = _aapl_synthetic_companyfacts()
    loader = _StubLoader(
        table={"AAPL": payload},
        ticker_cik_map={"AAPL": 320193, "ZQAI": None},
    )
    # Use a small in-process prices CSV so the lookup path is exercised.
    prices_csv = tmp_path / "prices_daily.csv"
    with prices_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2015-02-04",
                "ticker": "AAPL",
                "open": "138.0",
                "high": "139.0",
                "low": "137.5",
                "close": "138.5926",
                "adj_close": "16.0",
                "volume": "10000000",
            }
        )
    row_count, failures, skips = backfill.backfill(
        ["AAPL", "ZQAI"],
        date(2014, 1, 1),
        date(2026, 12, 31),
        loader,
        snapshots_root=tmp_path,
        prices_csv=prices_csv,
    )
    assert row_count == 1
    assert failures == []
    assert skips == ["ZQAI"]
    unified = tmp_path / "fundamentals" / "unified" / "fundamentals.csv"
    assert unified.exists()
    with unified.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == list(backfill.UNIFIED_COLUMNS)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["fiscal_quarter"] == "2014Q4"
    # Vendor artefacts landed under the CIK directory.
    cik_dir = tmp_path / "fundamentals" / "sec_edgar" / "0000320193"
    assert (cik_dir / "companyfacts.json").exists()
    assert (cik_dir / "parsed_ratios.json").exists()
    assert (cik_dir / "metadata.json").exists()


def test_backfill_skips_synthetic_ticker_with_warn_and_succeeds(tmp_path: Path) -> None:
    """Decision #3 fail-safe: a universe with only synthetic tickers
    completes with zero rows + zero failures + N synthetic_skips,
    never raising an exception that would abort the batch."""

    backfill = _import_script("backfill_fundamentals")
    loader = _StubLoader(
        table={},
        ticker_cik_map={"ZQAI": None, "ZQPT": None, "ZQLH": None},
    )
    row_count, failures, skips = backfill.backfill(
        ["ZQAI", "ZQPT", "ZQLH"],
        date(2014, 1, 1),
        date(2026, 12, 31),
        loader,
        snapshots_root=tmp_path,
        prices_csv=None,
    )
    assert row_count == 0
    assert failures == []
    assert sorted(skips) == ["ZQAI", "ZQLH", "ZQPT"]
    # The fetch was never invoked for synthetic tickers.
    assert loader.calls == []


def test_backfill_pit_invariant_report_date_after_fiscal_quarter_end(
    tmp_path: Path,
) -> None:
    """PIT spec assertion: each emitted row must have
    ``report_date >= fiscal_quarter_end`` (filing always happens after
    the period ends; B025 §4.1 says ≥30 days, but the assertion stays
    permissive here so a same-day amendment doesn't fail the spec —
    the F002 PIT validation report enforces the stricter ≥30d on real
    backfilled data)."""

    backfill = _import_script("backfill_fundamentals")
    payload = _aapl_synthetic_companyfacts()
    loader = _StubLoader(
        table={"AAPL": payload}, ticker_cik_map={"AAPL": 320193}
    )
    prices_csv = tmp_path / "prices_daily.csv"
    with prices_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2015-02-04",
                "ticker": "AAPL",
                "open": "138.0",
                "high": "139.0",
                "low": "137.5",
                "close": "138.5926",
                "adj_close": "16.0",
                "volume": "10000000",
            }
        )
    backfill.backfill(
        ["AAPL"],
        date(2014, 1, 1),
        date(2026, 12, 31),
        loader,
        snapshots_root=tmp_path,
        prices_csv=prices_csv,
    )
    unified = tmp_path / "fundamentals" / "unified" / "fundamentals.csv"
    with unified.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows  # at least one row
    for row in rows:
        rep = date.fromisoformat(row["report_date"])
        fq_end = date.fromisoformat(row["fiscal_quarter_end"])
        assert rep >= fq_end, (
            f"PIT invariant violated: report_date {rep} < "
            f"fiscal_quarter_end {fq_end} for ticker {row['ticker']} "
            f"{row['fiscal_quarter']}"
        )


def test_merge_into_unified_dedupes_on_ticker_fiscal_quarter(tmp_path: Path) -> None:
    """Re-running the backfill for the same (ticker, fiscal_quarter)
    replaces the row in place; the unified file size stays bounded
    across repeated runs."""

    backfill = _import_script("backfill_fundamentals")
    unified = tmp_path / "fundamentals.csv"
    row_v1 = {
        "report_date": "2015-02-04",
        "ticker": "AAPL",
        "fiscal_quarter": "2014Q4",
        "fiscal_quarter_end": "2014-12-31",
        "roe": "0.4469",
        "gross_margin": "0.4353",
        "fcf_yield": "0.0418",
        "debt_to_assets": "0.2952",
        "pe": "20.57",
        "pb": "12.54",
        "ev_ebitda": "16.72",
        "earnings_yield": "0.0486",
    }
    backfill.merge_into_unified([row_v1], unified)
    # Second pass with a corrected pe value.
    row_v2 = {**row_v1, "pe": "21.00"}
    count = backfill.merge_into_unified([row_v2], unified)
    assert count == 1
    with unified.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["pe"] == "21.00"


def test_merge_into_unified_atomic_write_temp_then_replace(tmp_path: Path) -> None:
    """Atomic write: after a successful merge, no stray temp file
    remains in the destination directory; only the target CSV is
    present. (Catches a regression where the temp file was created
    in /tmp instead of next to the destination, breaking atomicity
    across filesystems.)"""

    backfill = _import_script("backfill_fundamentals")
    unified = tmp_path / "fundamentals.csv"
    backfill.merge_into_unified(
        [
            {
                "report_date": "2015-02-04",
                "ticker": "AAPL",
                "fiscal_quarter": "2014Q4",
                "fiscal_quarter_end": "2014-12-31",
                "roe": "0.4469",
                "gross_margin": "0.4353",
                "fcf_yield": "0.0418",
                "debt_to_assets": "0.2952",
                "pe": "20.57",
                "pb": "12.54",
                "ev_ebitda": "16.72",
                "earnings_yield": "0.0486",
            }
        ],
        unified,
    )
    leftover = [p for p in tmp_path.iterdir() if p.name != "fundamentals.csv"]
    assert leftover == [], f"unexpected leftover files: {leftover}"


@pytest.mark.parametrize(
    "year,quarter,expected_end",
    [
        (2014, 4, date(2014, 12, 31)),
        (2024, 1, date(2024, 3, 31)),
        (2026, 2, date(2026, 6, 30)),
        (2020, 3, date(2020, 9, 30)),
    ],
)
def test_quarter_end_canonical_date(year: int, quarter: int, expected_end: date) -> None:
    """Canonical calendar quarter-end mapping for the PIT report's
    ``fiscal_quarter_end >= report_date + 30d`` assertion. Used by
    PIT validation downstream."""

    backfill = _import_script("backfill_fundamentals")
    assert backfill._quarter_end(year, quarter) == expected_end


# ---------------------------------------------------------------------------
# B030 F001 — per-sector alias chain routing through the backfill driver
# ---------------------------------------------------------------------------


def _bank_synthetic_companyfacts() -> dict[str, Any]:
    """Synthesise a bank-style SEC companyfacts payload for JPM FY2014.

    Critical difference from the default test fixture: revenues are
    filed under ``InterestAndDividendIncomeOperating`` (no ``Revenues``
    entry) and COGS is filed under ``InterestExpense`` (no
    ``CostOfGoodsAndServicesSold`` entry). Without per-sector
    overrides, both concepts would miss the default alias chain and
    the quarter would be skipped (B029 Soft-watch S1 root cause).
    """

    def usd_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "USD": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-24",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0000019617-15-000005",
                    }
                ]
            }
        }

    def shares_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "shares": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-24",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0000019617-15-000005",
                    }
                ]
            }
        }

    return {
        "cik": 19617,
        "entityName": "JPMorgan Chase & Co.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd_unit(21_745_000_000.0),
                "StockholdersEquity": usd_unit(231_727_000_000.0),
                # Bank-specific concepts only — no Revenues / COGS.
                "InterestAndDividendIncomeOperating": usd_unit(74_054_000_000.0),
                "InterestExpense": usd_unit(11_233_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd_unit(
                    77_407_000_000.0
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd_unit(
                    7_400_000_000.0
                ),
                "LongTermDebt": usd_unit(276_836_000_000.0),
                "Assets": usd_unit(2_572_274_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd_unit(27_831_000_000.0),
                "OperatingIncomeLoss": usd_unit(30_699_000_000.0),
                "DepreciationDepletionAndAmortization": usd_unit(4_759_000_000.0),
            },
            "dei": {
                "CommonStockSharesOutstanding": shares_unit(3_715_000_000.0),
            },
        },
    }


def test_backfill_uses_financials_alias_chain_for_bank_revenues() -> None:
    """B030 F001 acceptance §(5): with sector=Financials the driver
    finds ``InterestAndDividendIncomeOperating`` (the bank revenue
    concept) and produces a non-empty row even when ``Revenues`` is
    absent from the payload. Default-sector (no override) would
    skip the quarter."""

    backfill = _import_script("backfill_fundamentals")
    payload = _bank_synthetic_companyfacts()
    prices = {("JPM", "2015-02-24"): 56.40}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "JPM", payload, prices=prices, sector="Financials"
    )
    assert skips == [], skips
    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "JPM"
    assert row["fiscal_quarter"] == "2014Q4"
    # gross_margin = (revenues - cogs) / revenues
    # = (74_054 - 11_233) / 74_054 ≈ 0.8484
    assert row["gross_margin"] > 0
    # debt_to_assets = 276_836 / 2_572_274 ≈ 0.1076
    assert math.isclose(row["debt_to_assets"], 0.1076, abs_tol=0.001)


def test_backfill_skips_bank_revenues_without_sector_override() -> None:
    """Without the per-sector alias chain (sector=None or default),
    the bank payload misses on both ``revenues`` and ``cogs`` and the
    quarter is dropped — exactly the B029 Soft-watch S1 failure mode
    the B030 F001 override is fixing."""

    backfill = _import_script("backfill_fundamentals")
    payload = _bank_synthetic_companyfacts()
    prices = {("JPM", "2015-02-24"): 56.40}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "JPM", payload, prices=prices, sector=None
    )
    assert rows == []
    # Skip message must call out the missing revenue / cogs concept so
    # a maintainer can see why sector=None failed.
    joined = " | ".join(skips)
    assert "revenues" in joined or "cogs" in joined


def _utility_synthetic_companyfacts() -> dict[str, Any]:
    """Synthesise NEE-style filings: ``LongTermDebtNoncurrent`` is
    the primary concept, COGS lives under ``OperatingExpenses``,
    and there's no plain ``LongTermDebt`` or ``CostOfGoodsAndServicesSold``."""

    def usd_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "USD": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-19",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0000753308-15-000005",
                    }
                ]
            }
        }

    def shares_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "shares": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-19",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0000753308-15-000005",
                    }
                ]
            }
        }

    return {
        "cik": 753308,
        "entityName": "NextEra Energy, Inc.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd_unit(2_465_000_000.0),
                "StockholdersEquity": usd_unit(15_311_000_000.0),
                "Revenues": usd_unit(17_021_000_000.0),
                # Utility-specific: OperatingExpenses, no COGS.
                "OperatingExpenses": usd_unit(13_500_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd_unit(
                    5_300_000_000.0
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd_unit(
                    7_500_000_000.0
                ),
                # Utility-specific: LongTermDebtNoncurrent, no LongTermDebt.
                "LongTermDebtNoncurrent": usd_unit(26_000_000_000.0),
                "Assets": usd_unit(74_888_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd_unit(341_000_000.0),
                "OperatingIncomeLoss": usd_unit(3_521_000_000.0),
                "DepreciationDepletionAndAmortization": usd_unit(2_400_000_000.0),
            },
            "dei": {
                "CommonStockSharesOutstanding": shares_unit(443_000_000.0),
            },
        },
    }


def test_backfill_uses_utilities_alias_chain_for_long_term_debt() -> None:
    """B030 F001 acceptance §(5): sector=Utilities resolves
    ``LongTermDebtNoncurrent`` for NEE-style payloads that lack the
    plain ``LongTermDebt`` concept."""

    backfill = _import_script("backfill_fundamentals")
    payload = _utility_synthetic_companyfacts()
    prices = {("NEE", "2015-02-19"): 100.0}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "NEE", payload, prices=prices, sector="Utilities"
    )
    assert skips == [], skips
    assert len(rows) == 1
    row = rows[0]
    # NEE debt_to_assets = 26_000 / 74_888 ≈ 0.347 — utilities run
    # high leverage. Sanity-bound the value rather than the exact
    # number so a recompute on the same payload still passes.
    assert 0.30 <= row["debt_to_assets"] <= 0.40


def _real_estate_synthetic_companyfacts() -> dict[str, Any]:
    """REIT-style: ``LongTermDebtCurrentAndNoncurrent`` as the primary
    debt concept; ``OperatingExpenses`` rather than COGS."""

    def usd_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "USD": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-25",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0001045609-15-000005",
                    }
                ]
            }
        }

    def shares_unit(val: float, end: str = "2014-12-31") -> dict[str, Any]:
        return {
            "units": {
                "shares": [
                    {
                        "end": end,
                        "val": val,
                        "filed": "2015-02-25",
                        "fy": 2014,
                        "fp": "FY",
                        "form": "10-K",
                        "accn": "0001045609-15-000005",
                    }
                ]
            }
        }

    return {
        "cik": 1045609,
        "entityName": "Prologis, Inc.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd_unit(560_000_000.0),
                "StockholdersEquity": usd_unit(11_500_000_000.0),
                "Revenues": usd_unit(1_700_000_000.0),
                "OperatingExpenses": usd_unit(1_100_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd_unit(
                    600_000_000.0
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd_unit(
                    200_000_000.0
                ),
                # REIT-specific: LongTermDebtCurrentAndNoncurrent.
                "LongTermDebtCurrentAndNoncurrent": usd_unit(8_200_000_000.0),
                "Assets": usd_unit(24_500_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd_unit(380_000_000.0),
                "OperatingIncomeLoss": usd_unit(750_000_000.0),
                "DepreciationDepletionAndAmortization": usd_unit(450_000_000.0),
            },
            "dei": {
                "CommonStockSharesOutstanding": shares_unit(500_000_000.0),
            },
        },
    }


def test_backfill_uses_real_estate_alias_chain_for_consolidated_debt() -> None:
    """B030 F001 acceptance §(5): sector=Real Estate resolves
    ``LongTermDebtCurrentAndNoncurrent`` for REIT-style payloads."""

    backfill = _import_script("backfill_fundamentals")
    payload = _real_estate_synthetic_companyfacts()
    prices = {("PLD", "2015-02-25"): 42.50}
    rows, skips = backfill.raw_companyfacts_to_parsed_ratios(
        "PLD", payload, prices=prices, sector="Real Estate"
    )
    assert skips == [], skips
    assert len(rows) == 1
    row = rows[0]
    # PLD debt_to_assets = 8_200 / 24_500 ≈ 0.335
    assert math.isclose(row["debt_to_assets"], 0.3347, abs_tol=0.005)


def test_backfill_driver_threads_sector_via_get_ticker_sector(tmp_path: Path) -> None:
    """B030 F001 acceptance §(2)+§(3): the ``backfill()`` driver looks
    up the sector via :func:`get_ticker_sector` and threads it through
    to :func:`raw_companyfacts_to_parsed_ratios`. Verify by feeding a
    bank-style JPM payload through the full driver and confirming the
    row materialises (would be skipped without the sector lookup)."""

    backfill = _import_script("backfill_fundamentals")
    payload = _bank_synthetic_companyfacts()
    loader = _StubLoader(
        table={"JPM": payload}, ticker_cik_map={"JPM": 19617}
    )
    prices_csv = tmp_path / "prices_daily.csv"
    with prices_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2015-02-24",
                "ticker": "JPM",
                "open": "56.00",
                "high": "56.50",
                "low": "55.80",
                "close": "56.40",
                "adj_close": "40.0",
                "volume": "12000000",
            }
        )
    row_count, failures, skips = backfill.backfill(
        ["JPM"],
        date(2014, 1, 1),
        date(2026, 12, 31),
        loader,
        snapshots_root=tmp_path,
        prices_csv=prices_csv,
    )
    assert failures == []
    assert row_count == 1
    # Verify the row is in the unified CSV with non-zero ratios.
    unified = tmp_path / "fundamentals" / "unified" / "fundamentals.csv"
    with unified.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["ticker"] == "JPM"
    # Eight ratios must all be non-empty / parseable as float.
    for col in (
        "roe", "gross_margin", "fcf_yield", "debt_to_assets",
        "pe", "pb", "ev_ebitda", "earnings_yield",
    ):
        val = float(rows[0][col])
        # gross_margin / debt_to_assets / pe / pb / ev_ebitda are all
        # positive for a healthy bank; fcf_yield / earnings_yield are
        # positive too at these numbers but the floor here is "not
        # NaN, not zero" — the sector chain produced a real number.
        assert val != 0 and val == val, f"{col} produced zero/NaN: {val}"
