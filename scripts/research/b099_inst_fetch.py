#!/usr/bin/env python
"""B099 — fetch the QUARTERLY institutional-holding panel + qfq prices for an
institutional-BUILDING (机构建仓) first-look.

This is the FREE, QUARTERLY sleeve of the user's REAL goal (跟踪机构建仓动向跟随获利
— track institutions building positions and follow). Unlike 游资 (B094, retail
hot-money, NO-GO), this uses genuine INSTITUTIONAL holdings sourced from the quarterly
reports' 十大流通股东 (top-float holders). The paid ¥200 Tushare version is DAILY
(LHB institutional seats); this free version is QUARTERLY and disclosed with a LAG.
A NO-GO / INCONCLUSIVE is a fully valid, valuable outcome.

Data (free via akshare, no key):
  * PANEL   ``stock_institute_hold(symbol='<YYYY><Q>')`` — one row per stock per quarter:
            证券代码 / 证券简称 / 机构数 / 机构数变化 / 持股比例 / 持股比例增幅 /
            占流通股比例 / 占流通股比例增幅. symbol '20241' = 2024 Q1, '20203' = 2020 Q3.
            ~1900-3100 stocks/quarter. Fetched for 2020Q1..2024Q4 (20 quarters).
  * PRICES  Reused from the B070/B081 SURVIVORSHIP-FREE PIT qfq cache
            (``data/research/b070/b081_prices_cache.pkl``, 2018-2026, adj_close).
            That universe (~1310 liquid names) is the DETERMINISTIC LIQUID SUBSET /
            documented cap — selected by B070 on size/liquidity/quality, INDEPENDENT of
            the institutional-building signal (so it does not bias the signal). ~27% of
            the institutional universe overlaps (a large/liquid tilt — stated in report).

★ No look-ahead is enforced downstream in b099_inst_ic.py (disclosure-lagged entry).
research-only / no broker / no real money / no production change / no paid data.
"""

from __future__ import annotations

import argparse
import csv
import logging
import pickle
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUT_DIR = Path("data/research/b099_inst")
_PANEL_CSV = _OUT_DIR / "inst_panel.csv"
_PRICES_PKL = _OUT_DIR / "prices.pkl"
_COVERAGE_JSON = _OUT_DIR / "coverage.json"
_B070_PRICE_CACHE = Path("data/research/b070/b081_prices_cache.pkl")

PANEL_HEADER = (
    "quarter", "code", "name", "n_inst", "n_inst_chg",
    "hold_pct", "hold_pct_chg", "float_pct", "float_pct_chg",
)

# akshare column names (verified live 2026-07-06).
_C_CODE, _C_NAME, _C_NINST, _C_NCHG = "证券代码", "证券简称", "机构数", "机构数变化"
_C_HOLD, _C_HCHG, _C_FLOAT, _C_FCHG = "持股比例", "持股比例增幅", "占流通股比例", "占流通股比例增幅"


def quarters(start_year: int, start_q: int, end_year: int, end_q: int) -> list[str]:
    """akshare symbols '<YYYY><Q>' for an inclusive quarter range."""
    out: list[str] = []
    y, q = start_year, start_q
    while (y, q) <= (end_year, end_q):
        out.append(f"{y}{q}")
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return out


def fetch_panel(qsyms: list[str], pause: float = 0.4) -> list[tuple[Any, ...]]:
    """Fetch the institutional-holding panel for each quarter symbol.

    Best-effort: a failed quarter is logged + skipped, never fatal.
    """
    import akshare as ak

    rows: list[tuple[Any, ...]] = []
    for sym in qsyms:
        try:
            df = ak.stock_institute_hold(symbol=sym)
        except Exception as exc:  # noqa: BLE001 - best-effort per quarter
            logger.warning("panel fetch failed %s: %r", sym, exc)
            continue
        for _, r in df.iterrows():
            rows.append((
                sym, str(r[_C_CODE]), str(r[_C_NAME]),
                _num(r.get(_C_NINST)), _num(r.get(_C_NCHG)),
                _num(r.get(_C_HOLD)), _num(r.get(_C_HCHG)),
                _num(r.get(_C_FLOAT)), _num(r.get(_C_FCHG)),
            ))
        logger.info("panel %s: %d rows", sym, len(df))
        time.sleep(pause)
    return rows


def _num(v: Any) -> Any:
    try:
        import math

        f = float(v)
        return "" if math.isnan(f) else f
    except (TypeError, ValueError):
        return ""


def _six(s: Any) -> Any:
    return s.astype(str).str.extract(r"(\d{6})")[0]


def materialize_prices(panel_codes: set[str]) -> dict[str, Any]:
    """Slice the B070 survivorship-free PIT qfq cache down to the institutional
    universe intersection and write it to the B099 cache. Returns coverage stats."""
    import pandas as pd

    with open(_B070_PRICE_CACHE, "rb") as fh:
        px: pd.DataFrame = pickle.load(fh)  # noqa: S301
    px = px.copy()
    px["code6"] = _six(px["ticker"])
    keep = px[px["code6"].isin(panel_codes)].copy()
    keep = keep[keep["date"] >= pd.Timestamp("2019-10-01")]
    # Sanity guard (B092 pre-2017 corruption); window is 2019+ so expect clean.
    keep = keep[keep["adj_close"] > 0]
    sub = keep[["date", "code6", "adj_close"]].rename(columns={"code6": "code"})
    sub = sub.sort_values(["code", "date"]).reset_index(drop=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    sub.to_pickle(_PRICES_PKL)
    return {
        "price_universe_tickers": int(sub["code"].nunique()),
        "price_rows": int(len(sub)),
        "price_date_min": str(sub["date"].min().date()),
        "price_date_max": str(sub["date"].max().date()),
        "panel_codes": len(panel_codes),
        "overlap_tickers": int(sub["code"].nunique()),
        "overlap_pct": round(100 * sub["code"].nunique() / max(len(panel_codes), 1), 1),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="B099 institutional-holding panel fetch")
    ap.add_argument("--start", default="2020,1")
    ap.add_argument("--end", default="2024,4")
    ap.add_argument("--pause", type=float, default=0.4)
    args = ap.parse_args(argv)

    sy, sq = (int(x) for x in args.start.split(","))
    ey, eq = (int(x) for x in args.end.split(","))
    qsyms = quarters(sy, sq, ey, eq)
    logger.info("fetching %d quarters: %s .. %s", len(qsyms), qsyms[0], qsyms[-1])

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = fetch_panel(qsyms, pause=args.pause)
    with open(_PANEL_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(PANEL_HEADER)
        w.writerows(rows)
    logger.info("wrote %d panel rows -> %s", len(rows), _PANEL_CSV)

    codes = {r[1] for r in rows}
    cov = materialize_prices(codes)

    import json

    per_q: dict[str, int] = {}
    for r in rows:
        per_q[r[0]] = per_q.get(r[0], 0) + 1
    coverage = {
        "quarters": qsyms,
        "n_quarters": len(qsyms),
        "n_quarters_fetched": len(per_q),
        "panel_rows": len(rows),
        "stocks_per_quarter": per_q,
        "panel_unique_codes": len(codes),
        **cov,
    }
    with open(_COVERAGE_JSON, "w") as f:
        json.dump(coverage, f, ensure_ascii=False, indent=2)
    logger.info("coverage -> %s", json.dumps(coverage, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
