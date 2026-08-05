#!/usr/bin/env python
"""B112 F001-1c — 1500 宇宙新名价格回填（baostock qfq，与 b070 cache 同口径）。

1500 宇宙的季度块全集（~2000+ 只）超出既有价格集（b081 cache 1310 + 生产延伸
1494）的名，用 baostock 日 K（``adjustflag="2"`` qfq，``tradestatus`` 含停牌位）
逐只回填 2018-01-01→2026-07-31。与 b070 拉取同机制：单 baostock 会话整批
（F001 §5 #5）、逐只缓存、中断重跑零成本。

产物：`data/research/b112/prices_newnames.pkl`（schema 与 b081 cache 一致：
``date,ticker,open,high,low,close,adj_close,volume,tradestatus``；qfq 故
``adj_close == close``，只有收益跨名可比）。
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from scripts.research.b070_survivorship_free import to_baostock

_UNIVERSE = Path("data/research/b112/cn_pit_universe_1500.csv")
_PRICES_BASE = Path("data/research/b070/b081_prices_cache.pkl")
_PRICES_EXT = Path("data/research/b112/b112_prices_ext.pkl")
_CACHE_DIR = Path("data/research/b112/prices_new_cache")
_OUT = Path("data/research/b112/prices_newnames.pkl")
_START = "2018-01-01"
_END = "2026-07-31"
_K_FIELDS = "date,open,high,low,close,volume,tradestatus"


def missing_tickers(universe_path: Path) -> list[str]:
    universe = pd.read_csv(universe_path)
    wanted = set(universe["ticker"].unique())
    covered = set(pd.read_pickle(_PRICES_BASE)["ticker"].unique())
    covered |= set(pd.read_pickle(_PRICES_EXT)["ticker"].unique())
    return sorted(wanted - covered)


def fetch(out_path: Path, cache_dir: Path, universe_path: Path) -> tuple[int, int]:
    import baostock as bs  # noqa: PLC0415 — 联网依赖，仅回填时导入

    wanted = missing_tickers(universe_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    todo = [t for t in wanted if not (cache_dir / f"{t}.csv").exists()]
    print(f"宇宙名 {len(wanted)} 只待补；已有缓存 {len(wanted) - len(todo)}，待拉 {len(todo)}")

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock login failed: {lg.error_msg}")
    failed: list[str] = []
    done = 0
    try:
        for ticker in todo:
            try:
                code = to_baostock(ticker)
                rs = bs.query_history_k_data_plus(
                    code, _K_FIELDS, start_date=_START, end_date=_END,
                    frequency="d", adjustflag="2",
                )
            except Exception as exc:  # noqa: BLE001 — 留痕后继续（含不支持的板块码）
                failed.append(f"{ticker}: {exc!r}")
                continue
            rows: list[dict[str, object]] = []
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                rows.append(
                    {
                        "date": row[0],
                        "ticker": ticker,
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "adj_close": row[4],  # qfq（adjustflag=2）
                        "volume": row[5],
                        "tradestatus": row[6],
                    }
                )
            if not rows:
                failed.append(f"{ticker}: empty k-data")
                continue
            pd.DataFrame(rows).to_csv(cache_dir / f"{ticker}.csv", index=False)
            done += 1
            if done % 50 == 0:
                print(f"  …{done}/{len(todo)}", flush=True)
            time.sleep(0.25)
    finally:
        bs.logout()

    frames = [pd.read_csv(path) for path in sorted(cache_dir.glob("*.csv"))]
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    merged.to_pickle(out_path)
    if failed:
        (out_path.parent / "prices_newnames_failures.txt").write_text(
            "\n".join(failed) + "\n", encoding="utf-8"
        )
    return len(merged), len(failed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 1500 宇宙新名价格回填")
    parser.add_argument("--out", type=Path, default=_OUT)
    parser.add_argument("--cache-dir", type=Path, default=_CACHE_DIR)
    parser.add_argument("--universe", type=Path, default=_UNIVERSE)
    args = parser.parse_args(argv)
    rows, failures = fetch(args.out, args.cache_dir, args.universe)
    print(f"落盘行数: {rows}  失败: {failures}  → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
