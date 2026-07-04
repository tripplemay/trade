"""B082 F001 (part 2) — unit tests for the 红利低波 defensive-sleeve refresh.

Offline: pure parsers on plain dict rows, the akshare loader against a faked
module (pd.DataFrame in / rows out, no network), and the best-effort orchestrator
(5 CSVs written; single-series failure / hang / empty degrades that series only,
不炸整轮). The real akshare endpoints are exercised at L2 on the VM (Codex F004) —
these assert logic / wiring / schema, not market values.
"""

from __future__ import annotations

import threading
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from workbench_api.data_refresh.cli import parse_args
from workbench_api.data_refresh.cn_dividend_lowvol import (
    DIVIDEND_LOWVOL_SUBDIR,
    AkshareDividendLowvolLoader,
    parse_date_value,
    parse_etf_bars,
    run_dividend_lowvol_refresh,
)

# --------------------------------------------------------------------------- #
# pure parsers
# --------------------------------------------------------------------------- #


def test_parse_etf_bars_orders_and_requires_close() -> None:
    records: list[dict[str, Any]] = [
        {"date": "2024-06-02", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 900},
        {"date": "2024-01-02", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 500},
        {"date": "2024-03-03", "close": 0},  # non-positive close → skipped
        {"date": "bad", "close": 5.0},  # malformed date → skipped
        {"date": "2024-04-01", "close": "n/a"},  # bad close → skipped
    ]
    rows = parse_etf_bars(records)
    assert rows == [
        ["2024-01-02", "1.0", "1.1", "0.9", "1.05", "500.0"],
        ["2024-06-02", "1.1", "1.2", "1.0", "1.15", "900.0"],
    ]


def test_parse_etf_bars_blanks_missing_optional_columns() -> None:
    # A valid date + close but no OHLC/volume → those columns are blank, not dropped.
    rows = parse_etf_bars([{"date": "2024-01-02", "close": 1.05}])
    assert rows == [["2024-01-02", "", "", "", "1.05", ""]]


def test_parse_date_value_sorts_and_skips_non_positive_and_bad() -> None:
    records: list[dict[str, Any]] = [
        {"日期": "2024-06-02", "收盘": 1000.0},
        {"日期": "2024-01-02", "收盘": 900.0},
        {"日期": "2024-03-03", "收盘": 0},  # non-positive → skipped
        {"日期": "bad", "收盘": 100.0},  # bad date → skipped
        {"日期": "2024-04-01", "收盘": "n/a"},  # bad value → skipped
        {"日期": "2024-05-01", "收盘": float("nan")},  # NaN → skipped
    ]
    rows = parse_date_value(records, date_key="日期", value_key="收盘")
    assert rows == [["2024-01-02", "900.0"], ["2024-06-02", "1000.0"]]


# --------------------------------------------------------------------------- #
# akshare loader (faked module — no network)
# --------------------------------------------------------------------------- #


class _FakeAkshare:
    """Returns a pd.DataFrame per endpoint; ``None`` frame → the method raises."""

    def __init__(
        self,
        *,
        etf: pd.DataFrame | None = None,
        index: pd.DataFrame | None = None,
        bond: pd.DataFrame | None = None,
        gxl: pd.DataFrame | None = None,
    ) -> None:
        self._etf = etf
        self._index = index
        self._bond = bond
        self._gxl = gxl

    def fund_etf_hist_sina(self, symbol: str) -> pd.DataFrame:
        if self._etf is None:
            raise RuntimeError("sina unreachable")
        return self._etf

    def stock_zh_index_hist_csindex(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        if self._index is None:
            raise RuntimeError("csindex unreachable")
        return self._index

    def bond_zh_us_rate(self, start_date: str) -> pd.DataFrame:
        if self._bond is None:
            raise RuntimeError("chinabond unreachable")
        return self._bond

    def stock_a_gxl_lg(self, symbol: str) -> pd.DataFrame:
        if self._gxl is None:
            raise RuntimeError("legulegu unreachable")
        return self._gxl


def test_loader_fetch_etf_bars_parses_frame() -> None:
    frame = pd.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 3)],
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [500, 600],
        }
    )
    loader = AkshareDividendLowvolLoader(akshare_module=_FakeAkshare(etf=frame))
    rows = loader.fetch_etf_bars("sh512890")
    assert rows[0] == ["2024-01-02", "1.0", "1.2", "0.9", "1.05", "500.0"]
    assert len(rows) == 2


