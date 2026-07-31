"""B111 F005 fix-round — 正式 G2 的日成交额拉取 + 12 个月日均窗口构建。

验收 finding B111-F007-1：首轮 G2 只用了形成日**单日**成交额代理，未执行
spec §B.2 冻结的「**日均**成交额过滤」。本脚本拉取 2013-01～2024-12 **每个交易日**
的全市场 `daily.amount`（复用 `liquidity_cache` 既有日缓存，三道防线不变），
并对每个形成日构建**无前视的 12 个自然月日均成交额**：

- 形成日 t 的窗口 = **(t 前 12 个月, t]** 内的全部交易日（与 σ 排序的
  t-12…t-1 窗口同一段历史，严格无前视：所有交易日 ≤ t）。
- 个股日均 = 窗口内该股票**有成交记录的日子**的 amount 均值（A 股停牌日无记录；
  停牌本身不视为零成交——披露覆盖天数 `n_days`，不静默 dropna，H4）。
- 输出 `formation_date, ts_code, avg_amount_12m, n_days`，与首轮单日代理文件
  同形，供 `low_vol_cli.py --liquidity` 直接消费。

★成本说明：约 2800 个交易日的全市场分页拉取（每交易日 1 次调用级别），
是 finding B111-F007-1 要求重跑正式 G2 的必要成本；缓存落盘，重跑零成本。
token 只从 `.env.local` 读（H6）。
"""

from __future__ import annotations

import argparse
import csv
import gzip
from collections import defaultdict
from pathlib import Path

from scripts.research.ashare_pit.ep_panel_cli import Ledger, _fetch_cached
from scripts.research.ashare_pit.low_vol_liquidity_fetch import (
    _MIN_ROWS,
    _trading_days,
)
from scripts.research.ashare_pit.vintage_probe import load_token

WINDOW_MONTHS = 12  # 形成日前的自然月数（与 σ 排序窗口同段历史）


def _formation_dates(detail_path: Path) -> list[str]:
    with gzip.open(detail_path, "rt", encoding="utf-8", newline="") as handle:
        return sorted({row["formation_date"] for row in csv.DictReader(handle)})


def _shift_months(yyyymmdd: str, months: int) -> str:
    """``20140131`` 前移 12 个月 → ``20130131``（仅按年月平移，日对齐原值）。"""
    year = int(yyyymmdd[:4])
    month = int(yyyymmdd[4:6])
    total = (year * 12 + (month - 1)) + months
    return f"{total // 12}{total % 12 + 1:02d}{yyyymmdd[6:]}"


def _read_cached_amounts(cache_dir: Path, trade_date: str) -> dict[str, float]:
    """读已落盘的单日缓存 → ``{ts_code: amount}``（缓存文件由 _fetch_cached 写入）。"""
    path = cache_dir / f"daily_amount_{trade_date}.csv.gz"
    out: dict[str, float] = {}
    if not path.exists():
        return out
    import pandas as pd

    frame = pd.read_csv(path)
    for record in frame.itertuples(index=False):
        amount = getattr(record, "amount", None)
        if amount is not None:
            out[str(record.ts_code)] = float(amount)
    return out


