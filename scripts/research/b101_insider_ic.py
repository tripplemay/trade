#!/usr/bin/env python
"""B101 — insider-BUYING (大股东/高管增持) signal: announcement-lagged forward-return
rank-IC (5/20/60d) + an event long backtest vs baseline. NO LOOK-AHEAD.

★ CARDINAL RISK handled here — a 增持 transaction happens on a 变动日期 (transaction
  date) but only becomes PUBLIC on the later 公告日 (announcement date). Entering on the
  transaction date = look-ahead = fake edge. The akshare feed carries BOTH dates, so we
  key everything off the ANNOUNCEMENT date.

  Cohort construction (unambiguously look-ahead-free): events are bucketed by
  ANNOUNCEMENT month M; a single cohort ENTRY = first trading day of month M+1, i.e.
  strictly AFTER every announcement in the cohort. Effective lag ranges from ~1 trading
  day (an end-of-month announcement) up to ~1 month (a start-of-month announcement) —
  conservative on purpose. Forward returns are measured STRICTLY AFTER entry.

Signal (PRIOR stated ONCE, not tuned to the backtest):
  PRIMARY = per-stock SUM of 占总股本比例 (% of total share capital the insiders bought)
  across that stock's events in the announcement month — the size / conviction of the
  buying. Cross-sectional rank per month. Prior expectation: a WEAK positive forward
  rank-IC (~+0.02..+0.05) at 20-60d — insider buying is a known mild-alpha signal, but
  disclosure lag + A-share noise can erode it, so a near-zero result is plausible.
  SECONDARY = event COUNT (number of distinct insider buys that month), reported too.

Backtests (monthly rebalance, equal weight, hold = horizon td):
  EVENT  long = ALL stocks with an insider buy in month M   vs baseline = equal-weight
         the ENTIRE covered price universe over the same months. Tests the raw event
         edge ("does following insider buying beat the market?").
  MAGNITUDE long = top-quintile buyers by the PRIMARY signal vs the same baseline.
         Tests whether buy SIZE adds beyond the binary event.
research-only / no broker / no real money / no production change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DIR = Path("data/research/b101_insider")
_EVENTS_CSV = _DIR / "insider_events.csv"
_PRICES_PKL = _DIR / "prices.pkl"
_OUT = _DIR / "ic_result.json"

_HORIZONS = (5, 20, 60)   # short-horizon post-announcement (trading days)
_TOP_Q = 0.20             # magnitude top-quintile long book
_RET_SANITY = 6.0         # drop |exit/entry| outside [1/6, 6] as a data-error guard
_MIN_XS = 20              # min stocks in a cohort to compute an IC


def load_events() -> Any:
    """Clean event feed, restricted to the price universe. One row per (code, event)."""
    import pandas as pd

    ev = pd.read_csv(_EVENTS_CSV, dtype={"code": str})
    ev["code"] = ev["code"].str.extract(r"(\d{6})")[0]
    ev["announce_date"] = pd.to_datetime(ev["announce_date"])
    ev["txn_end_date"] = pd.to_datetime(ev["txn_end_date"])
    ev["chg_pct_total"] = pd.to_numeric(ev["chg_pct_total"], errors="coerce")
    ev = ev.dropna(subset=["code", "announce_date"])
    ev["ann_month"] = ev["announce_date"].dt.to_period("M")
    return ev


def load_prices_wide() -> Any:
    import pandas as pd

    px = pd.read_pickle(_PRICES_PKL)
    wide = px.pivot_table(index="date", columns="code", values="adj_close", aggfunc="last")
    return wide.sort_index()


_MAX_ENTRY_GAP_DAYS = 15  # entry must be a real next-month td, not snapped forward years


def cohort_entry(wide_index: Any, ann_month: Any) -> Any:
    """First trading day of the month AFTER the announcement month -> strictly after
    every announcement in that cohort. Returns a Timestamp or None.

    Guard: if the first available trading day is more than _MAX_ENTRY_GAP_DAYS past the
    next-month floor, the price panel does not cover this cohort (e.g. a pre-2018
    announcement snapping onto the 2018 cache start) -> return None so stale cohorts are
    NOT scored against unrelated later prices.
    """
    import pandas as pd

    floor = (ann_month + 1).to_timestamp()  # first calendar day of next month
    after = wide_index[wide_index >= pd.Timestamp(floor)]
    if not len(after):
        return None
    entry = after[0]
    if (entry - pd.Timestamp(floor)).days > _MAX_ENTRY_GAP_DAYS:
        return None
    return entry


def forward_return(wide: Any, code: str, entry: Any, horizon: int) -> float | None:
    """entry -> entry+horizon trading days, adj_close ratio - 1. STRICTLY after entry.
    None if price missing / non-positive / fails the sanity guard."""
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


def monthly_signal(ev: Any, ann_month: Any) -> Any:
    """Aggregate a month's events to one row per stock: summed buy-% + event count."""
    sub = ev[ev["ann_month"] == ann_month]
    g = sub.groupby("code").agg(
        buy_pct=("chg_pct_total", "sum"),
        n_events=("chg_pct_total", "size"),
    ).reset_index()
    return g


def _spearman(a: Any, b: Any) -> float:
    return float(a.rank().corr(b.rank()))


def _compound(rs: list[float]) -> float:
    out = 1.0
    for r in rs:
        out *= (1.0 + r)
    return float(out - 1.0)