def test_loader_fetch_index_close_parses_csindex_columns() -> None:
    frame = pd.DataFrame({"日期": [date(2024, 1, 2)], "收盘": [1000.0]})
    loader = AkshareDividendLowvolLoader(akshare_module=_FakeAkshare(index=frame))
    assert loader.fetch_index_close("H30269", "20050101", "20240704") == [
        ["2024-01-02", "1000.0"]
    ]


def test_loader_fetch_bond_yield_selects_column() -> None:
    frame = pd.DataFrame(
        {"日期": [date(2024, 1, 2)], "中国国债收益率10年": [2.5], "中国国债收益率5年": [2.1]}
    )
    loader = AkshareDividendLowvolLoader(akshare_module=_FakeAkshare(bond=frame))
    assert loader.fetch_bond_yield("20050101", "中国国债收益率10年") == [
        ["2024-01-02", "2.5"]
    ]


def test_loader_fetch_market_dividend_yield_parses_gxl() -> None:
    frame = pd.DataFrame({"日期": [date(2024, 1, 2)], "股息率": [3.1]})
    loader = AkshareDividendLowvolLoader(akshare_module=_FakeAkshare(gxl=frame))
    assert loader.fetch_market_dividend_yield("上证A股") == [["2024-01-02", "3.1"]]


def test_loader_unreachable_endpoint_returns_empty_not_raises() -> None:
    loader = AkshareDividendLowvolLoader(akshare_module=_FakeAkshare(etf=None))
    assert loader.fetch_etf_bars("sh512890") == []  # raises inside → [], no propagation


# --------------------------------------------------------------------------- #
# orchestrator (best-effort, 5 series)
# --------------------------------------------------------------------------- #


