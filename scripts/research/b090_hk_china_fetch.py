#!/usr/bin/env python
"""B090 F001 — fetch the HK/China real universe + proxy ETFs + FX for the retest.

Research-only (touches NO strategy/production code). Fetches every ticker in
:data:`trade.data.hk_china_real_universe.REAL_UNIVERSE_TICKERS` (16 HK + 10
mainland A-share) plus the four proxy ETFs (MCHI/FXI/KWEB/ASHR) and the shared
defensive asset SGOV into ONE unified long-format frame matching
:data:`trade.data.hk_china_real_universe.PRICES_REQUIRED_COLUMNS`
(``date,ticker,open,high,low,close,adj_close,volume``; canonical tickers,
``adj_close`` = qfq-adjusted close). It also fetches FRED DEXHKUS + DEXCHUS into
an FX CSV (``date,currency,rate``; LOCAL-per-USD) that
:class:`trade.data.fx.FxConverter` reads.

Sources (all offline-fetchable, no API key):
  * HK  ('0700.HK') -> akshare.stock_hk_daily(symbol='00700', adjust='qfq')
  * A   ('600519.SH') -> akshare.stock_zh_a_daily(symbol='sh600519', adjust='qfq')
        (sina host — eastmoney's stock_zh_a_hist is SSL/rate-limit flaky)
  * US  ('MCHI') -> akshare.stock_us_daily(symbol='MCHI', adjust='qfq')
  * FX  -> https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXHKUS|DEXCHUS

Honesty caveat: qfq-adjusted close ~= total-return adj_close, NOT identical to
the Tiingo adj_close the flagship uses. Fetch is resilient — a ticker that 404s
or errors is logged + skipped, and coverage is reported. Per-ticker + combined
outputs cached under ``data/research/b090_hk/`` (gitignored) so re-runs resume.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from trade.data.hk_china_real_universe import (
    PRICES_REQUIRED_COLUMNS,
    REAL_UNIVERSE_TICKERS,
    currency_for,
)

if TYPE_CHECKING:
    import pandas as pd

_OUT_DIR = Path("data/research/b090_hk")
_BY_TICKER_DIR = _OUT_DIR / "by_ticker"
_UNIFIED_CSV = _OUT_DIR / "unified_prices.csv"
_FX_CSV = _OUT_DIR / "fx_daily.csv"

# US-listed proxy ETFs + shared defensive asset (all USD, stock_us_daily qfq).
_PROXY_TICKERS: tuple[str, ...] = ("MCHI", "FXI", "KWEB", "ASHR")
_DEFENSIVE_TICKER = "SGOV"

# FRED series: LOCAL-currency-per-USD. currency label matches currency_for().
_FRED_SERIES: dict[str, str] = {"HKD": "DEXHKUS", "CNY": "DEXCHUS"}


def hk_canonical_to_symbol(ticker: str) -> str:
    """'0700.HK' -> '00700' (strip '.HK', zero-pad the numeric part to 5 digits)."""

    numeric = ticker.strip().upper().removesuffix(".HK")
    return numeric.zfill(5)


def a_canonical_to_symbol(ticker: str) -> str:
    """'600519.SH' -> 'sh600519', '000858.SZ' -> 'sz000858' (sina symbol form)."""

    upper = ticker.strip().upper()
    if upper.endswith(".SH"):
        return "sh" + upper.removesuffix(".SH")
    if upper.endswith(".SZ"):
        return "sz" + upper.removesuffix(".SZ")
    raise ValueError(f"not an A-share canonical ticker: {ticker!r}")


def _normalize_frame(raw: pd.DataFrame, canonical: str) -> pd.DataFrame:
    """Project a source OHLCV frame to the unified schema (adj_close = qfq close).

    All sources return qfq-adjusted ``close`` (and open/high/low), so ``close``
    and ``adj_close`` are set to the same qfq value. Rows with a non-positive or
    missing close/volume are dropped (honest — never fabricated)."""

    import pandas as pd

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["date"]).dt.strftime("%Y-%m-%d"),
            "ticker": canonical,
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "adj_close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
        }
    )
    out = out.dropna(subset=["close", "volume"])
    out = out[out["close"] > 0].reset_index(drop=True)
    return out[list(PRICES_REQUIRED_COLUMNS)]


def _fetch_raw(canonical: str) -> pd.DataFrame:
    """Fetch one ticker's raw OHLCV from the right akshare source by market."""

    import akshare as ak

    currency = currency_for(canonical)
    if currency == "HKD":
        return ak.stock_hk_daily(symbol=hk_canonical_to_symbol(canonical), adjust="qfq")
    if currency == "CNY":
        return ak.stock_zh_a_daily(symbol=a_canonical_to_symbol(canonical), adjust="qfq")
    return ak.stock_us_daily(symbol=canonical, adjust="qfq")


