"""B111 F005 — G2 硬门的流动性数据拉取（★本批次唯一的 API 成本）。

为每个形成日拉 `daily.amount`（成交额，千元）作为流动性度量，落盘成
`formation_date, ts_code, amount` 的 CSV，供 `low_vol_cli.py --liquidity` 跑 G2
（剔除最低 30% 流动性后几何超额是否仍 ≥ +1.0pp）。

★口径与防线（H5）：
- 走 `ep_panel_cli._fetch_cached` 的三道防线（行数下限 + 长退避 + 整页边界重取），
  缓存到 `cache_dir`——**重跑零成本**。
- trade_cal 先解析交易日，把形成日映射到 ≤ 它的最后交易日，避免对非交易月末长退避。
- token 只从 `.env.local` 读（`vintage_probe.load_token`，H6）。
- ★成交额取形成日**当日**（无前视：形成日已知）。这是单日代理，非滚动均值——
  是一个已知的粗口径限制，F007 若需更稳健可扩到滚动窗（成本更高）。
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
from pathlib import Path
from typing import Any

from scripts.research.ashare_pit.ep_panel_cli import Ledger, _fetch_cached
from scripts.research.ashare_pit.vintage_probe import load_token

_MIN_ROWS = 1500  # 交易日全 A 约 5000 只；<1500 视为静默空/短表（三道防线之一）


def _formation_dates(detail_path: Path) -> list[str]:
    with gzip.open(detail_path, "rt", encoding="utf-8", newline="") as handle:
        return sorted({row["formation_date"] for row in csv.DictReader(handle)})


def _trading_days(pro: Any, start: str, end: str) -> list[str]:
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
    return sorted(str(d) for d in cal["cal_date"].tolist())


def _last_trade_day_on_or_before(trade_days: list[str], target: str) -> str | None:
    idx = bisect.bisect_right(trade_days, target)
    return trade_days[idx - 1] if idx > 0 else None


def fetch_liquidity(
    detail_path: Path, out_path: Path, cache_dir: Path
) -> tuple[int, int]:
    """拉取并落盘流动性 CSV。返回 (形成日数, 落盘行数)。"""

    import tushare as ts  # type: ignore[import-untyped]  # noqa: PLC0415 — 联网依赖，仅拉取时导入

    pro = ts.pro_api(load_token())
    formation_dates = _formation_dates(detail_path)
    trade_days = _trading_days(pro, f"{formation_dates[0][:4]}0101", f"{formation_dates[-1]}")
    ledger = Ledger()
    cache_dir.mkdir(parents=True, exist_ok=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    dates_done = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["formation_date", "ts_code", "amount"])
        for formation_date in formation_dates:
            trade_date = _last_trade_day_on_or_before(trade_days, formation_date)
            if trade_date is None:
                continue
            frame = _fetch_cached(
                pro,
                "daily",
                cache_dir=cache_dir,
                name=f"daily_amount_{trade_date}",
                ledger=ledger,
                min_rows=_MIN_ROWS,
                trade_date=trade_date,
                fields="ts_code,amount",
            )
            for record in frame.itertuples(index=False):
                amount = getattr(record, "amount", None)
                if amount is None:
                    continue
                writer.writerow([formation_date, record.ts_code, amount])
                rows_written += 1
            dates_done += 1
    return dates_done, rows_written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B111 F005 G2 流动性拉取（唯一 API 成本）")
    parser.add_argument(
        "--detail", type=Path, default=Path("data/research/B110/ep_panel.csv.gz")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/research/B111/low_vol_liquidity.csv")
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path("data/research/B111/liquidity_cache")
    )
    args = parser.parse_args(argv)
    dates_done, rows = fetch_liquidity(args.detail, args.out, args.cache_dir)
    print(f"形成日: {dates_done}  落盘行数: {rows}  → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
