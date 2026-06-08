"""Deterministic synthetic-fixture generator for BL-B011-S2 HK-China.

Run once to (re)produce ``universe.csv`` + ``prices_daily.csv``. The data
is SYNTHETIC — distinct per-ticker trends so the strategy unit tests
(F002) can assert momentum / trend / regional-risk behaviour against known
shapes — and is NOT real market data. Re-run:

    python data/fixtures/hk_china_momentum/_generate.py

Determinism: a fixed per-ticker seed drives a geometric random walk, so
the output is byte-stable across runs (no wall-clock / unseeded RNG).
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# (ticker, name, exposure, listing_date, seed, annual_drift, annual_vol)
# Drifts are chosen so the fixture spans clear regimes: KWEB strong up,
# MCHI moderate up, FXI mild, ASHR down — enough spread for top-1/2 +
# trend-filter + regional-risk tests downstream.
_TICKERS = [
    ("MCHI", "iShares MSCI China ETF", "MSCI China", date(2011, 3, 31), 11, 0.18, 0.22),
    ("FXI", "iShares China Large-Cap ETF", "China Large-Cap", date(2004, 10, 5), 12, 0.05, 0.24),
    (
        "KWEB", "KraneShares CSI China Internet ETF", "China Internet",
        date(2013, 7, 31), 13, 0.30, 0.34,
    ),
    (
        "ASHR", "Xtrackers Harvest CSI 300 A-Shares ETF", "China A-Shares",
        date(2013, 11, 6), 14, -0.12, 0.26,
    ),
]

START = date(2023, 1, 2)
TRADING_DAYS = 460  # ≥ 252 (12m momentum) + 200 (MA) headroom


def _business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    cur = start
    while len(days) < count:
        if cur.weekday() < 5:  # Mon-Fri
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _walk(seed: int, drift: float, vol: float, n: int, start_price: float) -> list[float]:
    rng = random.Random(seed)
    daily_drift = drift / 252.0
    daily_vol = vol / math.sqrt(252.0)
    price = start_price
    out = [price]
    for _ in range(n - 1):
        shock = rng.gauss(daily_drift, daily_vol)
        price = max(1.0, price * (1.0 + shock))
        out.append(round(price, 2))
    return out


def main() -> None:
    days = _business_days(START, TRADING_DAYS)

    with (OUT_DIR / "universe.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "name", "exposure", "listing_date"])
        for ticker, name, exposure, listing, *_ in _TICKERS:
            w.writerow([ticker, name, exposure, listing.isoformat()])

    rows: list[list[object]] = []
    for ticker, _name, _exp, _listing, seed, drift, vol in _TICKERS:
        closes = _walk(seed, drift, vol, len(days), start_price=40.0)
        for d, close in zip(days, closes, strict=True):
            o = round(close * 0.999, 2)
            hi = round(close * 1.008, 2)
            lo = round(close * 0.992, 2)
            vol_shares = 1_000_000 + (seed * 1000)
            rows.append([d.isoformat(), ticker, o, hi, lo, close, close, vol_shares])

    # Sort by (date, ticker) to mirror the unified CSV layout.
    rows.sort(key=lambda r: (r[0], r[1]))
    with (OUT_DIR / "prices_daily.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])
        w.writerows(rows)

    print(f"wrote {len(rows)} price rows over {len(days)} trading days for {len(_TICKERS)} ETFs")


if __name__ == "__main__":
    main()