def _fetch_one(canonical: str) -> pd.DataFrame:
    """Cached per-ticker fetch → normalized unified-schema frame."""

    import pandas as pd

    cache = _BY_TICKER_DIR / f"{canonical.replace('.', '_')}.csv"
    if cache.is_file():
        return pd.read_csv(cache, dtype={"ticker": str})
    frame = _normalize_frame(_fetch_raw(canonical), canonical)
    _BY_TICKER_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache, index=False)
    return frame


def fetch_prices() -> tuple[pd.DataFrame, list[str], list[str]]:
    """Fetch all 31 tickers → (unified_frame, covered, missing)."""

    import pandas as pd

    all_tickers = (*REAL_UNIVERSE_TICKERS, *_PROXY_TICKERS, _DEFENSIVE_TICKER)
    frames: list[pd.DataFrame] = []
    covered: list[str] = []
    missing: list[str] = []
    for canonical in all_tickers:
        try:
            frame = _fetch_one(canonical)
        except Exception as exc:  # noqa: BLE001 — best-effort per ticker
            missing.append(canonical)
            print(f"  SKIP {canonical}: {type(exc).__name__} {str(exc)[:70]}")
            continue
        if frame.empty:
            missing.append(canonical)
            print(f"  SKIP {canonical}: empty frame")
            continue
        frames.append(frame)
        covered.append(canonical)
        print(
            f"  OK   {canonical}: {len(frame)} rows "
            f"({frame['date'].min()}..{frame['date'].max()})"
        )
    if not frames:
        empty = pd.DataFrame(columns=list(PRICES_REQUIRED_COLUMNS))
        return empty, covered, missing
    unified = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    return unified, covered, missing


def parse_fred_csv(text: str, currency: str) -> list[tuple[str, str, float]]:
    """Parse a FRED ``observation_date,<series>`` CSV → [(date, currency, rate)].

    Pure (no IO) so it is unit-testable. Rows valued ``.`` (FRED holidays) or
    otherwise non-numeric are skipped; the header line is dropped."""

    rows: list[tuple[str, str, float]] = []
    for line in text.strip().splitlines()[1:]:  # skip header
        parts = line.split(",")
        if len(parts) != 2:
            continue
        obs_date, value = parts[0].strip(), parts[1].strip()
        if value == "." or not value:
            continue
        try:
            rate = float(value)
        except ValueError:
            continue
        rows.append((obs_date, currency, rate))
    return rows


def _fred_rows(currency: str, series_id: str) -> list[tuple[str, str, float]]:
    """Fetch one FRED series → [(date, currency, rate)]; '.' holiday rows skipped."""

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 — fixed FRED host
        text = response.read().decode("utf-8")
    return parse_fred_csv(text, currency)


def fetch_fx() -> pd.DataFrame:
    """Fetch DEXHKUS + DEXCHUS → long FX frame (date,currency,rate; LOCAL-per-USD)."""

    import pandas as pd

    records: list[tuple[str, str, float]] = []
    for currency, series_id in _FRED_SERIES.items():
        series_rows = _fred_rows(currency, series_id)
        records.extend(series_rows)
        print(f"  FX {currency} ({series_id}): {len(series_rows)} obs")
    return pd.DataFrame(records, columns=["date", "currency", "rate"]).sort_values(
        ["currency", "date"]
    )


def main() -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching prices (31 tickers: 26 real + 4 proxy + SGOV) ...")
    unified, covered, missing = fetch_prices()
    unified.to_csv(_UNIFIED_CSV, index=False)
    n_real = len([t for t in covered if t in REAL_UNIVERSE_TICKERS])
    print(
        f"wrote {_UNIFIED_CSV}: {len(unified)} rows, {len(covered)}/31 tickers "
        f"({n_real}/{len(REAL_UNIVERSE_TICKERS)} real). missing={missing}"
    )

    print("Fetching FX (FRED DEXHKUS + DEXCHUS) ...")
    fx = fetch_fx()
    fx.to_csv(_FX_CSV, index=False)
    print(f"wrote {_FX_CSV}: {len(fx)} rows, currencies={sorted(fx['currency'].unique())}")

    return 0 if not unified.empty and not fx.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
