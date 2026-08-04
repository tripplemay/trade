"""B112 F001 — A 股宇宙基本面深历史回填（quality mode 的 A/B 判据输入）。

生产 fundamentals.csv 只到 2021-08（pipeline 起点），b068 研究集只有 393 只窄宇宙；
B112 冻结窗口 2019-04→2026-07 需要 1310 只研究宇宙的全段 CAS 基本面。本脚本用
akshare `stock_financial_abstract`（深历史 指标×报告期 透视表）逐只回填。

口径（与生产 `cn_fundamentals.py` 完全一致，保证 A/B 与生产可比）：
- `report_date` = CSRC 保守披露死线（Q1→04-30 / 半年报→08-31 / Q3→10-31 / 年报→次年 04-30；
  非标准期 +90 天）——与生产同一函数（复制自 ``cn_fundamentals.cas_disclosure_date``）。
- 字段：roe / gross_margin / fcf_yield / debt_to_assets（质量 composite 的四个输入）；
  FCF 每股缺失时回退经营现金流每股（生产同款 fallback）；fcf_yield = fcf_ps / 披露日最近
  交易日收盘（本批价格集 = b081 cache + 生产延伸段）。
- 逐只缓存，中断重跑零成本；akshare 仅本脚本懒导入（research 边界，H6/H5 不适用生产）。

产物：`data/research/b112/fundamentals_full.csv.gz`（含与生产文件的并集去重规则见 runner）。
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

_UNIVERSE = Path("data/research/b070/snapshots/universe/cn_pit_universe.csv")
_PRICES_BASE = Path("data/research/b070/b081_prices_cache.pkl")
_PRICES_EXT = Path("data/research/b112/b112_prices_ext.pkl")
_CACHE_DIR = Path("data/research/b112/fundamentals_cache")
_OUT = Path("data/research/b112/fundamentals_full.csv")

_IND_ROE = "净资产收益率(ROE)"
_IND_GROSS_MARGIN = "毛利率"
_IND_DEBT_ASSET = "资产负债率"
_IND_FCF_PS = "每股企业自由现金流量"
_IND_CFO_PS = "每股经营现金流"

# 与 cn_fundamentals.py 的 _DISCLOSURE_DEADLINE 逐字一致（生产口径）。
_DISCLOSURE_DEADLINE: dict[tuple[int, int], tuple[int, int, int]] = {
    (3, 31): (4, 30, 0),
    (6, 30): (8, 31, 0),
    (9, 30): (10, 31, 0),
    (12, 31): (4, 30, 1),
}


def cas_disclosure_date(period_end: date) -> date:
    deadline = _DISCLOSURE_DEADLINE.get((period_end.month, period_end.day))
    if deadline is None:
        return period_end + timedelta(days=90)
    month, day, year_offset = deadline
    return date(period_end.year + year_offset, month, day)


def _fiscal_quarter(period_end: date) -> str:
    return f"{period_end.year}Q{(period_end.month - 1) // 3 + 1}"


def backfill(out_path: Path, cache_dir: Path) -> tuple[int, int]:
    import akshare as ak  # noqa: PLC0415 — 联网依赖，仅回填时导入

    tickers = sorted(pd.read_csv(_UNIVERSE)["ticker"].unique())
    base = pd.read_pickle(_PRICES_BASE)
    ext = pd.read_pickle(_PRICES_EXT)
    prices = pd.concat([base, ext], ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"])
    price_by_ticker = {
        ticker: frame.set_index("date").sort_index()
        for ticker, frame in prices.groupby("ticker")
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    failed: list[str] = []
    for ticker in tickers:
        cache_path = cache_dir / f"{ticker}.csv"
        if cache_path.exists():
            done += 1
            continue
        code = ticker.split(".")[0]
        try:
            frame = ak.stock_financial_abstract(symbol=code)
        except Exception as exc:  # noqa: BLE001 — 留痕后继续，单只失败不中止全批
            failed.append(f"{ticker}: {exc!r}")
            time.sleep(2.0)
            continue
        if frame is None or frame.empty:
            failed.append(f"{ticker}: empty abstract")
            continue
        records = frame.to_dict("records")
        by_indicator: dict[str, dict[str, object]] = {}
        for record in records:
            indicator = str(record.get("指标", ""))
            if indicator and indicator not in by_indicator:
                by_indicator[indicator] = record

        def metric(
            indicator: str, col: str, *, _table: dict[str, dict[str, object]]
        ) -> float | None:
            row = _table.get(indicator)
            if row is None:
                return None
            try:
                value = float(row.get(col))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            return value if value == value else None  # NaN check

        rows: list[dict[str, object]] = []
        for col in frame.columns:
            text = str(col)
            if not (len(text) == 8 and text.isdigit()):
                continue
            period_end = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            disclosure = cas_disclosure_date(period_end)
            fcf_ps = metric(_IND_FCF_PS, text, _table=by_indicator)
            if fcf_ps is None:
                fcf_ps = metric(_IND_CFO_PS, text, _table=by_indicator)
            close = _close_near_frame(price_by_ticker.get(ticker), disclosure)
            fcf_yield = (fcf_ps / close) if (fcf_ps is not None and close) else None
            rows.append(
                {
                    "report_date": disclosure.isoformat(),
                    "ticker": ticker,
                    "fiscal_quarter": _fiscal_quarter(period_end),
                    "fiscal_quarter_end": period_end.isoformat(),
                    "roe": metric(_IND_ROE, text, _table=by_indicator),
                    "gross_margin": metric(_IND_GROSS_MARGIN, text, _table=by_indicator),
                    "fcf_yield": fcf_yield,
                    "debt_to_assets": metric(_IND_DEBT_ASSET, text, _table=by_indicator),
                }
            )
        pd.DataFrame(rows).to_csv(cache_path, index=False)
        done += 1
        if done % 50 == 0:
            print(f"  …{done}/{len(tickers)}", flush=True)
        time.sleep(0.4)  # 温和限速

    # 合并缓存 + 生产新鲜段（2026 年报告期以生产 pipeline 为准）。
    frames = [pd.read_csv(path) for path in sorted(cache_dir.glob("*.csv"))]
    merged = pd.concat(frames, ignore_index=True)
    # ★单位归一（2026-08-04 对拍实证）：akshare CAS 行是**百分数**（roe=2.80），
    # 生产 fundamentals 是**小数**（0.0280，`_frac` 口径）——回填行必须先 /100
    # 才能与生产同口径合并；fcf_yield 已是 fcf_ps/close 的小数，不再除。
    for column in ("roe", "gross_margin", "debt_to_assets"):
        merged[column] = pd.to_numeric(merged[column], errors="coerce") / 100.0
    prod = pd.read_pickle("data/research/b112/b112_fundamentals.pkl")
    prod["fiscal_quarter_end"] = pd.to_datetime(prod["fiscal_quarter_end"]).dt.date.astype(str)
    merged = pd.concat([merged, prod[merged.columns]], ignore_index=True)
    # 生产行优先（同 ticker+period 重复时保留生产 pipeline 的口径）。
    merged["report_date"] = pd.to_datetime(merged["report_date"]).dt.date.astype(str)
    merged = merged.drop_duplicates(
        subset=["ticker", "fiscal_quarter_end"], keep="last"
    ).sort_values(["ticker", "fiscal_quarter_end"])
    # ★schema 补全（2026-08-04 冒烟发现）：quality_score 的 _ensure_columns 要求
    # pe/pb/ev_ebitda/earnings_yield 四列存在。CAS 回填不算这四个估值比率
    #（质量 composite 只用 roe/gross_margin/fcf_yield/debt_to_assets 四输入，
    # 估值列在 CN 复合分中不被读取）——补 NaN 列以满足模式契约，报告中如实披露。
    for column in ("pe", "pb", "ev_ebitda", "earnings_yield"):
        if column not in merged.columns:
            merged[column] = float("nan")
    merged = merged[
        [
            "report_date", "ticker", "fiscal_quarter", "fiscal_quarter_end",
            "roe", "gross_margin", "fcf_yield", "debt_to_assets",
            "pe", "pb", "ev_ebitda", "earnings_yield",
        ]
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    if failed:
        (out_path.parent / "fundamentals_backfill_failures.txt").write_text(
            "\n".join(failed) + "\n", encoding="utf-8"
        )
    return len(merged), len(failed)


def _close_near_frame(frame: pd.DataFrame | None, on: date) -> float | None:
    if frame is None:
        return None
    upto = frame[frame.index <= pd.Timestamp(on)]
    if upto.empty:
        return None
    value = float(upto["close"].iloc[-1])
    return value if value > 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 基本面深历史回填")
    parser.add_argument("--out", type=Path, default=_OUT)
    parser.add_argument("--cache-dir", type=Path, default=_CACHE_DIR)
    args = parser.parse_args(argv)
    rows, failures = backfill(args.out, args.cache_dir)
    print(f"落盘行数: {rows}  失败: {failures}  → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
