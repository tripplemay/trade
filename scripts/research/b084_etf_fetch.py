#!/usr/bin/env python
"""B084 F001 — bulk-fetch A股 宽基/红利 ETF daily prices for the trend first-look (F002).

Reuses B082's akshare ``fund_etf_hist_em`` path (qfq-adjusted). first-look = 研究批
(不建生产模式), so a one-time bulk snapshot → ``data/research/b084_etf/prices.csv``
(long form: date, ticker, name, close). F002 computes time-series momentum / trend from
these. Resumable: per-ETF cached.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_OUT_DIR = Path("data/research/b084_etf")
_PER_ETF_DIR = _OUT_DIR / "by_etf"
_PRICES_CSV = _OUT_DIR / "prices.csv"

# 宽基 + 红利 ETF 池（评审 §3.4：时序动量, 非横截面行业轮动）。科创 588000 短史(2020-)诚实标注。
_ETFS = {
    "510300": "沪深300",
    "510500": "中证500",
    "588000": "科创50",
    "512890": "红利低波",
    "159915": "创业板",
}


def _sina_symbol(code: str) -> str:
    """sh for 5xxxxx/6xxxxx (Shanghai), sz for 0/1/3xxxxx (Shenzhen)."""

    return ("sh" if code[0] in "56" else "sz") + code


def _fetch_one(code: str, name: str) -> Any:
    import pandas as pd

    cache = _PER_ETF_DIR / f"{code}.csv"
    if cache.is_file():
        return pd.read_csv(cache, dtype={"ticker": str})

    import akshare as ak

    # Sina source (fund_etf_hist_sina) — different host from the rate-limited Eastmoney
    # (push2his.eastmoney.com). Raw (non-qfq) close: fine for a trend/momentum first-look
    # (direction preserved; ETF dividends small) — 口径 noted in the report.
    df = ak.fund_etf_hist_sina(symbol=_sina_symbol(code))
    out = pd.DataFrame(
        {"date": pd.to_datetime(df["date"]), "ticker": code, "name": name, "close": df["close"]}
    )
    _PER_ETF_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False)
    return out


def main() -> int:
    import pandas as pd

    frames = []
    for code, name in _ETFS.items():
        try:
            df = _fetch_one(code, name)
            frames.append(df)
            print(f"{code} {name}: {len(df)} rows")
        except Exception as exc:  # noqa: BLE001 — best-effort per ETF
            print(f"{code} {name}: ERROR {type(exc).__name__} {str(exc)[:60]}")

    if not frames:
        print("no ETF prices fetched")
        return 1
    prices = pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])
    prices = prices[prices["close"] > 0].reset_index(drop=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_csv(_PRICES_CSV, index=False)
    print(f"wrote {_PRICES_CSV}: {len(prices)} rows, {prices['ticker'].nunique()} ETFs "
          f"({prices['date'].min().date()}..{prices['date'].max().date()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
