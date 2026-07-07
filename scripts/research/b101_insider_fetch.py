#!/usr/bin/env python
"""B101 — fetch major-shareholder / executive NET-BUYING (大股东/高管增持) events +
qfq prices for an insider-buying first-look.

This is the MOST PROMISING free "smart-money" angle: insider / major-holder BUYING is
a known mild-alpha signal globally and in A-shares (insiders / large holders accumulate
before good news). Unlike 游资 retail hot-money (B094 NO-GO) or quarterly fund holdings
(B099 NO-GO), 增持 is genuine INSIDER / 大资金 accumulation. A NO-GO / INCONCLUSIVE is a
fully valid, valuable outcome (it would mean even the most promising free angle fails).

Data (free via akshare, no key):
  * EVENTS  ``stock_ggcg_em(symbol='股东增持')`` — 东方财富 高管持股 增持-only feed.
            ~33k rows. Columns (verified live 2026-07-06):
              代码 / 名称 / 股东名称 / 持股变动信息-增减(=增持) /
              持股变动信息-变动数量(万股) / 持股变动信息-占总股本比例(%) /
              变动开始日 / 变动截止日(TRANSACTION date) / 公告日(ANNOUNCEMENT date).
            ★ Crucially carries BOTH the transaction date (变动截止日) AND the
              announcement / disclosure date (公告日). 公告日 >= 变动截止日 (disclosure
              lag), so entry can be pinned to the PUBLIC date — no look-ahead.
            The '股东增持' filter (buys only) is ~2x faster than '全部'.
  * PRICES  Reused from the B070/B081 SURVIVORSHIP-FREE PIT qfq cache
            (``data/research/b070/b081_prices_cache.pkl``, 2018-2026, adj_close, 1310
            liquid names). That universe is a DETERMINISTIC LIQUID SUBSET selected by
            B070 on size/liquidity/quality, INDEPENDENT of the insider-buying signal
            (so it does not bias the signal). The overlap is the tradeable universe;
            overlap % is reported in coverage.

★ No look-ahead is enforced downstream in b101_insider_ic.py (announcement-dated entry).
research-only / no broker / no real money / no production change / no paid data.
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUT_DIR = Path("data/research/b101_insider")
_EVENTS_CSV = _OUT_DIR / "insider_events.csv"
_PRICES_PKL = _OUT_DIR / "prices.pkl"
_COVERAGE_JSON = _OUT_DIR / "coverage.json"
_B070_PRICE_CACHE = Path("data/research/b070/b081_prices_cache.pkl")

# Output event schema (one row per 增持 record).
EVENTS_HEADER = (
    "code", "name", "holder", "chg_shares_wan", "chg_pct_total",
    "txn_end_date", "announce_date",
)

# akshare column names (verified live 2026-07-06).
_C_CODE, _C_NAME, _C_HOLDER = "代码", "名称", "股东名称"
_C_DIR = "持股变动信息-增减"
_C_QTY = "持股变动信息-变动数量"
_C_PCT = "持股变动信息-占总股本比例"
_C_TXN_END = "变动截止日"
_C_ANNOUNCE = "公告日"


def fetch_events(symbol: str = "股东增持", retries: int = 4, pause: float = 5.0) -> Any:
    """Fetch the 增持 event feed from 东方财富 via akshare (buys only).

    The feed paginates ~67 pages (~3 min); a mid-stream network hiccup
    (ChunkedEncodingError) is transient, so retry the whole call a few times.
    """
    import akshare as ak

    last: Exception | None = None
    for attempt in range(1, retries + 1):
        t0 = time.time()
        try:
            df = ak.stock_ggcg_em(symbol=symbol)
            logger.info("fetched %d raw rows in %.0fs (attempt %d)",
                        len(df), time.time() - t0, attempt)
            return df
        except Exception as exc:  # noqa: BLE001 - transient network, retry whole call
            last = exc
            logger.warning("fetch attempt %d failed: %r; retrying in %.0fs",
                           attempt, exc, pause)
            time.sleep(pause)
    raise RuntimeError(f"fetch_events failed after {retries} attempts") from last


def normalize_events(df: Any) -> Any:
    """Coerce raw akshare frame to the clean event schema, keeping only 增持 buys with
    a parseable code + both transaction and announcement dates + positive qty."""
    import pandas as pd

    out = pd.DataFrame({
        "code": df[_C_CODE].astype(str).str.extract(r"(\d{6})")[0],
        "name": df[_C_NAME].astype(str),
        "holder": df[_C_HOLDER].astype(str),
        "direction": df[_C_DIR].astype(str),
        "chg_shares_wan": pd.to_numeric(df[_C_QTY], errors="coerce"),
        "chg_pct_total": pd.to_numeric(df[_C_PCT], errors="coerce"),
        "txn_end_date": pd.to_datetime(df[_C_TXN_END], errors="coerce"),
        "announce_date": pd.to_datetime(df[_C_ANNOUNCE], errors="coerce"),
    })
    out = out[out["direction"].str.contains("增")]  # buys only (defensive)
    out = out.dropna(subset=["code", "txn_end_date", "announce_date"])
    out = out[out["chg_shares_wan"] > 0]
    # Announcement must be on/after the transaction end (disclosure lag).
    out = out[out["announce_date"] >= out["txn_end_date"]]
    out = out[list(EVENTS_HEADER)].sort_values(
        ["announce_date", "code"]).reset_index(drop=True)
    return out


def _six(s: Any) -> Any:
    return s.astype(str).str.extract(r"(\d{6})")[0]


def materialize_prices(event_codes: set[str], date_min: str) -> dict[str, Any]:
    """Slice the B070 survivorship-free PIT qfq cache to the insider universe."""
    import pandas as pd

    with open(_B070_PRICE_CACHE, "rb") as fh:
        px: pd.DataFrame = pickle.load(fh)  # noqa: S301
    px = px.copy()
    px["code6"] = _six(px["ticker"])
    keep = px[px["code6"].isin(event_codes)].copy()
    keep = keep[keep["date"] >= pd.Timestamp(date_min)]
    keep = keep[keep["adj_close"] > 0]  # B092 corruption guard (window is 2018+)
    sub = keep[["date", "code6", "adj_close"]].rename(columns={"code6": "code"})
    sub = sub.sort_values(["code", "date"]).reset_index(drop=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    sub.to_pickle(_PRICES_PKL)
    return {
        "price_tickers": int(sub["code"].nunique()),
        "price_rows": int(len(sub)),
        "price_date_min": str(sub["date"].min().date()),
        "price_date_max": str(sub["date"].max().date()),
        "event_codes": len(event_codes),
        "overlap_tickers": int(sub["code"].nunique()),
        "overlap_pct": round(100 * sub["code"].nunique() / max(len(event_codes), 1), 1),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="B101 insider-buying event fetch")
    ap.add_argument("--symbol", default="股东增持")
    ap.add_argument("--price-date-min", default="2018-01-01")
    args = ap.parse_args(argv)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = fetch_events(args.symbol)
    events = normalize_events(raw)
    events.to_csv(_EVENTS_CSV, index=False)
    logger.info("wrote %d clean events -> %s", len(events), _EVENTS_CSV)

    codes = set(events["code"].unique())
    cov_px = materialize_prices(codes, args.price_date_min)

    # Announcement-lag descriptive stats (公告日 - 变动截止日, trading-agnostic days).
    lag = (events["announce_date"] - events["txn_end_date"]).dt.days
    coverage = {
        "source_function": "ak.stock_ggcg_em(symbol='股东增持')",
        "n_events": int(len(events)),
        "n_unique_stocks": int(events["code"].nunique()),
        "announce_date_min": str(events["announce_date"].min().date()),
        "announce_date_max": str(events["announce_date"].max().date()),
        "txn_end_date_min": str(events["txn_end_date"].min().date()),
        "txn_end_date_max": str(events["txn_end_date"].max().date()),
        "announce_lag_days_median": float(lag.median()),
        "announce_lag_days_mean": round(float(lag.mean()), 1),
        "announce_lag_days_p90": float(lag.quantile(0.90)),
        "has_announcement_date": True,
        **cov_px,
    }
    with open(_COVERAGE_JSON, "w") as f:
        json.dump(coverage, f, ensure_ascii=False, indent=2)
    logger.info("coverage -> %s", json.dumps(coverage, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
