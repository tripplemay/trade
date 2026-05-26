"""B029 F003 — PIT enforcement for ``trade.data.loader.load_fundamentals``.

These specs lock the contract the B030 cutover will rely on:

* Real-data path: when ``data/snapshots/fundamentals/unified/fundamentals.csv``
  exists (produced by ``scripts/backfill_fundamentals.py``), the loader
  reads from it and filters strictly by ``effective_date = report_date
  + 1 business day``.
* Fallback path: when the unified file is absent, the loader reads the
  B025 synthetic fixture (``data/fixtures/us_quality_momentum/fundamentals.csv``).
  This preserves backtest determinism for the six sector-structural
  tickers (BAC/JPM/V/LIN/NEE/PLD) that produce zero rows in the F002
  unified file (see B029 PIT validation report §3).
* No-source path: when both are absent, the loader returns the empty
  dict shape — strategy code never crashes pre-backfill.
* Schema violations raise :class:`FixtureDataError` with a remediation
  pointer so a misshapen CSV is loud, not silent.
* PIT semantics: a row filed on 2019-10-31 (Thursday) becomes visible
  on 2019-11-01 (Friday) — the next business day. A row filed on a
  Friday becomes visible the following Monday.

Each spec patches the loader's module-level path constants via
``monkeypatch`` so the assertions run against a per-test tmp file
without touching the real ``data/snapshots/`` artefacts.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.data import loader as loader_module
from trade.data.loader import (
    FixtureDataError,
    FundamentalsRow,
    load_fundamentals,
)

UNIFIED_COLUMNS = (
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


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=UNIFIED_COLUMNS)
        writer.writeheader()
        for row in rows:
            full = {col: "" for col in UNIFIED_COLUMNS}
            full.update(row)
            writer.writerow(full)


def _aapl_row(
    report_date: str,
    fiscal_quarter: str,
    fiscal_quarter_end: str,
    *,
    ticker: str = "AAPL",
    roe: str = "0.4469",
) -> dict[str, str]:
    """A minimal fundamentals row with sensible defaults — every test
    only cares about the PIT triplet (report_date / fiscal_quarter /
    fiscal_quarter_end) plus the ticker, so the other columns get
    placeholder values that pass the float cast."""

    return {
        "report_date": report_date,
        "ticker": ticker,
        "fiscal_quarter": fiscal_quarter,
        "fiscal_quarter_end": fiscal_quarter_end,
        "roe": roe,
        "gross_margin": "0.4353",
        "fcf_yield": "0.0418",
        "debt_to_assets": "0.2952",
        "pe": "20.57",
        "pb": "12.54",
        "ev_ebitda": "16.72",
        "earnings_yield": "0.0486",
    }


def _seed_unified_csv(path: Path) -> None:
    """Seed a tiny unified file covering 4 quarters of AAPL + 2 of NVDA."""

    _write_csv(
        path,
        [
            # AAPL — 4 quarters in 2019 with report_dates spaced through 2019/2020
            _aapl_row("2019-05-01", "2019Q1", "2019-03-30"),
            _aapl_row("2019-07-31", "2019Q2", "2019-06-29"),
            _aapl_row("2019-10-31", "2019Q3", "2019-09-28"),
            _aapl_row("2020-01-29", "2019Q4", "2019-12-28"),
            # NVDA — 2 quarters; the filing on Friday 2020-02-21 exercises
            # the business-day-add (visible 2020-02-24, next Monday).
            _aapl_row(
                "2020-02-21",
                "2019Q4",
                "2019-10-27",
                ticker="NVDA",
                roe="0.1298",
            ),
            _aapl_row(
                "2019-08-15",
                "2019Q2",
                "2019-07-28",
                ticker="NVDA",
                roe="0.1100",
            ),
        ],
    )


def _patch_paths(
    monkeypatch: pytest.MonkeyPatch,
    *,
    unified: Path | None,
    fixture: Path | None,
) -> None:
    """Override both fundamentals paths so the loader points at our tmp
    files. Either may be ``None`` (file simply non-existent) to
    exercise the fall-back / no-source branches."""

    monkeypatch.setattr(
        loader_module,
        "UNIFIED_FUNDAMENTALS_PATH",
        unified if unified is not None else Path("/nonexistent/unified.csv"),
    )
    monkeypatch.setattr(
        loader_module,
        "B025_FIXTURE_FUNDAMENTALS_PATH",
        fixture if fixture is not None else Path("/nonexistent/fixture.csv"),
    )


# ---------------------------------------------------------------------------
# Real-data unified path + PIT filter
# ---------------------------------------------------------------------------


def test_load_fundamentals_returns_latest_row_visible_at_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AAPL has 4 quarters in the seed file. ``as_of=2020-03-01`` makes
    the 2020-01-29 filing visible (effective 2020-01-30); that row
    (2019Q4) is the latest by ``effective_date`` for AAPL."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    result = load_fundamentals(["AAPL"], date(2020, 3, 1))
    assert isinstance(result["AAPL"], FundamentalsRow)
    assert result["AAPL"].fiscal_quarter == "2019Q4"
    assert result["AAPL"].report_date == date(2020, 1, 29)
    assert result["AAPL"].fiscal_quarter_end == date(2019, 12, 28)


def test_load_fundamentals_pit_drops_rows_filed_after_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``as_of=2019-09-15`` excludes the 2019-10-31 + 2020-01-29 AAPL
    filings (their effective_dates fall after the cutoff). The latest
    visible row is the 2019-07-31 filing (2019Q2)."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    result = load_fundamentals(["AAPL"], date(2019, 9, 15))
    assert isinstance(result["AAPL"], FundamentalsRow)
    assert result["AAPL"].fiscal_quarter == "2019Q2"
    assert result["AAPL"].report_date == date(2019, 7, 31)


def test_load_fundamentals_business_day_offset_advances_friday_to_monday(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NVDA's 2020-02-21 filing is a Friday. Adding 1 business day lands
    on Monday 2020-02-24 — NOT Saturday 2020-02-22. The row must be
    invisible at ``as_of=2020-02-22`` (Saturday) and visible at
    ``as_of=2020-02-24`` (Monday)."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    # Saturday — Friday filing not yet visible.
    sat_result = load_fundamentals(["NVDA"], date(2020, 2, 22))
    assert isinstance(sat_result["NVDA"], FundamentalsRow)
    # Falls back to the earlier 2019-08-15 filing.
    assert sat_result["NVDA"].fiscal_quarter == "2019Q2"

    # Monday — Friday filing visible (effective 2020-02-24).
    mon_result = load_fundamentals(["NVDA"], date(2020, 2, 24))
    assert isinstance(mon_result["NVDA"], FundamentalsRow)
    assert mon_result["NVDA"].fiscal_quarter == "2019Q4"


def test_load_fundamentals_returns_none_when_no_row_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``as_of`` earlier than every row's effective_date → that ticker
    maps to ``None`` (not absent from the dict, not raising)."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    result = load_fundamentals(["AAPL"], date(2018, 1, 1))
    assert "AAPL" in result
    assert result["AAPL"] is None


def test_load_fundamentals_clamps_future_as_of_to_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec contract — an ``as_of`` after today is clamped to today so
    the loader never accidentally surfaces unobservable data when a
    caller passes ``date.max`` etc."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    far_future = date.today() + timedelta(days=10_000)
    today_result = load_fundamentals(["AAPL"], date.today())
    future_result = load_fundamentals(["AAPL"], far_future)
    # Both produce the same row (the future query is clamped).
    assert today_result["AAPL"] == future_result["AAPL"]


# ---------------------------------------------------------------------------
# Multi-ticker handling
# ---------------------------------------------------------------------------


def test_load_fundamentals_multi_ticker_returns_every_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The result dict always contains every requested ticker, even
    if some are absent from the source. Absent tickers map to
    ``None``."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    result = load_fundamentals(["AAPL", "NVDA", "TICKER_NOT_IN_FILE"], date(2020, 3, 1))
    assert set(result.keys()) == {"AAPL", "NVDA", "TICKER_NOT_IN_FILE"}
    assert isinstance(result["AAPL"], FundamentalsRow)
    assert isinstance(result["NVDA"], FundamentalsRow)
    assert result["TICKER_NOT_IN_FILE"] is None


# ---------------------------------------------------------------------------
# Source resolution (unified-first / fixture fallback / nothing)
# ---------------------------------------------------------------------------


def test_load_fundamentals_prefers_unified_over_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both files exist, the unified file wins. Distinguish via
    a custom roe value that only the unified file carries."""

    unified = tmp_path / "unified.csv"
    fixture = tmp_path / "fixture.csv"
    _write_csv(
        unified,
        [_aapl_row("2019-05-01", "2019Q1", "2019-03-30", roe="0.9999")],
    )
    _write_csv(
        fixture,
        [_aapl_row("2019-05-01", "2019Q1", "2019-03-30", roe="0.1111")],
    )
    _patch_paths(monkeypatch, unified=unified, fixture=fixture)

    result = load_fundamentals(["AAPL"], date(2019, 6, 1))
    assert isinstance(result["AAPL"], FundamentalsRow)
    assert result["AAPL"].roe == 0.9999  # unified wins


