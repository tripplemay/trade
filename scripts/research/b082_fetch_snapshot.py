"""B082 F002 — one-shot frozen research snapshot for the 红利低波 defensive sleeve.

Fetches (real akshare, no fakes) the six series the F002 backtest reads and writes
one compact CSV per series under ``data/research/b082/`` (B070 frozen-snapshot mode:
the backtest reads these OFFLINE so a re-run is byte-reproducible). ``data/research``
is git-ignored (the ``data/*`` convention, mirroring ``data/research/b070``); the
snapshot is a LOCAL artifact and the backtest runner can regenerate it deterministically
(``--refetch``). Provenance is documented in ``docs/test-reports/B082-F002-backtest.md``
so an evaluator can independently reproduce it.

Series (endpoints per B082-F001 探针 报告 §1, akshare 1.18.64):
- etf_512890.csv   ← fund_etf_hist_sina("sh512890")        → date,open,high,low,close,volume
- index_h30269.csv ← stock_zh_index_hist_csindex("H30269") → date,close (PR)
- index_h20269.csv ← stock_zh_index_hist_csindex("H20269") → date,close (TR, primary)
- cn_10y_yield.csv ← bond_zh_us_rate("20050101")           → date,yield (percent units)
- gxl_sh.csv       ← stock_a_gxl_lg("上证A股")             → date,dividend_yield (secondary)
- hs300.csv        ← stock_zh_index_daily("sh000300")      → date,close (drawdown 对照基准)

Usage: .venv/bin/python scripts/research/b082_fetch_snapshot.py [--out-dir data/research/b082]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path("data/research/b082")
BOND_10Y_COLUMN = "中国国债收益率10年"


def _coerce_date(value: Any) -> str | None:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    try:
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _write(path: Path, header: list[str], rows: list[list[str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def _fmt(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number != number:  # NaN
        return ""
    return repr(number)


def fetch(out_dir: Path) -> int:
    import akshare as ak

    print(f"akshare {ak.__version__} → {out_dir}", file=sys.stderr)

    # 1) ETF 512890 daily (sina, UNADJUSTED — implementability/cost layer only).
    df = ak.fund_etf_hist_sina(symbol="sh512890")
    rows = []
    for r in df.to_dict("records"):
        d = _coerce_date(r.get("date"))
        if d is None:
            continue
        rows.append([d, _fmt(r.get("open")), _fmt(r.get("high")), _fmt(r.get("low")),
                     _fmt(r.get("close")), _fmt(r.get("volume"))])
    rows.sort(key=lambda x: x[0])
    n = _write(out_dir / "etf_512890.csv",
               ["date", "open", "high", "low", "close", "volume"], rows)
    print(f"  etf_512890: {n} rows [{rows[0][0]}..{rows[-1][0]}]", file=sys.stderr)

    # 2) H30269 price index (PR) + H20269 total-return index (TR, primary口径).
    today = dt.date.today().strftime("%Y%m%d")
    for code, name in (("H30269", "index_h30269"), ("H20269", "index_h20269")):
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date="20050101", end_date=today)
        rows = []
        for r in df.to_dict("records"):
            d = _coerce_date(r.get("日期"))
            close = _fmt(r.get("收盘"))
            if d is None or not close:
                continue
            rows.append([d, close])
        rows.sort(key=lambda x: x[0])
        n = _write(out_dir / f"{name}.csv", ["date", "close"], rows)
        print(f"  {name}: {n} rows [{rows[0][0]}..{rows[-1][0]}]", file=sys.stderr)

    # 3) China 10Y treasury yield (percent units, e.g. 1.74 = 1.74%).
    df = ak.bond_zh_us_rate(start_date="20050101")
    sub = df[["日期", BOND_10Y_COLUMN]].dropna()
    rows = []
    for r in sub.to_dict("records"):
        d = _coerce_date(r.get("日期"))
        y = _fmt(r.get(BOND_10Y_COLUMN))
        if d is None or not y:
            continue
        rows.append([d, y])
    rows.sort(key=lambda x: x[0])
    n = _write(out_dir / "cn_10y_yield.csv", ["date", "yield"], rows)
    print(f"  cn_10y_yield: {n} rows [{rows[0][0]}..{rows[-1][0]}]", file=sys.stderr)

    # 4) Market-level dividend yield (legulegu, secondary/robustness only).
    df = ak.stock_a_gxl_lg(symbol="上证A股")
    rows = []
    for r in df.to_dict("records"):
        d = _coerce_date(r.get("日期"))
        v = _fmt(r.get("股息率"))
        if d is None or not v:
            continue
        rows.append([d, v])
    rows.sort(key=lambda x: x[0])
    n = _write(out_dir / "gxl_sh.csv", ["date", "dividend_yield"], rows)
    print(f"  gxl_sh: {n} rows [{rows[0][0]}..{rows[-1][0]}]", file=sys.stderr)

    # 5) HS300 (沪深300) daily close — drawdown 对照基准 (sina).
    df = ak.stock_zh_index_daily(symbol="sh000300")
    rows = []
    for r in df.to_dict("records"):
        d = _coerce_date(r.get("date"))
        close = _fmt(r.get("close"))
        if d is None or not close:
            continue
        rows.append([d, close])
    rows.sort(key=lambda x: x[0])
    n = _write(out_dir / "hs300.csv", ["date", "close"], rows)
    print(f"  hs300: {n} rows [{rows[0][0]}..{rows[-1][0]}]", file=sys.stderr)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=SNAPSHOT_DIR)
    args = parser.parse_args()
    return fetch(args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
