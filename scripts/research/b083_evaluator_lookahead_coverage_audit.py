#!/usr/bin/env python
"""B083 F003 — 手工前视抽验 + 覆盖率诚实性核查 + PIT 时点核查。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

EVENTS = Path("data/research/b083_pead/events.csv")
PRICES = Path("data/research/b070/snapshots/prices/unified/prices_daily.csv")
UNIV = Path("data/research/b070/snapshots/universe/cn_pit_universe.csv")


def six(s):
    return s.astype(str).str.extract(r"(\d{6})")[0]


ev = pd.read_csv(EVENTS, dtype={"ticker": str})
ev["ticker"] = ev["ticker"].str.zfill(6)
ev["announce_date"] = pd.to_datetime(ev["announce_date"])

px = pd.read_csv(PRICES, dtype={"ticker": str}, usecols=["date", "ticker", "adj_close"])
px["date"] = pd.to_datetime(px["date"])
px["t6"] = six(px["ticker"])
close_p = px.pivot_table(
    index="date", columns="t6", values="adj_close", aggfunc="last"
).sort_index()
dates = pd.DatetimeIndex(close_p.index)

print("=" * 70)
print("【1】手工前视抽验 — 抽 3 个事件, 核对 announce vs entry(次日 open)")
print("=" * 70)
# 抽 3 个：最早、中间、含跨报告期末的
in_univ = ev[ev["ticker"].isin(close_p.columns)].reset_index(drop=True)
sample_idx = [0, len(in_univ) // 2, len(in_univ) - 5]
for i in sample_idx:
    r = in_univ.iloc[i]
    t, ad = r["ticker"], r["announce_date"]
    period = str(r["report_period"])
    pos = np.searchsorted(dates.values, np.datetime64(ad), side="right")
    entry = dates[pos] if pos < len(dates) else None
    # 期末日
    period_end = pd.to_datetime(period, format="%Y%m%d")
    print(f"\n  {r['name']}({t}) 报告期={period}(期末 {period_end.date()})")
    print(f"    公告日(announce, 真发布日) = {ad.date()}")
    print(f"    进场(entry, 第一个交易日 > 公告日) = {entry.date() if entry is not None else None}")
    print(f"    entry 严格晚于公告? {entry > ad}   entry 晚于报告期末? {entry > period_end}")
    print(f"    forecast={r['forecast_value']} prior={r['prior_year_value']} "
          f"type={r['forecast_type']}")

print("\n" + "=" * 70)
print("【2】覆盖率诚实性核查")
print("=" * 70)
total_ev = len(ev)
uniq_tickers_all = ev["ticker"].nunique()
ev_in_panel = ev[ev["ticker"].isin(close_p.columns)]
uniq_in_panel = ev_in_panel["ticker"].nunique()
print(f"  events.csv 总事件 = {total_ev}, 唯一标的 = {uniq_tickers_all}")
print(f"  价格面板(B070) 标的数 = {close_p.shape[1]}")
if UNIV.is_file():
    u = pd.read_csv(UNIV, dtype=str)
    print(f"  universe 文件 {UNIV.name}: {len(u)} 行, 列={list(u.columns)[:6]}")
    for c in u.columns:
        if u[c].astype(str).str.contains(r"\d{6}").any():
            n_u = u[c].nunique()
            print(f"    列 '{c}' 唯一值 = {n_u}")
            break
print(f"  事件∩B070面板(ticker 命中) = {len(ev_in_panel)} 事件 ({uniq_in_panel} 唯一标的)")
print(f"  覆盖率(事件级) = {len(ev_in_panel)/total_ev*100:.1f}%")
print(f"  覆盖率(标的级) = {uniq_in_panel/uniq_tickers_all*100:.1f}%")

print("\n" + "=" * 70)
print("【3】PIT 时点核查 — 公告日是否为真发布日(散布), 非报告期末")
print("=" * 70)
for period in ["20200930", "20211231", "20230930"]:
    sub = ev[ev["report_period"].astype(str) == period]
    if len(sub):
        pe = pd.to_datetime(period, format="%Y%m%d").date()
        amin, amax = sub["announce_date"].min().date(), sub["announce_date"].max().date()
        n_before = (sub["announce_date"].dt.date <= pe).sum()
        print(f"  报告期 {period}(期末 {pe}): {len(sub)} 事件, 公告日 {amin}..{amax}, "
              f"其中 {n_before} 个公告日 ≤ 期末(预告特性=期末前预披)")