class _FakeLoader:
    """Configurable rows per method; ``fail`` raises and ``hang`` blocks forever."""

    def __init__(
        self,
        *,
        etf: list[list[str]] | None = None,
        index: list[list[str]] | None = None,
        bond: list[list[str]] | None = None,
        gxl: list[list[str]] | None = None,
        fail: set[str] | None = None,
        hang: set[str] | None = None,
    ) -> None:
        default_etf = [["2024-01-02", "1.0", "1.1", "0.9", "1.05", "500.0"]]
        self._etf = etf if etf is not None else default_etf
        self._index = index if index is not None else [["2024-01-02", "1000.0"]]
        self._bond = bond if bond is not None else [["2024-01-02", "2.5"]]
        self._gxl = gxl if gxl is not None else [["2024-01-02", "3.1"]]
        self._fail = fail or set()
        self._hang = hang or set()
        self.index_calls: list[tuple[str, str, str]] = []

    def _gate(self, key: str) -> None:
        if key in self._hang:
            threading.Event().wait()  # blocks forever (daemon worker) → FetchTimeoutError
        if key in self._fail:
            raise RuntimeError(f"{key} unreachable")

    def fetch_etf_bars(self, symbol: str) -> list[list[str]]:
        self._gate("etf")
        return self._etf

    def fetch_index_close(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[list[str]]:
        self.index_calls.append((symbol, start_date, end_date))
        self._gate("index")
        return self._index

    def fetch_bond_yield(self, start_date: str, column: str) -> list[list[str]]:
        self._gate("bond")
        return self._bond

    def fetch_market_dividend_yield(self, symbol: str) -> list[list[str]]:
        self._gate("gxl")
        return self._gxl


def _read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_refresh_writes_all_five_csvs(tmp_path: Path) -> None:
    loader = _FakeLoader()
    summary = run_dividend_lowvol_refresh(
        data_root=tmp_path, loader=loader, today=date(2024, 7, 4)
    )
    assert summary.errors == 0
    assert summary.rows_by_series == {
        "etf_512890": 1,
        "index_h30269": 1,
        "index_h20269": 1,
        "cn_10y_yield": 1,
        "gxl_sh": 1,
    }
    base = tmp_path.joinpath(*DIVIDEND_LOWVOL_SUBDIR)
    # Headers + content per series.
    assert _read(base / "etf_512890.csv")[0] == "date,open,high,low,close,volume"
    assert _read(base / "etf_512890.csv")[1] == "2024-01-02,1.0,1.1,0.9,1.05,500.0"
    assert _read(base / "index_h30269.csv")[0] == "date,close"
    assert _read(base / "index_h20269.csv") == ["date,close", "2024-01-02,1000.0"]
    assert _read(base / "cn_10y_yield.csv") == ["date,yield", "2024-01-02,2.5"]
    assert _read(base / "gxl_sh.csv") == ["date,dividend_yield", "2024-01-02,3.1"]
    # csindex called for BOTH index codes, end_date pinned to the run date.
    assert loader.index_calls == [
        ("H30269", "20050101", "20240704"),
        ("H20269", "20050101", "20240704"),
    ]


def test_refresh_single_series_failure_does_not_abort_others(tmp_path: Path) -> None:
    loader = _FakeLoader(fail={"etf"})
    summary = run_dividend_lowvol_refresh(
        data_root=tmp_path, loader=loader, today=date(2024, 7, 4)
    )
    assert summary.errors == 1
    assert summary.rows_by_series["etf_512890"] == 0
    base = tmp_path.joinpath(*DIVIDEND_LOWVOL_SUBDIR)
    assert not (base / "etf_512890.csv").exists()  # failed series left unwritten
    # The other four survived (不炸整轮).
    for name in ("index_h30269", "index_h20269", "cn_10y_yield", "gxl_sh"):
        assert (base / f"{name}.csv").is_file()


def test_refresh_timeout_degrades_series_only(tmp_path: Path) -> None:
    loader = _FakeLoader(hang={"etf"})
    summary = run_dividend_lowvol_refresh(
        data_root=tmp_path,
        loader=loader,
        fetch_timeout_seconds=0.05,
        today=date(2024, 7, 4),
    )
    assert summary.rows_by_series["etf_512890"] == 0  # hung fetch → FetchTimeoutError
    assert summary.errors == 1
    base = tmp_path.joinpath(*DIVIDEND_LOWVOL_SUBDIR)
    assert not (base / "etf_512890.csv").exists()
    assert (base / "index_h30269.csv").is_file()  # non-hung series unaffected


def test_refresh_empty_series_counted_and_unwritten(tmp_path: Path) -> None:
    loader = _FakeLoader(gxl=[])
    summary = run_dividend_lowvol_refresh(
        data_root=tmp_path, loader=loader, today=date(2024, 7, 4)
    )
    assert summary.rows_by_series["gxl_sh"] == 0
    assert summary.errors == 1
    assert not tmp_path.joinpath(*DIVIDEND_LOWVOL_SUBDIR, "gxl_sh.csv").exists()


# --------------------------------------------------------------------------- #
# cli flag wiring
# --------------------------------------------------------------------------- #


def test_dividend_lowvol_on_by_default() -> None:
    assert parse_args(["fetch"]).no_dividend_lowvol is False


def test_no_dividend_lowvol_flag_disables() -> None:
    assert parse_args(["fetch", "--no-dividend-lowvol"]).no_dividend_lowvol is True
