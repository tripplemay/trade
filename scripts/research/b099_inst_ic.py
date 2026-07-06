#!/usr/bin/env python
"""B099 — institutional-BUILDING (机构建仓) signal: disclosure-lagged forward-return
rank-IC + a long-only top-signal backtest vs baseline. NO LOOK-AHEAD.

★ CARDINAL RISK handled here — A-share quarterly reports disclose with a LAG:
    Q1 (ends Mar 31) → by Apr 30      Q2 (ends Jun 30) → by Aug 31
    Q3 (ends Sep 30) → by Oct 31      Q4/annual (ends Dec 31) → by Apr 30 next year
  The 机构持股 for quarter Q is NOT public at Q-end. We enter CONSERVATIVELY on the
  first trading day on/after the FIRST DAY OF THE MONTH AFTER the disclosure deadline
  (Q1→May 1, Q2→Sep 1, Q3→Nov 1, Q4→May 1 next yr) — a full extra month past the
  legal deadline. Forward returns are measured STRICTLY AFTER that entry. Using the
  Q-end date as entry would be look-ahead and invalidate everything.

Signal (PRIOR stated ONCE, not tuned to the backtest):
  PRIMARY = 持股比例增幅 (institutional holding-% increase that quarter), cross-sectional
  rank per quarter. This is the direct "building" magnitude. Prior expectation: a WEAK
  positive next-quarter rank-IC (~+0.03) — institutions may carry mild informational
  edge, but a 1-4 month disclosure lag means the edge is largely STALE by entry, so a
  near-zero result is entirely plausible. SECONDARY = 机构数变化 (count of institutions
  joining), reported alongside for cross-checking.

Method: per-quarter Spearman rank-IC(signal, fwd_ret); mean IC + IC_IR + t across the
~20 quarterly cross-sections. Backtest: each quarter long the top-quintile by signal
(equal weight), hold ~1 quarter (63 td) to the next disclosure entry, vs baseline =
equal-weight the ENTIRE covered universe that quarter. research-only.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DIR = Path("data/research/b099_inst")
_PANEL_CSV = _DIR / "inst_panel.csv"
_PRICES_PKL = _DIR / "prices.pkl"
_OUT = _DIR / "ic_result.json"

_HORIZONS = (21, 63)          # ~1 month, ~1 quarter (trading days)
_PRIMARY = "hold_pct_chg"     # 持股比例增幅
_SECONDARY = "n_inst_chg"     # 机构数变化
_TOP_Q = 0.20                 # top-quintile long book
_RET_SANITY = 6.0             # drop |exit/entry| outside [1/6, 6] as a data-error guard
_MIN_XS = 30                  # min stocks in a cross-section to compute an IC


def parse_quarter(sym: str) -> tuple[int, int]:
    """'20241' -> (2024, 1); '20203' -> (2020, 3)."""
    s = str(sym)
    return int(s[:4]), int(s[4:])


def disclosure_deadline(year: int, q: int) -> date:
    """Legal latest disclosure date for quarter (year, q)."""
    if q == 1:
        return date(year, 4, 30)
    if q == 2:
        return date(year, 8, 31)
    if q == 3:
        return date(year, 10, 31)
    return date(year + 1, 4, 30)  # Q4 / annual


def entry_floor(year: int, q: int) -> date:
    """CONSERVATIVE entry floor = first day of the month AFTER the disclosure deadline.
    Strictly later than the deadline, so any on-time report is already public."""
    if q == 1:
        return date(year, 5, 1)
    if q == 2:
        return date(year, 9, 1)
    if q == 3:
        return date(year, 11, 1)
    return date(year + 1, 5, 1)  # Q4 disclosed by Apr 30 next year -> May 1 next year


def first_trading_day_on_or_after(dates: Any, floor: date) -> Any:
    """First index timestamp >= floor, or None if the calendar ends before floor."""
    import pandas as pd

    ts = pd.Timestamp(floor)
    after = dates[dates >= ts]
    return after[0] if len(after) else None


def _spearman(a: Any, b: Any) -> float:
    return float(a.rank().corr(b.rank()))


def load_panel() -> Any:
    import pandas as pd

    df = pd.read_csv(_PANEL_CSV, dtype={"code": str, "quarter": str})
    df["code"] = df["code"].str.extract(r"(\d{6})")[0]
    return df.dropna(subset=["code"])


def load_prices_wide() -> Any:
    import pandas as pd

    px = pd.read_pickle(_PRICES_PKL)
    wide = px.pivot_table(index="date", columns="code", values="adj_close", aggfunc="last")
    return wide.sort_index()


def forward_return(wide: Any, code: str, entry: Any, horizon: int) -> float | None:
    """entry -> entry+horizon trading days, adj_close ratio - 1. STRICTLY after entry.
    None if either price missing/non-positive or return fails the sanity guard."""
    import pandas as pd

    if code not in wide.columns:
        return None
    col = wide[code]
    idx = wide.index
    if entry not in idx:
        return None
    ei = idx.get_loc(entry)
    j = ei + horizon
    if j >= len(idx):
        return None
    p0 = col.iloc[ei]
    p1 = col.iloc[j]
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0 or p1 <= 0:
        return None
    ratio = p1 / p0
    if ratio > _RET_SANITY or ratio < 1.0 / _RET_SANITY:
        return None
    return float(ratio - 1.0)


def build_quarter_frame(panel: Any, wide: Any, sym: str, signal_col: str,
                        horizon: int) -> Any:
    """One cross-section: signal + disclosure-lagged forward return per covered stock.

    entry = first trading day on/after entry_floor(year,q) -> NO LOOK-AHEAD.
    """
    import pandas as pd

    year, q = parse_quarter(sym)
    entry = first_trading_day_on_or_after(wide.index, entry_floor(year, q))
    sub = panel[panel["quarter"] == sym].copy()
    sub = sub.dropna(subset=[signal_col])
    rows = []
    if entry is None:
        return pd.DataFrame(rows), entry
    for _, r in sub.iterrows():
        ret = forward_return(wide, r["code"], entry, horizon)
        if ret is None:
            continue
        rows.append({"code": r["code"], "signal": float(r[signal_col]),
                     "ret": ret, "entry": entry})
    return pd.DataFrame(rows), entry


def quarterly_ic_and_backtest(panel: Any, wide: Any, signal_col: str,
                              horizon: int) -> dict[str, Any]:
    import numpy as np

    syms = sorted(panel["quarter"].unique(), key=parse_quarter)
    ics: list[float] = []
    per_q: list[dict[str, Any]] = []
    long_rets: list[float] = []
    base_rets: list[float] = []
    for sym in syms:
        year, q = parse_quarter(sym)
        df, entry = build_quarter_frame(panel, wide, sym, signal_col, horizon)
        if len(df) < _MIN_XS:
            per_q.append({"quarter": sym, "n": int(len(df)), "ic": None,
                          "entry": str(entry.date()) if entry is not None else None})
            continue
        ic = _spearman(df["signal"], df["ret"])
        # long-only top-quintile by signal vs baseline (equal-weight whole universe).
        k = max(1, int(round(len(df) * _TOP_Q)))
        top = df.nlargest(k, "signal")
        long_r = float(top["ret"].mean())
        base_r = float(df["ret"].mean())
        ics.append(ic)
        long_rets.append(long_r)
        base_rets.append(base_r)
        # deadline check exposed for audit / tests.
        dl = disclosure_deadline(year, q)
        per_q.append({
            "quarter": sym, "n": int(len(df)), "ic": round(ic, 4),
            "entry": str(entry.date()), "disclosure_deadline": str(dl),
            "entry_after_deadline": bool(entry.date() > dl),
            "long_ret": round(long_r, 4), "base_ret": round(base_r, 4),
            "excess": round(long_r - base_r, 4),
        })

    ic_arr = np.array(ics, dtype=float)
    n = len(ic_arr)
    mean_ic = float(ic_arr.mean()) if n else None
    std_ic = float(ic_arr.std(ddof=1)) if n > 1 else None
    ic_ir = (mean_ic / std_ic) if (std_ic and std_ic > 0) else None
    t_stat = (ic_ir * (n ** 0.5)) if ic_ir is not None else None

    def _compound(rs: list[float]) -> float:
        out = 1.0
        for r in rs:
            out *= (1.0 + r)
        return float(out - 1.0)

    long_cum = _compound(long_rets)
    base_cum = _compound(base_rets)
    excess = [a - b for a, b in zip(long_rets, base_rets, strict=True)]
    hit = float(np.mean([e > 0 for e in excess])) if excess else None

    return {
        "signal_col": signal_col,
        "horizon_td": horizon,
        "n_quarters_scored": n,
        "mean_ic": round(mean_ic, 4) if mean_ic is not None else None,
        "std_ic": round(std_ic, 4) if std_ic is not None else None,
        "ic_ir": round(ic_ir, 4) if ic_ir is not None else None,
        "ic_t_stat": round(t_stat, 3) if t_stat is not None else None,
        "long_mean_q_ret": round(float(np.mean(long_rets)), 4) if long_rets else None,
        "base_mean_q_ret": round(float(np.mean(base_rets)), 4) if base_rets else None,
        "long_cum_ret": round(long_cum, 4),
        "base_cum_ret": round(base_cum, 4),
        "excess_cum": round(long_cum - base_cum, 4),
        "excess_mean_q": round(float(np.mean(excess)), 4) if excess else None,
        "excess_hit_rate": round(hit, 3) if hit is not None else None,
        "per_quarter": per_q,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    panel = load_panel()
    wide = load_prices_wide()
    result: dict[str, Any] = {
        "prior": "PRIMARY 持股比例增幅 cross-sectional rank; prior weak-positive IC ~+0.03; "
                 "not tuned to backtest. Disclosure-lagged conservative entry (deadline+1mo).",
        "runs": {},
    }
    for label, col in (("primary_hold_pct_chg", _PRIMARY),
                       ("secondary_n_inst_chg", _SECONDARY)):
        for h in _HORIZONS:
            key = f"{label}__h{h}"
            result["runs"][key] = quarterly_ic_and_backtest(panel, wide, col, h)
            r = result["runs"][key]
            logger.info("%s: meanIC=%s t=%s longCum=%s baseCum=%s excessCum=%s hit=%s",
                        key, r["mean_ic"], r["ic_t_stat"], r["long_cum_ret"],
                        r["base_cum_ret"], r["excess_cum"], r["excess_hit_rate"])
    with open(_OUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("wrote %s", _OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