def test_load_fundamentals_falls_back_to_fixture_when_unified_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No unified file → the loader reads the B025 fixture. This is
    the path strategy code uses on a fresh checkout that hasn't run
    the F002 backfill yet, and the path the six sector-structural
    tickers (BAC/JPM/V/LIN/NEE/PLD) take in production."""

    fixture = tmp_path / "fixture.csv"
    _write_csv(
        fixture,
        [_aapl_row("2019-05-01", "2019Q1", "2019-03-30", roe="0.1111")],
    )
    _patch_paths(monkeypatch, unified=None, fixture=fixture)

    result = load_fundamentals(["AAPL"], date(2019, 6, 1))
    assert isinstance(result["AAPL"], FundamentalsRow)
    assert result["AAPL"].roe == 0.1111  # fixture path


def test_load_fundamentals_returns_none_when_no_source_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither file present → every ticker maps to ``None``. Strategy
    code on a fresh checkout never crashes."""

    _patch_paths(monkeypatch, unified=None, fixture=None)

    result = load_fundamentals(["AAPL", "NVDA"], date(2020, 1, 1))
    assert result == {"AAPL": None, "NVDA": None}


# ---------------------------------------------------------------------------
# Schema violations
# ---------------------------------------------------------------------------


def test_load_fundamentals_raises_on_missing_required_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CSV missing one of the 12 required columns surfaces as
    :class:`FixtureDataError` with a remediation pointer
    (``scripts/backfill_fundamentals.py``)."""

    unified = tmp_path / "unified.csv"
    # Hand-write a CSV missing ``fiscal_quarter_end``.
    with unified.open("w", encoding="utf-8") as fh:
        fh.write("report_date,ticker,fiscal_quarter,roe\n")
        fh.write("2019-05-01,AAPL,2019Q1,0.4469\n")
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    with pytest.raises(FixtureDataError) as exc_info:
        load_fundamentals(["AAPL"], date(2020, 1, 1))
    message = str(exc_info.value)
    assert "fiscal_quarter_end" in message
    assert "scripts/backfill_fundamentals.py" in message


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_fundamentals_row_dataclass_is_frozen_and_has_12_fields() -> None:
    """Mirror the workbench_api FundamentalsRow guarantees: frozen +
    slots + 12 fields in canonical column order. This is the dataclass
    contract the F003 loader returns and the B030 cutover will rely on
    on the strategy-code side."""

    from dataclasses import FrozenInstanceError, fields

    row = FundamentalsRow(
        report_date=date(2019, 5, 1),
        ticker="AAPL",
        fiscal_quarter="2019Q1",
        fiscal_quarter_end=date(2019, 3, 30),
        roe=0.4469,
        gross_margin=0.4353,
        fcf_yield=0.0418,
        debt_to_assets=0.2952,
        pe=20.57,
        pb=12.54,
        ev_ebitda=16.72,
        earnings_yield=0.0486,
    )
    with pytest.raises(FrozenInstanceError):
        row.roe = 0.5  # type: ignore[misc]
    assert hasattr(FundamentalsRow, "__slots__")
    field_names = tuple(f.name for f in fields(FundamentalsRow))
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
    assert field_names == expected


# ---------------------------------------------------------------------------
# PIT spot-check (parametrized — 5 (ticker, as_of) tuples)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "as_of, expected_fq",
    [
        # Before any filing visible — None.
        (date(2018, 1, 1), None),
        # After Q1 filing only.
        (date(2019, 6, 1), "2019Q1"),
        # After Q2 filing.
        (date(2019, 9, 1), "2019Q2"),
        # After Q3 filing.
        (date(2019, 12, 1), "2019Q3"),
        # After Q4 filing.
        (date(2020, 6, 1), "2019Q4"),
    ],
)
def test_load_fundamentals_pit_spot_check_5_aapl_quarters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    as_of: date,
    expected_fq: str | None,
) -> None:
    """5 (as_of_date, expected fiscal_quarter) tuples walking AAPL
    forward through its 2019 filing cadence. Validates PIT semantics
    are monotonic — as ``as_of_date`` advances, the loader surfaces
    progressively newer quarters."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    _patch_paths(monkeypatch, unified=unified, fixture=None)

    result = load_fundamentals(["AAPL"], as_of)
    if expected_fq is None:
        assert result["AAPL"] is None
    else:
        assert isinstance(result["AAPL"], FundamentalsRow)
        assert result["AAPL"].fiscal_quarter == expected_fq
