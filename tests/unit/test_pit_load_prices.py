"""B028 F003 — PIT enforcement for ``trade.data.loader.load_prices``.

These specs lock the contract the B030 cutover will rely on:

* Real-data path: when ``data/snapshots/prices/unified/prices_daily.csv``
  exists (produced by ``scripts/backfill_prices.py``), the loader
  reads from it and filters strictly by ``as_of_date``.
* Fallback path: when the unified file is absent, the loader reads
  the B025 synthetic fixture instead.
* No-source path: when both are absent, the loader returns the empty
  dict shape — strategy code never crashes pre-backfill.
* Schema violations raise :class:`FixtureDataError` with a remediation
  pointer so a misshapen CSV is loud, not silent.

Each spec patches the loader's module-level path constants via
``monkeypatch`` so the assertions run against a per-test tmp file
without touching the real ``data/snapshots/`` artifacts.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.data import loader as loader_module
from trade.data.loader import (
    FixtureDataError,
    PriceBar,
    load_prices,
)

UNIFIED_COLUMNS = ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=UNIFIED_COLUMNS)
        writer.writeheader()
        for row in rows:
            full = {col: "" for col in UNIFIED_COLUMNS}
            full.update(row)
            writer.writerow(full)


def _seed_unified_csv(path: Path) -> None:
    _write_csv(
        path,
        [
            {
                "date": "2024-01-02",
                "ticker": "SPY",
                "open": "470.0",
                "high": "475.0",
                "low": "469.0",
                "close": "472.0",
                "adj_close": "470.0",
                "volume": "100000000",
            },
            {
                "date": "2024-01-03",
                "ticker": "SPY",
                "open": "471.0",
                "high": "473.0",
                "low": "469.5",
                "close": "470.0",
                "adj_close": "468.0",
                "volume": "90000000",
            },
            {
                "date": "2024-01-04",
                "ticker": "SPY",
                "open": "469.0",
                "high": "471.0",
                "low": "467.0",
                "close": "470.5",
                "adj_close": "468.5",
                "volume": "80000000",
            },
            {
                "date": "2024-01-02",
                "ticker": "QQQ",
                "open": "405.0",
                "high": "407.0",
                "low": "404.0",
                "close": "406.5",
                "adj_close": "405.5",
                "volume": "50000000",
            },
        ],
    )


def test_load_prices_filters_by_as_of_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 1 — no row with date > as_of_date."""

    unified = tmp_path / "prices_daily.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2024, 1, 3))
    spy_dates = [b.date for b in bars["SPY"]]
    assert spy_dates == [date(2024, 1, 2), date(2024, 1, 3)]
    assert all(d <= date(2024, 1, 3) for d in spy_dates)


