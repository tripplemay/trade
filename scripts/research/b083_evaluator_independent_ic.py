#!/usr/bin/env python
"""B083 F003 独立验收 — 从零重实现 PEAD rank-IC（不 import generator 脚本）。

独立点：
  - 直接读 events.csv + prices_daily.csv（不走 trade.data.load_prices）
  - surprise=(forecast-prior)/|prior|，丢 |prior|==0 / inf / nan（独立实现）
  - entry = 第一个交易日 strictly > announce_date（np.searchsorted 独立实现）
  - forward-only 收益 adj_close[entry+n]/adj_close[entry]-1
  - rank-IC = scipy.stats.spearmanr（与 generator 的 Pearson-of-ranks 不同实现）
  - 涨跌停：entry open vs 前收 ±band（300/688=20% else 10%）
输出与 generator ic_result.json 对照。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

EVENTS = Path("data/research/b083_pead/events.csv")


def _avg_rank(a: np.ndarray) -> np.ndarray:
    """Average ranks with tie handling (independent of pandas .rank())."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    sa = a[order]
    i = 0
    n = len(a)
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx = _avg_rank(x)
    ry = _avg_rank(y)
    return float(np.corrcoef(rx, ry)[0, 1])
PRICES = Path("data/research/b070/snapshots/prices/unified/prices_daily.csv")
HORIZONS = (1, 5, 10, 20)


def six(s: pd.Series) -> pd.Series:
    return s.astype(str).str.extract(r"(\d{6})")[0]


def main() -> int:
    # --- events + independent surprise ---
    ev = pd.read_csv(EVENTS, dtype={"ticker": str})
    ev["ticker"] = ev["ticker"].str.zfill(6)
    ev["announce_date"] = pd.to_datetime(ev["announce_date"])
    prior = ev["prior_year_value"].astype(float)
    fc = ev["forecast_value"].astype(float)
    mask = prior.abs() > 0
    ev = ev[mask].copy()
    ev["surprise"] = (fc[mask] - prior[mask]) / prior[mask].abs()
    ev = ev.replace([np.inf, -np.inf], np.nan).dropna(subset=["surprise"])
    print(f"events after surprise: {len(ev)}")

    # --- prices wide panels (independent load) ---
    px = pd.read_csv(PRICES, dtype={"ticker": str},
                     usecols=["date", "ticker", "open", "close", "adj_close"])
    px["date"] = pd.to_datetime(px["date"])
    px["t6"] = six(px["ticker"])
    px = px.dropna(subset=["t6"])
    def _wide(col: str) -> pd.DataFrame:
        return px.pivot_table(index="date", columns="t6", values=col, aggfunc="last").sort_index()

    close_p = _wide("adj_close")
    open_p = _wide("open")
    prev_close_p = close_p.shift(1)
    dates = close_p.index.values  # datetime64 sorted
    print(f"price panel: {close_p.shape[0]} dates x {close_p.shape[1]} tickers")

    rows = []
    date_arr = pd.DatetimeIndex(close_p.index)
    for _, r in ev.iterrows():
        t = r["ticker"]
        if t not in close_p.columns:
            continue
        ad = r["announce_date"]
        # first trading day strictly AFTER announce (independent: searchsorted 'right')
        pos = np.searchsorted(dates, np.datetime64(ad), side="right")
        if pos >= len(dates):
            continue
        ei = int(pos)
        p0 = close_p[t].iloc[ei]
        if pd.isna(p0) or p0 <= 0:
            continue
        band = 0.20 if str(t).startswith(("300", "688")) else 0.10
        o = open_p[t].iloc[ei] if t in open_p.columns else np.nan
        pc = prev_close_p[t].iloc[ei] if t in prev_close_p.columns else np.nan
        locked = False
        if pd.notna(o) and pd.notna(pc) and o > 0 and pc > 0:
            ret0 = o / pc - 1.0
            locked = (ret0 >= band - 1e-9) or (ret0 <= -band + 1e-9)
        rec = {"ticker": t, "surprise": float(r["surprise"]),
               "entry": date_arr[ei], "announce": ad, "locked": locked}
        for n in HORIZONS:
            j = ei + n
            pn = close_p[t].iloc[j] if j < len(dates) else np.nan
            rec[f"ret_{n}"] = float(pn / p0 - 1.0) if (pd.notna(pn) and pn > 0) else np.nan
        rows.append(rec)

    fr = pd.DataFrame(rows)
    print(f"events priced: {len(fr)}")
    # sanity: entry strictly after announce for ALL
    bad = (fr["entry"] <= fr["announce"]).sum()
    print(f"LOOK-AHEAD CHECK: events with entry<=announce = {bad} (must be 0)")

    def ic_block(d: pd.DataFrame) -> dict:
        out = {}
        for n in HORIZONS:
            sub = d.dropna(subset=["surprise", f"ret_{n}"])
            if len(sub) > 30:
                ic = spearman(sub["surprise"].to_numpy(), sub[f"ret_{n}"].to_numpy())
                out[f"N{n}"] = {"ic": round(ic, 4), "n": int(len(sub))}
            else:
                out[f"N{n}"] = {"ic": None, "n": int(len(sub))}
        return out

    result = {
        "events_priced": int(len(fr)),
        "entry_limit_locked_frac": round(float(fr["locked"].mean()), 3),
        "ic_all": ic_block(fr),
        "ic_executable": ic_block(fr[~fr["locked"]]),
        "lookahead_violations": int(bad),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    Path("/tmp/eval_b083_ic_independent_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
