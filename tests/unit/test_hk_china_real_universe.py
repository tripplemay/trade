"""B063 F002 — wide CN/HK universe + USD conversion.

Covers point-in-time membership, suffix-derived currency, offline price read
(filter to the universe + ``date <= as_of``, honest-empty when absent), the
as-of FX → USD conversion (per-row rate, OHLC scaled together, unconvertible
rows dropped, USD passthrough), and the PriceBar projection.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import (
    REAL_HK_CHINA_UNIVERSE,
    REAL_UNIVERSE_TICKERS,
    RealUniverseError,
    currency_for,
    load_real_prices,
    load_real_universe,
    to_usd_prices,
    usd_price_bars,
)

_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def _fx(rows: list[tuple[str, str, float]]) -> FxConverter:
    rates: dict[str, list[tuple[date, float]]] = {}
    for iso, ccy, rate in rows:
        rates.setdefault(ccy, []).append((date.fromisoformat(iso), rate))
    for ccy in rates:
        rates[ccy].sort(key=lambda item: item[0])
    return FxConverter(rates)


def _prices(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """``rows`` = (iso_date, ticker, close); other OHLCV columns derived."""

    records = [
        {
            "date": pd.Timestamp(iso),
            "ticker": ticker,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "adj_close": close,
            "volume": 1000,
        }
        for iso, ticker, close in rows
    ]
    return pd.DataFrame(records, columns=_COLUMNS)


# --- universe ---


def test_universe_is_wide_and_multi_sector() -> None:
    # Spec §2: deliberately wider than the seven mega-cap winners.
    assert len(REAL_HK_CHINA_UNIVERSE) >= 20
    sectors = {entry.sector for entry in REAL_HK_CHINA_UNIVERSE}
    assert {"bank", "insurance", "energy"} <= sectors  # not just internet winners
    assert len(REAL_UNIVERSE_TICKERS) == len(set(REAL_UNIVERSE_TICKERS))  # no dups


def test_currency_for_suffix() -> None:
    assert currency_for("0700.HK") == "HKD"
    assert currency_for("600519.SH") == "CNY"
    assert currency_for("000858.SZ") == "CNY"
    assert currency_for("SPY") == "USD"


def test_every_entry_currency_matches_suffix() -> None:
    for entry in REAL_HK_CHINA_UNIVERSE:
        assert entry.currency == currency_for(entry.ticker)


def test_universe_pit_membership_excludes_not_yet_listed() -> None:
    # CATL (300750.SZ) listed 2018-06-11 — invisible before, visible after.
    before = {e.ticker for e in load_real_universe(as_of=date(2015, 1, 1))}
    after = {e.ticker for e in load_real_universe(as_of=date(2020, 1, 1))}
    assert "300750.SZ" not in before
    assert "300750.SZ" in after
    assert "0700.HK" in before  # listed 2004
    assert load_real_universe() == REAL_HK_CHINA_UNIVERSE  # None = all


# --- offline price read ---


def _write_csv(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_COLUMNS)
        writer.writerows(rows)


def test_load_real_prices_filters_universe_and_as_of(tmp_path: Path) -> None:
    path = tmp_path / "prices_daily.csv"
    _write_csv(
        path,
        [
            ["2024-01-02", "0700.HK", 300, 301, 299, 300, 300, 10],
            ["2024-02-02", "0700.HK", 320, 321, 319, 320, 320, 10],  # after as_of
            ["2024-01-02", "SPY", 470, 471, 469, 470, 470, 10],  # not in universe
        ],
    )
    frame = load_real_prices(date(2024, 1, 31), path=path)
    assert set(frame["ticker"]) == {"0700.HK"}  # SPY filtered out
    assert frame["date"].max() == pd.Timestamp("2024-01-02")  # future row dropped


def test_load_real_prices_missing_file_is_empty_not_error(tmp_path: Path) -> None:
    frame = load_real_prices(date(2024, 1, 1), path=tmp_path / "nope.csv")
    assert frame.empty
    assert list(frame.columns) == _COLUMNS


def test_load_real_prices_malformed_csv_raises(tmp_path: Path) -> None:
    # A present-but-misshapen CSV (missing adj_close) must fail loudly, not
    # silently degrade — a corrupt source is a different failure from "absent".
    path = tmp_path / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02", "0700.HK", 300, 301, 299, 300, 10])
    with pytest.raises(RealUniverseError):
        load_real_prices(date(2024, 1, 31), path=path)


# --- USD conversion ---


def test_to_usd_divides_by_as_of_rate() -> None:
    local = _prices([("2024-01-02", "0700.HK", 780.0), ("2024-01-02", "600519.SH", 1700.0)])
    fx = _fx([("2024-01-02", "HKD", 7.8), ("2024-01-02", "CNY", 7.0)])
    usd = to_usd_prices(local, fx)
    by_ticker = {row.ticker: row for row in usd.itertuples(index=False)}
    assert by_ticker["0700.HK"].close == pytest.approx(100.0)  # 780 / 7.8
    assert by_ticker["600519.SH"].adj_close == pytest.approx(242.857142, rel=1e-5)  # 1700/7


def test_to_usd_forward_fills_across_fx_gap() -> None:
    # FX has only 2024-01-02; a 2024-01-04 bar must use the 01-02 rate (as-of).
    local = _prices([("2024-01-04", "0700.HK", 780.0)])
    fx = _fx([("2024-01-02", "HKD", 7.8)])
    usd = to_usd_prices(local, fx)
    assert usd.iloc[0]["close"] == pytest.approx(100.0)


def test_to_usd_drops_unconvertible_rows() -> None:
    # No HKD rate on/before the bar date → row dropped, not fabricated.
    local = _prices([("2024-01-02", "0700.HK", 780.0)])
    fx = _fx([("2024-01-05", "HKD", 7.8)])  # only after the bar
    assert to_usd_prices(local, fx).empty


def test_usd_price_bars_projection() -> None:
    usd = _prices([("2024-01-02", "0700.HK", 100.0)])
    bars = usd_price_bars(usd)
    assert len(bars) == 1
    assert bars[0].symbol == "0700.HK"
    assert bars[0].adjusted_close == pytest.approx(100.0)
    assert bars[0].date == date(2024, 1, 2)
    assert usd_price_bars(pd.DataFrame(columns=_COLUMNS)) == ()
