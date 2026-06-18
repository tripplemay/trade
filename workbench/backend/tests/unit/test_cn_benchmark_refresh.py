"""B066 F003 — unit tests for the CSI 300 benchmark refresh (offline, faked loader)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from workbench_api.data_refresh.cn_benchmark import (
    CN_BENCHMARK_RELPATH,
    parse_index_close,
    run_cn_benchmark_refresh,
)


class _FakeLoader:
    def __init__(self, pairs: list[tuple[date, float]] | None = None, *, raises: bool = False):
        self._pairs = pairs or []
        self._raises = raises
        self.symbols: list[str] = []

    def fetch_index_close(self, symbol: str) -> list[tuple[date, float]]:
        self.symbols.append(symbol)
        if self._raises:
            raise RuntimeError("sina unreachable")
        return self._pairs


def test_parse_index_close_sorts_and_skips_bad_rows() -> None:
    records: list[dict[str, Any]] = [
        {"date": "2025-06-02", "close": 3900.0},
        {"date": "2025-01-02", "close": 3700.0},
        {"date": "2025-03-03", "close": 0},  # non-positive → skipped
        {"date": "bad", "close": 100.0},  # bad date → skipped
        {"date": "2025-04-01", "close": "n/a"},  # bad close → skipped
    ]
    pairs = parse_index_close(records)
    assert pairs == [(date(2025, 1, 2), 3700.0), (date(2025, 6, 2), 3900.0)]


def test_refresh_writes_csv(tmp_path: Path) -> None:
    loader = _FakeLoader([(date(2025, 1, 2), 3700.0), (date(2025, 1, 3), 3720.0)])
    rows = run_cn_benchmark_refresh(data_root=tmp_path, loader=loader)
    assert rows == 2
    path = tmp_path.joinpath(*CN_BENCHMARK_RELPATH)
    assert path.is_file()
    content = path.read_text(encoding="utf-8").splitlines()
    assert content[0] == "date,close"
    assert content[1] == "2025-01-02,3700.0"
    assert loader.symbols == ["sh000300"]  # sina CSI 300 code


def test_refresh_degrades_on_fetch_failure(tmp_path: Path) -> None:
    loader = _FakeLoader(raises=True)
    rows = run_cn_benchmark_refresh(data_root=tmp_path, loader=loader)
    assert rows == 0
    # No file written → the report degrades to "benchmark unavailable", never raises.
    assert not tmp_path.joinpath(*CN_BENCHMARK_RELPATH).exists()


def test_refresh_no_rows_writes_nothing(tmp_path: Path) -> None:
    rows = run_cn_benchmark_refresh(data_root=tmp_path, loader=_FakeLoader([]))
    assert rows == 0
    assert not tmp_path.joinpath(*CN_BENCHMARK_RELPATH).exists()


def test_refresh_degrades_on_write_failure(tmp_path: Path) -> None:
    # A WRITE failure (here: "snapshots" is a FILE → mkdir of snapshots/benchmark
    # raises OSError) must be best-effort too — return 0, never abort the wider
    # refresh (which would skip the downstream CN universe build / data-window).
    (tmp_path / "snapshots").write_text("not a dir", encoding="utf-8")
    rows = run_cn_benchmark_refresh(
        data_root=tmp_path, loader=_FakeLoader([(date(2025, 1, 2), 3700.0)])
    )
    assert rows == 0