def test_load_prices_returns_recent_range_for_late_as_of(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A far-future as_of_date returns every row in the source."""

    unified = tmp_path / "prices_daily.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2030, 1, 1))
    # 3 SPY rows total in the seed.
    assert len(bars["SPY"]) == 3


def test_load_prices_reads_unified_when_present_skips_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    fallback = tmp_path / "fixture.csv"
    _write_csv(
        fallback,
        [
            {
                "date": "2024-01-02",
                "ticker": "AAPL",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            }
        ],
    )
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)
    monkeypatch.setattr(loader_module, "B025_FIXTURE_PRICES_PATH", fallback)

    bars = load_prices(["SPY", "AAPL"], as_of_date=date(2030, 1, 1))
    # AAPL is in the fallback fixture only; unified takes precedence so
    # AAPL should be empty.
    assert len(bars["SPY"]) == 3
    assert bars["AAPL"] == []


def test_load_prices_falls_back_to_fixture_when_unified_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 3 — unified absent reads fixture."""

    fallback = tmp_path / "fixture.csv"
    _write_csv(
        fallback,
        [
            {
                "date": "2024-01-02",
                "ticker": "AAPL",
                "open": "190.0",
                "high": "191.0",
                "low": "189.5",
                "close": "190.5",
                "adj_close": "189.0",
                "volume": "60000000",
            }
        ],
    )
    monkeypatch.setattr(
        loader_module, "UNIFIED_PRICES_PATH", tmp_path / "missing.csv"
    )
    monkeypatch.setattr(loader_module, "B025_FIXTURE_PRICES_PATH", fallback)

    bars = load_prices(["AAPL"], as_of_date=date(2024, 1, 5))
    assert len(bars["AAPL"]) == 1
    assert bars["AAPL"][0].symbol == "AAPL"
    assert bars["AAPL"][0].adjusted_close == 189.0


def test_load_prices_future_as_of_clamps_to_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 5 — future as_of clamps to today."""

    unified = tmp_path / "unified.csv"
    today_iso = date.today().isoformat()
    yesterday_iso = (date.today() - timedelta(days=1)).isoformat()
    # Row whose date is exactly today — visible only when as_of >= today.
    _write_csv(
        unified,
        [
            {
                "date": today_iso,
                "ticker": "SPY",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            },
            {
                "date": yesterday_iso,
                "ticker": "SPY",
                "open": "2.0",
                "high": "2.0",
                "low": "2.0",
                "close": "2.0",
                "adj_close": "2.0",
                "volume": "2",
            },
        ],
    )
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2099, 12, 31))
    spy_dates = [b.date for b in bars["SPY"]]
    # Today's row appears (as_of clamped to today) — and nothing newer.
    assert date.today() in spy_dates
    assert max(spy_dates) == date.today()


def test_load_prices_returns_empty_when_as_of_before_earliest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 6 — sub-earliest as_of returns []."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2000, 1, 1))
    assert bars["SPY"] == []


def test_load_prices_returns_dict_keyed_by_every_requested_ticker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 7 — multi-ticker dict output."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY", "QQQ", "BTC"], as_of_date=date(2030, 1, 1))
    assert set(bars.keys()) == {"SPY", "QQQ", "BTC"}
    # BTC is absent from the source — must still appear with an empty list.
    assert bars["BTC"] == []
    assert len(bars["SPY"]) == 3
    assert len(bars["QQQ"]) == 1


def test_load_prices_returns_empty_dict_when_no_source_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither unified nor fixture present — still produce the dict
    shape, not raise. Strategy code calling ``load_prices`` before any
    backfill has happened must degrade gracefully."""

    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", tmp_path / "no-unified.csv")
    monkeypatch.setattr(loader_module, "B025_FIXTURE_PRICES_PATH", tmp_path / "no-fixture.csv")

    bars = load_prices(["SPY", "QQQ"], as_of_date=date(2024, 1, 5))
    assert bars == {"SPY": [], "QQQ": []}


def test_load_prices_raises_on_schema_mismatch_with_remediation_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §F003 acceptance #3 row 9 — clear ValueError on schema drift."""

    bad = tmp_path / "bad.csv"
    bad.write_text("date,ticker,open\n2024-01-02,SPY,470.0\n", encoding="utf-8")
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", bad)

    with pytest.raises(FixtureDataError) as exc_info:
        load_prices(["SPY"], as_of_date=date(2024, 1, 5))
    message = str(exc_info.value)
    # Missing column names appear in the message.
    assert "adj_close" in message
    assert "volume" in message
    # Remediation pointer is present.
    assert "scripts/backfill_prices.py" in message


def test_load_prices_bars_use_legacy_pricebar_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unified row maps onto :class:`PriceBar` (legacy shape) with
    ``ticker`` → ``symbol`` and ``adj_close`` → ``adjusted_close``."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2030, 1, 1))
    bar = bars["SPY"][0]
    assert isinstance(bar, PriceBar)
    assert bar.symbol == "SPY"
    assert bar.date == date(2024, 1, 2)
    assert bar.open == 470.0
    assert bar.close == 472.0
    assert bar.adjusted_close == 470.0
    assert bar.volume == 100_000_000


def test_load_prices_sorts_bars_by_date_ascending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Order of rows on disk is irrelevant — output is sorted ascending."""

    unified = tmp_path / "unified.csv"
    _write_csv(
        unified,
        [
            {
                "date": "2024-01-04",
                "ticker": "SPY",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            },
            {
                "date": "2024-01-02",
                "ticker": "SPY",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            },
            {
                "date": "2024-01-03",
                "ticker": "SPY",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            },
        ],
    )
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(["SPY"], as_of_date=date(2030, 1, 1))
    assert [b.date for b in bars["SPY"]] == [
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
    ]


def test_load_prices_from_date_lower_bound_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``from_date`` is the inclusive lower bound — combine with
    ``as_of_date`` to slice a window."""

    unified = tmp_path / "unified.csv"
    _seed_unified_csv(unified)
    monkeypatch.setattr(loader_module, "UNIFIED_PRICES_PATH", unified)

    bars = load_prices(
        ["SPY"],
        as_of_date=date(2024, 1, 4),
        from_date=date(2024, 1, 3),
    )
    assert [b.date for b in bars["SPY"]] == [date(2024, 1, 3), date(2024, 1, 4)]
