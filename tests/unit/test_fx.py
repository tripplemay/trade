"""B063 F001 — FX reader + USD converter (trade-side, offline CSV read).

Covers as-of (forward-fill) rate lookup across FRED weekend/holiday gaps, USD
conversion (local/rate), USD passthrough, unknown-currency / missing-file
honest-None degradation, and case-insensitive currency.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from trade.data.fx import FxConverter, load_fx_rates


def _write_fx(path: Path, rows: list[tuple[str, str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "currency", "rate"])
        writer.writerows(rows)


def test_as_of_forward_fill(tmp_path: Path) -> None:
    path = tmp_path / "fx_daily.csv"
    _write_fx(path, [("2024-01-02", "CNY", 7.10), ("2024-01-05", "CNY", 7.20)])
    conv = FxConverter.load(path)
    assert conv.rate_as_of("CNY", date(2024, 1, 2)) == 7.10
    # forward-fill: 2024-01-04 (no obs) -> most recent prior (2024-01-02)
    assert conv.rate_as_of("CNY", date(2024, 1, 4)) == 7.10
    # after the last obs -> last known
    assert conv.rate_as_of("CNY", date(2024, 1, 6)) == 7.20
    # before the first obs -> None (no rate to forward-fill from)
    assert conv.rate_as_of("CNY", date(2024, 1, 1)) is None


def test_to_usd_conversion(tmp_path: Path) -> None:
    path = tmp_path / "fx.csv"
    _write_fx(path, [("2024-01-02", "CNY", 7.0), ("2024-01-02", "HKD", 7.8)])
    conv = FxConverter.load(path)
    assert conv.to_usd(700.0, "CNY", date(2024, 1, 2)) == pytest.approx(100.0)
    assert conv.to_usd(78.0, "HKD", date(2024, 1, 2)) == pytest.approx(10.0)
    assert conv.to_usd(50.0, "USD", date(2024, 1, 2)) == 50.0  # passthrough
    assert conv.to_usd(100.0, "JPY", date(2024, 1, 2)) is None  # unknown -> None


def test_case_insensitive_currency(tmp_path: Path) -> None:
    path = tmp_path / "fx.csv"
    _write_fx(path, [("2024-01-02", "CNY", 7.0)])
    conv = FxConverter.load(path)
    assert conv.to_usd(700.0, "cny", date(2024, 1, 2)) == pytest.approx(100.0)


def test_missing_file_degrades_honestly(tmp_path: Path) -> None:
    conv = FxConverter.load(tmp_path / "nope.csv")
    assert load_fx_rates(tmp_path / "nope.csv") == {}
    assert conv.rate_as_of("CNY", date(2024, 1, 2)) is None
    assert conv.to_usd(100.0, "CNY", date(2024, 1, 2)) is None
    # USD never needs the file.
    assert conv.to_usd(100.0, "USD", date(2024, 1, 2)) == 100.0
