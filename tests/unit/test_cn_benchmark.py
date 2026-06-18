"""B066 F003 — unit tests for the CSI 300 benchmark loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from trade.data.cn_benchmark import load_cn_benchmark

_HEADER = "date,close\n"


def _write(path: Path, rows: list[tuple[str, float]]) -> None:
    lines = [_HEADER] + [f"{d},{c}\n" for d, c in rows]
    path.write_text("".join(lines), encoding="utf-8")


def test_missing_file_degrades_to_empty(tmp_path: Path) -> None:
    series = load_cn_benchmark(benchmark_path=tmp_path / "nope.csv")
    assert series.empty  # honest degradation, no raise


def test_loads_and_sorts_and_filters_window(tmp_path: Path) -> None:
    path = tmp_path / "cn_csi300.csv"
    _write(
        path,
        [
            ("2025-03-03", 3800.0),
            ("2025-01-02", 3700.0),
            ("2025-06-02", 3900.0),
        ],
    )
    series = load_cn_benchmark(
        date(2025, 1, 1), date(2025, 4, 1), benchmark_path=path
    )
    assert list(series.index) == [pd.Timestamp("2025-01-02"), pd.Timestamp("2025-03-03")]
    assert series.iloc[0] == 3700.0


def test_drops_non_positive_and_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "cn_csi300.csv"
    path.write_text(
        _HEADER + "2025-01-02,3700\n2025-01-03,0\n2025-01-04,-5\nbad,100\n",
        encoding="utf-8",
    )
    series = load_cn_benchmark(benchmark_path=path)
    assert list(series.index) == [pd.Timestamp("2025-01-02")]


def test_missing_columns_degrades(tmp_path: Path) -> None:
    path = tmp_path / "cn_csi300.csv"
    path.write_text("date,value\n2025-01-02,3700\n", encoding="utf-8")
    assert load_cn_benchmark(benchmark_path=path).empty


def test_non_numeric_close_dropped_not_raised(tmp_path: Path) -> None:
    # The loader contract is "never raise on a malformed file": a valid date with a
    # non-numeric close must DROP the row, not raise (else it crashes the backtest).
    path = tmp_path / "cn_csi300.csv"
    path.write_text("date,close\n2025-01-02,3700\n2025-01-03,abc\n", encoding="utf-8")
    series = load_cn_benchmark(benchmark_path=path)
    assert list(series.index) == [pd.Timestamp("2025-01-02")]
