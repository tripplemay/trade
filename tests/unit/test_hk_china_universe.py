"""BL-B011-S2 F001 — HK-China universe loader (price-only).

Pins the loader the strategy (F002) + master dispatch (F003) read from:
``load_universe`` / ``load_prices`` against the synthetic fixture and a
unified-CSV stand-in, the as_of point-in-time filters, the HK-China ticker
filter on the shared price file, and the resolution priority (fixture_dir >
FORCE_FIXTURE_PATH > unified > default fixture).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from trade.data import hk_china_universe as repo
from trade.data.hk_china_universe import (
    DEFAULT_FIXTURE_DIR,
    HK_CHINA_TICKERS,
    PRICES_FILE_NAME,
    HkChinaFixtureError,
    load_prices,
    load_universe,
)

_PRICE_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def _write_prices(path: Path, rows: list[tuple[str, str, float]]) -> None:
    """rows = (date, ticker, close); OHLCV padded around close."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_PRICE_HEADER)
        for d, t, c in rows:
            w.writerow([d, t, c, c, c, c, c, 1000])


# --- fixture branch -------------------------------------------------------


def test_load_universe_returns_phase1_etfs() -> None:
    entries = load_universe()
    tickers = {e.ticker for e in entries}
    assert tickers == set(HK_CHINA_TICKERS)
    by = {e.ticker: e for e in entries}
    assert by["KWEB"].exposure  # exposure metadata present
    assert by["MCHI"].name


def test_load_universe_as_of_excludes_unlisted() -> None:
    # MCHI listed 2011-03, FXI 2004-10; KWEB/ASHR listed 2013 → excluded
    # before their listing date.
    entries = load_universe(as_of=date(2012, 1, 1))
    tickers = {e.ticker for e in entries}
    assert tickers == {"MCHI", "FXI"}


def test_load_prices_fixture_has_history_for_momentum_window() -> None:
    # Pin the synthetic fixture (a stale on-disk unified CSV would otherwise
    # win via the default resolution and make this nondeterministic).
    frame = load_prices(fixture_dir=DEFAULT_FIXTURE_DIR)
    assert set(frame["ticker"].unique()) == set(HK_CHINA_TICKERS)
    # ≥ 252 trading days per ticker so 12-month momentum + 200D MA resolve.
    per_ticker = frame.groupby("ticker").size()
    assert per_ticker.min() >= 252


def test_load_prices_as_of_filters_future() -> None:
    full = load_prices(fixture_dir=DEFAULT_FIXTURE_DIR)
    cutoff = date(2023, 6, 30)
    filtered = load_prices(as_of=cutoff, fixture_dir=DEFAULT_FIXTURE_DIR)
    assert filtered["date"].max() <= pd_ts(cutoff)
    assert len(filtered) < len(full)


def pd_ts(d: date):  # tiny helper to avoid importing pandas at module top
    import pandas as pd

    return pd.Timestamp(d)


# --- unified-CSV branch + ticker filter -----------------------------------


def test_load_prices_filters_to_hk_china_tickers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unified CSV holds every Master symbol; load_prices returns only
    the HK-China ETFs (never us_quality / risk-parity rows)."""

    unified = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    _write_prices(
        unified,
        [
            ("2024-01-02", "MCHI", 50.0),
            ("2024-01-02", "KWEB", 30.0),
            ("2024-01-02", "AAPL", 190.0),  # us_quality — must be filtered out
            ("2024-01-02", "SPY", 470.0),   # risk-parity — filtered out
        ],
    )
    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", unified)
    frame = load_prices()
    assert set(frame["ticker"].unique()) == {"MCHI", "KWEB"}


def test_force_fixture_path_overrides_unified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unified = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    _write_prices(unified, [("2024-01-02", "MCHI", 999.0)])
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", unified)
    monkeypatch.setenv("FORCE_FIXTURE_PATH", "1")
    frame = load_prices()
    # Forced to the synthetic fixture, not the 999.0 unified stub.
    assert 999.0 not in set(frame["close"])
    assert set(frame["ticker"].unique()) == set(HK_CHINA_TICKERS)


def test_explicit_fixture_dir_wins(tmp_path: Path) -> None:
    fixture = tmp_path / "fix"
    fixture.mkdir()
    _write_prices(fixture / PRICES_FILE_NAME, [("2024-01-02", "MCHI", 123.0)])
    frame = load_prices(fixture_dir=fixture)
    assert list(frame["close"]) == [123.0]


def test_missing_fixture_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(HkChinaFixtureError):
        load_prices(fixture_dir=tmp_path / "nope")


def test_default_fixture_dir_exists() -> None:
    assert DEFAULT_FIXTURE_DIR.is_dir()
