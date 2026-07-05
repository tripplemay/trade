#!/usr/bin/env python
"""B083 F002 — PEAD forward-return rank-IC first-look (同 B077 模式).

盈余惊喜 = (预测数值 − 上年同期值)/|上年同期值|（先验口径，禁扫参）。事件日 = 公告日（PIT）。
★前视 rigor（命门）：entry = 公告日**之后**的第一个交易日（strictly >），forward-only 收益，
绝无 look-ahead。rank-IC N1/N5/N10/N20 = spearman(surprise, fwd_ret)。涨跌停分层：剔除 entry 日
一字触板（open vs 前收 ±band）的**不可执行**事件，报可执行 IC vs 纸面 IC。

宇宙 = events ∩ B070 去偏 PIT prices（~1152 名 / 8878 事件, 23% 覆盖；cn_attack 宇宙偏差显式标注）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_EVENTS = Path("data/research/b083_pead/events.csv")
_HORIZONS = (1, 5, 10, 20)
_OUT = Path("data/research/b083_pead/ic_result.json")


def compute_surprise(events: Any) -> Any:
    """盈余惊喜 = (预测−上年)/|上年|; 丢 |上年|==0 与 inf/nan。"""

    import numpy as np

    e = events.copy()
    e = e[e["prior_year_value"].abs() > 0].copy()
    e["surprise"] = (e["forecast_value"] - e["prior_year_value"]) / e["prior_year_value"].abs()
    e = e.replace([np.inf, -np.inf], np.nan).dropna(subset=["surprise"])
    return e


def _six(s: Any) -> Any:
    return s.astype(str).str.extract(r"(\d{6})")[0]


def forward_returns(close_panel: Any, open_panel: Any, prev_close_panel: Any,
                    events: Any, horizons: tuple[int, ...]) -> Any:
    """Per event: entry = 第一个交易日 strictly > 公告日（前视 rigor）; forward-only rets;
    涨跌停 = entry 日 open vs 前收 ±band（300/688=20% else 10%）一字触板标记。"""

    import numpy as np
    import pandas as pd

    dates = close_panel.index
    rows = []
    for _, ev in events.iterrows():
        t = ev["ticker"]
        if t not in close_panel.columns:
            continue
        ad = pd.Timestamp(ev["announce_date"])
        after = dates[dates > ad]  # ★ strictly after announcement — no look-ahead
        if len(after) == 0:
            continue
        entry = after[0]
        ei = dates.get_loc(entry)
        col = close_panel[t]
        p0 = col.iloc[ei]
        if pd.isna(p0) or p0 <= 0:
            continue
        # 涨跌停触板判定 at entry (open vs prev close)
        band = 0.20 if str(t).startswith(("300", "688")) else 0.10
        o = open_panel[t].iloc[ei] if t in open_panel.columns else np.nan
        pc = prev_close_panel[t].iloc[ei] if t in prev_close_panel.columns else np.nan
        limit_locked = False
        if pd.notna(o) and pd.notna(pc) and o > 0 and pc > 0:
            r = o / pc - 1.0
            limit_locked = (r >= band - 1e-9) or (r <= -band + 1e-9)
        rec: dict[str, Any] = {"ticker": t, "surprise": float(ev["surprise"]),
                               "entry": entry, "announce": ad, "limit_locked": bool(limit_locked)}
        for n in horizons:
            j = ei + n
            pn = col.iloc[j] if j < len(dates) else np.nan
            rec[f"ret_{n}"] = float(pn / p0 - 1.0) if (pd.notna(pn) and pn > 0) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def rank_ic(df: Any, horizons: tuple[int, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for n in horizons:
        sub = df.dropna(subset=["surprise", f"ret_{n}"])
        # spearman = Pearson of ranks (scipy-free).
        ic = (
            float(sub["surprise"].rank().corr(sub[f"ret_{n}"].rank()))
            if len(sub) > 30 else None
        )
        out[f"N{n}"] = {"ic": round(ic, 4) if ic is not None else None, "n": int(len(sub))}
    return out


def main() -> int:
    import json

    import pandas as pd

    os.environ["WORKBENCH_DATA_ROOT"] = str(Path("data/research/b070").resolve())
    from trade.data.us_quality_universe import load_prices

    events = compute_surprise(pd.read_csv(_EVENTS, dtype={"ticker": str}))
    events["ticker"] = events["ticker"].str.zfill(6)

    prices = load_prices()
    prices = prices.assign(t6=_six(prices["ticker"])).dropna(subset=["t6"])

    def _wide(col: str) -> Any:
        return prices.pivot_table(
            index="date", columns="t6", values=col, aggfunc="last"
        ).sort_index()

    close_p = _wide("adj_close")
    open_p = _wide("open")
    prev_close_p = close_p.shift(1)

    fr = forward_returns(close_p, open_p, prev_close_p, events, _HORIZONS)
    all_ic = rank_ic(fr, _HORIZONS)
    exec_ic = rank_ic(fr[~fr["limit_locked"]], _HORIZONS)  # 剔除 entry 触板 = 可执行
    locked_frac = round(float(fr["limit_locked"].mean()), 3) if len(fr) else None

    result = {"events_priced": int(len(fr)), "entry_limit_locked_frac": locked_frac,
              "ic_all": all_ic, "ic_executable": exec_ic}
    _OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
