"""B090 F001 — deterministic unit tests for the HK/China retest mechanical pieces.

Covers only the pure, deterministic helpers (no network, no akshare): the
canonical-ticker → akshare-symbol maps, the FRED CSV parser row shape, the
fetch-frame normalization (adj_close == qfq close), and the 200D-warmup signal
filter. The backtest numbers themselves are exercised by running the scripts
against cached real data, not asserted here.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts.research.b090_hk_china_fetch import (
    _normalize_frame,
    a_canonical_to_symbol,
    hk_canonical_to_symbol,
    parse_fred_csv,
)
from scripts.research.b090_hk_china_retest import warmup_filter
from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import PRICES_REQUIRED_COLUMNS


def _write_fx(frame: pd.DataFrame) -> Path:
    path = Path(tempfile.mkdtemp()) / "fx_daily.csv"
    frame.to_csv(path, index=False)
    return path


# --- canonical HK ticker -> stock_hk_daily 5-digit symbol ---------------------


def test_hk_canonical_to_symbol_zero_pads_to_five() -> None:
    assert hk_canonical_to_symbol("0700.HK") == "00700"  # Tencent
    assert hk_canonical_to_symbol("9988.HK") == "09988"  # Alibaba HK
    assert hk_canonical_to_symbol("1398.HK") == "01398"  # ICBC
    assert hk_canonical_to_symbol("0941.HK") == "00941"  # China Mobile


def test_hk_canonical_to_symbol_is_case_insensitive() -> None:
    assert hk_canonical_to_symbol("0700.hk") == "00700"


# --- canonical A-share ticker -> stock_zh_a_daily sina symbol ------------------


def test_a_canonical_to_symbol_exchange_prefix() -> None:
    assert a_canonical_to_symbol("600519.SH") == "sh600519"  # Kweichow Moutai
    assert a_canonical_to_symbol("000858.SZ") == "sz000858"  # Wuliangye
    assert a_canonical_to_symbol("300750.SZ") == "sz300750"  # CATL


def test_a_canonical_to_symbol_rejects_non_a_share() -> None:
    with pytest.raises(ValueError, match="not an A-share"):
        a_canonical_to_symbol("0700.HK")


# --- FRED CSV parser: row shape (date, currency, rate), '.' rows skipped -------


def test_parse_fred_csv_row_shape_and_skips_holidays() -> None:
    text = (
        "observation_date,DEXHKUS\n"
        "2020-01-02,7.7900\n"
        "2020-01-03,.\n"  # FRED holiday marker — must be skipped
        "2020-01-06,7.7850\n"
    )
    rows = parse_fred_csv(text, "HKD")
    assert rows == [("2020-01-02", "HKD", 7.79), ("2020-01-06", "HKD", 7.785)]
    # Every row is the (date, currency, rate) triple the fx CSV schema needs.
    assert all(len(r) == 3 and r[1] == "HKD" and isinstance(r[2], float) for r in rows)


def test_parse_fred_csv_empty_when_only_header() -> None:
    assert parse_fred_csv("observation_date,DEXCHUS\n", "CNY") == []


def test_fx_csv_shape_loads_and_converts() -> None:
    """A CSV with columns date,currency,rate (LOCAL-per-USD) round-trips through
    FxConverter with usd = amount / rate."""

    rows = parse_fred_csv("observation_date,DEXHKUS\n2020-01-02,7.8\n", "HKD")
    frame = pd.DataFrame(rows, columns=["date", "currency", "rate"])
    assert list(frame.columns) == ["date", "currency", "rate"]

    fx_path = _write_fx(frame)
    converter = FxConverter.load(path=fx_path)
    assert converter.currencies() == ["HKD"]
    assert converter.to_usd(78.0, "HKD", date(2020, 1, 2)) == pytest.approx(10.0)


# --- fetch-frame normalization: adj_close == qfq close, bad rows dropped -------


def test_normalize_frame_sets_adj_close_to_qfq_close_and_drops_bad_rows() -> None:
    raw = pd.DataFrame(
        {
            "date": ["2021-01-04", "2021-01-05", "2021-01-06"],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10.2, 0.0, 12.2],  # middle row non-positive -> dropped
            "volume": [1000.0, 2000.0, None],  # last row NaN volume -> dropped
        }
    )
    out = _normalize_frame(raw, "0700.HK")
    assert list(out.columns) == list(PRICES_REQUIRED_COLUMNS)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["ticker"] == "0700.HK"
    assert row["date"] == "2021-01-04"
    # adj_close is the qfq-adjusted close (same value as close for these sources).
    assert row["adj_close"] == row["close"] == pytest.approx(10.2)


# --- 200D-warmup signal filter -------------------------------------------------


def _days(n: int) -> list[date]:
    return list(pd.bdate_range("2020-01-01", periods=n).date)


def test_warmup_filter_keeps_only_dates_on_or_after_200th_shared_day() -> None:
    shared = _days(260)
    cutoff = shared[199]  # the 200th shared trading day
    before, on, after = shared[100], cutoff, shared[240]
    kept = warmup_filter((before, on, after), shared)
    assert before not in kept  # inside the warmup window -> dropped
    assert on in kept and after in kept  # on/after the cutoff -> kept


def test_warmup_filter_empty_when_history_shorter_than_warmup() -> None:
    shared = _days(150)  # < 200 shared trading days
    assert warmup_filter(tuple(shared), shared) == ()
