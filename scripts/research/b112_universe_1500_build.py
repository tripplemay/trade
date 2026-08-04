#!/usr/bin/env python
"""B112 F001-1b — 生产同源 top-1500 PIT 宇宙构建（用户 2026-08-04 裁定）。

发现 B112-F001-1：spec 冻结「top~1500、与生产 precompute 同源」的宇宙口径。
本脚本用**生产同款排序函数**（``point_in_time_top_n``：最新总市值 + 60 日
成交额 composite percent_rank，0.5/0.5，top_n=1500）在 tushare 全市场日频
数据上重建 2019-03-31→2026-06-30 的 30 个季度块：

- 总市值：``b112_marketcap_turnover_fetch.py`` 的 mv_cache（daily_basic，全市场逐日）。
- 成交额：B111 liquidity_cache（2013→2024）+ 本批延伸段（2025→2026-07）。
- 季度块日期复用 ``quarterly_rebalance_dates``（生产同函数）。
- 覆盖率（块内名数、缺数据名数）逐块披露（H6）。

产物：`data/research/b112/cn_pit_universe_1500.csv`（生产同款 UNIVERSE_HEADER）。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from workbench_api.data_refresh.cn_universe import (  # noqa: PLC0415
    MarketCapBar,
    point_in_time_top_n,
    quarterly_rebalance_dates,
)

_MV_CACHE = Path("data/research/b112/mv_cache")
_AMOUNT_CACHE = Path("data/research/B111/liquidity_cache")
_OUT = Path("data/research/b112/cn_pit_universe_1500.csv")
_SUMMARY = Path("data/research/b112/universe_1500_build_summary.json")
TOP_N = 1500


def _load_mv() -> dict[str, list[MarketCapBar]]:
    bars: dict[str, list[MarketCapBar]] = defaultdict(list)
    for path in sorted(_MV_CACHE.glob("mv_*.csv.gz")):
        stem = path.stem.removeprefix("mv_")  # YYYYMMDD
        day = date(int(stem[:4]), int(stem[4:6]), int(stem[6:8]))
        frame = pd.read_csv(path)
        for record in frame.itertuples(index=False):
            mv = getattr(record, "total_mv", None)
            if mv is None or not (mv > 0):
                continue
            bars[str(record.ts_code)].append(
                MarketCapBar(
                    ticker=str(record.ts_code),
                    bar_date=day,
                    total_mv=float(mv),
                    circ_mv=None,
                )
            )
    return bars


def _load_amount() -> dict[str, list[tuple[date, float]]]:
    out: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for path in sorted(_AMOUNT_CACHE.glob("daily_amount_*.csv.gz")):
        stem = path.stem.removeprefix("daily_amount_")
        day = date(int(stem[:4]), int(stem[4:6]), int(stem[6:8]))
        frame = pd.read_csv(path)
        for record in frame.itertuples(index=False):
            amount = getattr(record, "amount", None)
            if amount is None or not (amount > 0):
                continue
            out[str(record.ts_code)].append((day, float(amount)))
    return out


def build(out_path: Path, summary_path: Path) -> dict[str, object]:
    market_caps = _load_mv()
    turnover = _load_amount()
    block_dates = quarterly_rebalance_dates(date(2019, 1, 1), date(2026, 6, 30))
    # 季度块日对齐到 ≤ 该日的最近一个有市值数据的交易日（生产 build 同理用 ≤as_of）。
    mv_days = sorted({bar.bar_date for bars in market_caps.values() for bar in bars})
    import bisect

    rows: list[dict[str, object]] = []
    per_block: list[dict[str, object]] = []
    for block in block_dates:
        pos = bisect.bisect_right(mv_days, block)
        if pos == 0:
            continue
        eval_day = mv_days[pos - 1]
        members = point_in_time_top_n(
            eval_day, market_caps, turnover, top_n=TOP_N, turnover_window_days=60
        )
        for member in members:
            rows.append(
                {
                    "as_of_date": block.isoformat(),
                    "ticker": member.ticker,
                    "rank": member.rank,
                    "market_cap": member.market_cap,
                    "avg_turnover": member.avg_turnover,
                    "composite_score": member.composite_score,
                }
            )
        per_block.append(
            {"as_of_date": block.isoformat(), "eval_day": eval_day.isoformat(), "n": len(members)}
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "as_of_date", "ticker", "rank", "market_cap",
                "avg_turnover", "composite_score",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "top_n": TOP_N,
        "blocks": per_block,
        "rows": len(rows),
        "mv_days": len(mv_days),
        "tickers_with_mv": len(market_caps),
        "tickers_with_amount": len(turnover),
        "note": (
            "生产同源排序（point_in_time_top_n 复用），输入=tushare 全市场；"
            "缺额块（<1500）如实呈现。"
        ),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 top-1500 PIT 宇宙构建")
    parser.add_argument("--out", type=Path, default=_OUT)
    parser.add_argument("--summary", type=Path, default=_SUMMARY)
    args = parser.parse_args(argv)
    summary = build(args.out, args.summary)
    sizes = [b["n"] for b in summary["blocks"]]
    print(
        f"块数 {len(sizes)}  每块 {min(sizes)}–{max(sizes)} 只  总行数 {summary['rows']}"
        f"  → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
