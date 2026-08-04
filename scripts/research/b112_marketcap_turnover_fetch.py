#!/usr/bin/env python
"""B112 F001-1（fix-round）— top-1500 宇宙排名输入拉取（tushare 三道防线）。

验收 finding B112-F001-1 + 用户 2026-08-04 裁定「先建 1500 宇宙再裁」：
生产同源排序（mcap + 60 日成交额 composite）需要全市场逐日的
``total_mv``（daily_basic）与 ``amount``（daily）。本脚本：

1. ``daily_basic(trade_date, fields=ts_code,total_mv)``：2018-01-01 → 2026-07-31
   全交易日（宇宙窗口 2019-04 起 + 排名 trailing 需要的前置历史）。
2. ``daily(trade_date, fields=ts_code,amount)``：2025-01-01 → 2026-07-31——
   复用 B111 的 liquidity_cache（2013→2024 已缓存，零成本命中）。

防线与 B111 相同（``_fetch_cached``：行数下限 + 长退避 + 整页边界重取 + 绝不缓存
短表/空表）；短表日跳过并逐日披露（H4/H6）。token 只从 .env.local 读（H6）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research.ashare_pit.ep_panel_cli import Ledger, _fetch_cached
from scripts.research.ashare_pit.low_vol_liquidity_fetch import _trading_days
from scripts.research.ashare_pit.vintage_probe import load_token

_MV_CACHE = Path("data/research/b112/mv_cache")
# B111 日成交额缓存（2013→2024 已落盘；本脚本只补 2025+ 段）。
_AMOUNT_CACHE = Path("data/research/B111/liquidity_cache")
_SUMMARY = Path("data/research/b112/mv_amount_fetch_summary.json")

_MIN_ROWS = 1000  # 2018+ 全 A 正常日 >2300 只；<1000 视为静默空/短表（跳过并披露）


def fetch(out_summary: Path, mv_cache: Path, amount_cache: Path) -> dict[str, object]:
    import tushare as ts  # type: ignore[import-untyped]  # noqa: PLC0415

    pro = ts.pro_api(load_token())
    trade_days = _trading_days(pro, "20180101", "20260731")
    ledger = Ledger()
    mv_cache.mkdir(parents=True, exist_ok=True)
    amount_cache.mkdir(parents=True, exist_ok=True)

    short_mv: list[str] = []
    for day in trade_days:
        frame = _fetch_cached(
            pro,
            "daily_basic",
            cache_dir=mv_cache,
            name=f"mv_{day}",
            ledger=ledger,
            min_rows=_MIN_ROWS,
            on_shortfall="disclose",
            trade_date=day,
            fields="ts_code,total_mv",
        )
        if frame.empty:
            short_mv.append(day)

    amount_days = [d for d in trade_days if d >= "20250101"]
    short_amount: list[str] = []
    for day in amount_days:
        frame = _fetch_cached(
            pro,
            "daily",
            cache_dir=amount_cache,
            name=f"daily_amount_{day}",
            ledger=ledger,
            min_rows=_MIN_ROWS,
            on_shortfall="disclose",
            trade_date=day,
            fields="ts_code,amount",
        )
        if frame.empty:
            short_amount.append(day)

    summary: dict[str, object] = {
        "trade_days": len(trade_days),
        "amount_days_fetched": len(amount_days),
        "api_calls": ledger.calls,
        "api_rows": ledger.rows,
        "short_days_mv": short_mv,
        "short_days_amount": short_amount,
        "note": "短表日（行数<下限）跳过不缓存、逐日披露；不参与后续排名输入。",
    }
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 top-1500 宇宙排名输入拉取")
    parser.add_argument("--summary", type=Path, default=_SUMMARY)
    parser.add_argument("--mv-cache", type=Path, default=_MV_CACHE)
    parser.add_argument("--amount-cache", type=Path, default=_AMOUNT_CACHE)
    args = parser.parse_args(argv)
    summary = fetch(args.summary, args.mv_cache, args.amount_cache)
    print(
        f"交易日 {summary['trade_days']}  调用 {summary['api_calls']}  "
        f"短表日 mv={len(summary['short_days_mv'])} amount={len(summary['short_days_amount'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