def run(ev: Any, wide: Any, signal_col: str, horizon: int) -> dict[str, Any]:
    """Per-announcement-month cross-section: rank-IC + event & magnitude backtests."""
    import numpy as np

    months = sorted(ev["ann_month"].unique())
    all_codes = list(wide.columns)
    ics: list[float] = []
    event_rets: list[float] = []
    mag_rets: list[float] = []
    base_rets: list[float] = []
    per_month: list[dict[str, Any]] = []

    for m in months:
        entry = cohort_entry(wide.index, m)
        if entry is None:
            continue
        sig = monthly_signal(ev, m)
        rows = []
        for _, r in sig.iterrows():
            ret = forward_return(wide, r["code"], entry, horizon)
            if ret is None:
                continue
            rows.append({"code": r["code"], "signal": float(r[signal_col]), "ret": ret})
        import pandas as pd

        df = pd.DataFrame(rows)
        # baseline = equal-weight the ENTIRE covered universe over the same cohort/hold.
        base_vals = [forward_return(wide, c, entry, horizon) for c in all_codes]
        base_vals = [x for x in base_vals if x is not None]
        base_r = float(np.mean(base_vals)) if base_vals else None
        if len(df) < _MIN_XS or base_r is None:
            per_month.append({"month": str(m), "n": int(len(df)), "ic": None,
                              "entry": str(entry.date())})
            continue
        ic = _spearman(df["signal"], df["ret"])
        event_r = float(df["ret"].mean())  # long ALL buyers
        k = max(1, int(round(len(df) * _TOP_Q)))
        mag_r = float(df.nlargest(k, "signal")["ret"].mean())  # top-quintile by size
        ics.append(ic)
        event_rets.append(event_r)
        mag_rets.append(mag_r)
        base_rets.append(base_r)
        per_month.append({
            "month": str(m), "n": int(len(df)), "ic": round(ic, 4),
            "entry": str(entry.date()),
            "event_ret": round(event_r, 4), "mag_ret": round(mag_r, 4),
            "base_ret": round(base_r, 4), "event_excess": round(event_r - base_r, 4),
        })

    ic_arr = np.array(ics, dtype=float)
    n = len(ic_arr)
    mean_ic = float(ic_arr.mean()) if n else None
    std_ic = float(ic_arr.std(ddof=1)) if n > 1 else None
    ic_ir = (mean_ic / std_ic) if (std_ic and std_ic > 0) else None
    t_stat = (ic_ir * (n ** 0.5)) if ic_ir is not None else None

    event_excess = [a - b for a, b in zip(event_rets, base_rets, strict=True)]
    mag_excess = [a - b for a, b in zip(mag_rets, base_rets, strict=True)]
    return {
        "signal_col": signal_col,
        "horizon_td": horizon,
        "n_months_scored": n,
        "mean_ic": round(mean_ic, 4) if mean_ic is not None else None,
        "std_ic": round(std_ic, 4) if std_ic is not None else None,
        "ic_ir": round(ic_ir, 4) if ic_ir is not None else None,
        "ic_t_stat": round(t_stat, 3) if t_stat is not None else None,
        "event_long_mean_ret": round(float(np.mean(event_rets)), 4) if event_rets else None,
        "mag_long_mean_ret": round(float(np.mean(mag_rets)), 4) if mag_rets else None,
        "base_mean_ret": round(float(np.mean(base_rets)), 4) if base_rets else None,
        "event_cum_ret": round(_compound(event_rets), 4) if event_rets else None,
        "mag_cum_ret": round(_compound(mag_rets), 4) if mag_rets else None,
        "base_cum_ret": round(_compound(base_rets), 4) if base_rets else None,
        "event_excess_cum": round(_compound(event_rets) - _compound(base_rets), 4)
        if event_rets else None,
        "event_excess_mean": round(float(np.mean(event_excess)), 4) if event_excess else None,
        "event_excess_hit": round(float(np.mean([e > 0 for e in event_excess])), 3)
        if event_excess else None,
        "mag_excess_mean": round(float(np.mean(mag_excess)), 4) if mag_excess else None,
        "per_month": per_month,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ev = load_events()
    wide = load_prices_wide()
    # restrict events to the price universe for the tradeable analysis.
    ev = ev[ev["code"].isin(set(wide.columns))].copy()
    result: dict[str, Any] = {
        "prior": "PRIMARY buy_pct = summed 占总股本比例 per stock/month, cross-sectional "
                 "rank; prior weak-positive IC ~+0.02..+0.05; not tuned. Cohort entry = "
                 "first trading day of month AFTER announcement month (no look-ahead).",
        "n_events_in_universe": int(len(ev)),
        "n_stocks_in_universe": int(ev["code"].nunique()),
        "runs": {},
    }
    for label, col in (("primary_buy_pct", "buy_pct"), ("secondary_n_events", "n_events")):
        for h in _HORIZONS:
            key = f"{label}__h{h}"
            r = run(ev, wide, col, h)
            result["runs"][key] = r
            logger.info(
                "%s: meanIC=%s t=%s eventCum=%s baseCum=%s excess=%s hit=%s",
                key, r["mean_ic"], r["ic_t_stat"], r["event_cum_ret"],
                r["base_cum_ret"], r["event_excess_cum"], r["event_excess_hit"])
    with open(_OUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("wrote %s", _OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
