#!/usr/bin/env python
"""B083 F001 part2 — bulk-fetch 业绩预告 events for the PEAD first-look IC (F002).

first-look = 研究批（spec §0#1 不建生产模式），so the events are a **one-time bulk
historical fetch** (not a daily data_refresh timer): loop akshare ``stock_yjyg_em``
over report periods 2019Q1..2024Q4 → normalise → PIT-dedup (same stock+period → keep
the LATEST 公告日期) → ``data/research/b083_pead/events.csv``. F002 joins these events
(event date = 公告日期, PIT) with the B070 PIT prices for forward-return rank-IC.

Resumable: per-period CSVs cached so a killed run continues. akshare is external
(~1-2s/period), so this is background-friendly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_OUT_DIR = Path("data/research/b083_pead")
_PER_PERIOD_DIR = _OUT_DIR / "by_period"
_EVENTS_CSV = _OUT_DIR / "events.csv"

# Report-period ends: Q1/H1/Q3/annual × 2019..2024. akshare stock_yjyg_em(date=...).
_YEARS = range(2019, 2025)
_QUARTER_ENDS = ("0331", "0630", "0930", "1231")

# Normalised columns (PIT-clean): the surprise inputs + the event date.
_COLS = {
    "股票代码": "ticker",
    "股票简称": "name",
    "公告日期": "announce_date",  # ★ PIT event date (publication, not period end)
    "预测数值": "forecast_value",  # predicted net profit (or midpoint)
    "上年同期值": "prior_year_value",  # baseline for the surprise
    "业绩变动幅度": "change_pct",  # akshare-provided %Δ (cross-check)
    "预告类型": "forecast_type",  # 略增/预增/扭亏/首亏/预减/...
}


def _fetch_period(period: str) -> Any:
    """One report period → normalised DataFrame (cached per-period)."""

    import pandas as pd

    cache = _PER_PERIOD_DIR / f"{period}.csv"
    if cache.is_file():
        return pd.read_csv(cache, dtype={"ticker": str})

    import akshare as ak

    df = ak.stock_yjyg_em(date=period)
    if df is None or not len(df):
        out = pd.DataFrame(columns=list(_COLS.values()) + ["report_period"])
    else:
        keep = {k: v for k, v in _COLS.items() if k in df.columns}
        out = df[list(keep)].rename(columns=keep).copy()
        out["ticker"] = out["ticker"].astype(str).str.zfill(6)
        out["report_period"] = period
    _PER_PERIOD_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False)
    return out


def pit_dedup(events: Any) -> Any:
    """PIT dedup: same stock + report period → keep the LATEST 公告日期 (the final
    pre-report forecast). Rows without a parseable announce_date are dropped (can't be
    PIT-entered). Pure/testable — no akshare."""

    import pandas as pd

    events = events.copy()
    events["announce_date"] = pd.to_datetime(events["announce_date"], errors="coerce")
    events = events.dropna(subset=["announce_date"])
    return (
        events.sort_values("announce_date")
        .drop_duplicates(subset=["ticker", "report_period"], keep="last")
        .sort_values(["announce_date", "ticker"])
        .reset_index(drop=True)
    )


def main() -> int:
    import pandas as pd

    frames = []
    for year in _YEARS:
        for q in _QUARTER_ENDS:
            period = f"{year}{q}"
            try:
                df = _fetch_period(period)
                frames.append(df)
                print(f"{period}: {len(df)} events")
            except Exception as exc:  # noqa: BLE001 — best-effort per period
                print(f"{period}: ERROR {type(exc).__name__} {str(exc)[:80]}")

    if not frames:
        print("no events fetched")
        return 1
    events = pit_dedup(pd.concat(frames, ignore_index=True))
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    events.to_csv(_EVENTS_CSV, index=False)
    print(f"wrote {_EVENTS_CSV}: {len(events)} PIT events "
          f"({events['announce_date'].min().date()}..{events['announce_date'].max().date()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