def fetch_daily_amounts(
    detail_path: Path,
    out_path: Path,
    cache_dir: Path,
    *,
    summary_path: Path | None = None,
) -> tuple[int, int, int]:
    """拉全日历日成交额并落盘 12 月日均 CSV。返回 (交易日数, 形成日数, 落盘行数)。

    ★短表处置（H4）：单日行数低于 `_MIN_ROWS` 下限的交易日**跳过不缓存**
    （`_fetch_cached(on_shortfall="disclose")`），该日不参与任何股票的均值，
    并逐日记入 ``short_days_skipped`` 披露——2015-07 停牌潮期间单日真实交易
    家数可低于 1500（邻日实测 2371→2044→1489 逐日递减），但宁可丢弃也不
    接纳无法与静默截断区分的短表。12 月窗口约 240 个交易日，跳过 1-3 日
    对均值无实质影响。
    """

    import tushare as ts  # type: ignore[import-untyped]  # noqa: PLC0415 — 联网依赖，仅拉取时导入

    pro = ts.pro_api(load_token())
    formation_dates = _formation_dates(detail_path)
    # 最早的 12 月窗口起点（首个形成日前 12 个月）到最后一个形成日。
    first_window_start = _shift_months(formation_dates[0], -WINDOW_MONTHS)
    trade_days = _trading_days(pro, f"{first_window_start[:4]}0101", formation_dates[-1])
    ledger = Ledger()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1) 逐交易日拉全市场 amount（命中缓存的零成本；短表跳过不缓存）。
    short_days: list[str] = []
    for trade_date in trade_days:
        frame = _fetch_cached(
            pro,
            "daily",
            cache_dir=cache_dir,
            name=f"daily_amount_{trade_date}",
            ledger=ledger,
            min_rows=_MIN_ROWS,
            on_shortfall="disclose",
            trade_date=trade_date,
            fields="ts_code,amount",
        )
        if frame.empty:
            short_days.append(trade_date)

    # 2) 每个形成日：窗口内逐日读取缓存，累计 per-stock 日均。
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    formations_done = 0
    coverage: list[int] = []
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["formation_date", "ts_code", "avg_amount_12m", "n_days"])
        for formation_date in formation_dates:
            window_start = _shift_months(formation_date, -WINDOW_MONTHS)
            window_days = [d for d in trade_days if window_start < d <= formation_date]
            if not window_days:
                continue
            totals: dict[str, float] = defaultdict(float)
            counts: dict[str, int] = defaultdict(int)
            for trade_date in window_days:
                for ts_code, amount in _read_cached_amounts(cache_dir, trade_date).items():
                    totals[ts_code] += amount
                    counts[ts_code] += 1
            for ts_code in sorted(totals):
                n_days = counts[ts_code]
                writer.writerow(
                    [formation_date, ts_code, f"{totals[ts_code] / n_days:.6f}", n_days]
                )
                rows_written += 1
                coverage.append(n_days)
            formations_done += 1

    if summary_path is not None:
        # H4 结构化披露：覆盖天数分布（停牌导致的稀疏度如实可见，不静默）。
        import json

        window_len = len(
            [d for d in trade_days if _shift_months(formation_dates[-1], -WINDOW_MONTHS) < d]
        )
        summary = {
            "window_months": WINDOW_MONTHS,
            "trade_days_fetched": len(trade_days),
            "formations": formations_done,
            "rows": rows_written,
            "api_calls": ledger.calls,
            "api_rows": ledger.rows,
            "short_days_skipped": short_days,
            "short_days_note": (
                "低于行数下限的交易日被跳过不缓存、不参与均值（H4 如实披露）。"
                "2015-07 停牌潮属真实低计数（邻日 2371→2044→1489 逐日递减可验），"
                "但为与静默截断不可区分而不接纳。"
            ),
            "coverage_n_days": {
                "min": min(coverage) if coverage else 0,
                "max": max(coverage) if coverage else 0,
                "window_days_at_last_formation": window_len,
                "note": "n_days = 12 月窗口内该股有成交记录的交易日数；停牌日无记录不视为零成交。",
            },
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return len(trade_days), formations_done, rows_written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B111 F005 fix-round 正式 G2 日均成交额拉取")
    parser.add_argument(
        "--detail", type=Path, default=Path("data/research/B110/ep_panel.csv.gz")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/research/B111/low_vol_liquidity_dailyavg.csv")
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path("data/research/B111/liquidity_cache")
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/research/B111/low_vol_liquidity_dailyavg_summary.json"),
    )
    args = parser.parse_args(argv)
    days, formations, rows = fetch_daily_amounts(
        args.detail, args.out, args.cache_dir, summary_path=args.summary
    )
    print(f"交易日: {days}  形成日: {formations}  落盘行数: {rows}  → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
