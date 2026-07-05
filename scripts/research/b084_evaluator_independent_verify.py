#!/usr/bin/env python
"""B084 F003 — INDEPENDENT evaluator re-implementation of the ETF trend first-look.

Written from scratch by the independent evaluator; does NOT import any generator b084
script (deliberately different code path). Cross-checks the F002 report numbers
(docs/test-reports/B084-etf-trend-ic.md) and — the spec命门 — recomputes the
2022 / 2024 震荡切换期 whipsaw at both annual and finer sub-windows to test the
report's "未见震荡损耗" claim.

Run: .venv/bin/python scripts/research/b084_evaluator_independent_verify.py
(reads data/research/b084_etf/prices.csv — reproduce via scripts/research/b084_etf_fetch.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PRICES = Path("data/research/b084_etf/prices.csv")
_LOOKBACK = 12  # 先验 12-月绝对动量 (禁扫参)
_IN_SAMPLE = 0.7


def _month_end_panel(df: Any) -> Any:
    """Month-end close panel via groupby (independent of the generator's pivot_table)."""

    import pandas as pd

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["m"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    last = df.sort_values("date").groupby(["m", "ticker"], as_index=False)["close"].last()
    panel = last.pivot(index="m", columns="ticker", values="close").sort_index()
    panel.index.name = "date"
    return panel


def _metrics(r: Any) -> dict[str, Any]:
    import numpy as np

    r = r.dropna()
    if len(r) < 6:
        return {"cagr": None, "sharpe": None, "maxdd": None, "n": int(len(r))}
    eq = (1.0 + r).cumprod()
    yrs = len(r) / 12.0
    cagr = float(eq.iloc[-1] ** (1.0 / yrs) - 1.0)
    sd = float(r.std(ddof=1))
    sharpe = float(r.mean() / sd * np.sqrt(12)) if sd > 0 else None
    maxdd = float((eq / eq.cummax() - 1.0).min())
    return {"cagr": round(cagr, 4), "sharpe": round(sharpe, 3) if sharpe else None,
            "maxdd": round(maxdd, 4), "n": int(len(r))}


def _build(panel: Any) -> Any:
    """Forward return t->t+1 (explicit shift) × 12m past momentum signal (known at t)."""

    import numpy as np
    import pandas as pd

    fwd = panel.shift(-1) / panel - 1.0
    mom = panel / panel.shift(_LOOKBACK) - 1.0
    rows = []
    for t in panel.index:
        sig = mom.loc[t]
        held = [c for c in panel.columns if pd.notna(sig[c]) and sig[c] > 0]
        f = fwd.loc[t]
        held_priced = [f[c] for c in held if pd.notna(f[c])]
        strat = float(np.mean(held_priced)) if held_priced else 0.0
        priced = f.dropna()
        hold = float(priced.mean()) if len(priced) else float("nan")
        rows.append({"date": t, "strat": strat, "hold": hold, "n_held": len(held)})
    out = pd.DataFrame(rows).set_index("date")
    return out.iloc[_LOOKBACK:-1]  # drop warmup + final (no forward)


def _cum(series: Any) -> float:
    return round(float((1.0 + series).prod() - 1.0), 4)


def main() -> int:
    import pandas as pd

    tv = _build(_month_end_panel(pd.read_csv(_PRICES, dtype={"ticker": str})))
    n = len(tv)
    split = int(n * _IN_SAMPLE)
    print(f"months={n}  OOS_n={n - split}  avg_n_held={round(float(tv['n_held'].mean()), 2)}")
    print("FULL  trend:", _metrics(tv["strat"]))
    print("FULL  hold :", _metrics(tv["hold"]))
    print("OOS   trend:", _metrics(tv["strat"].iloc[split:]))
    print("OOS   hold :", _metrics(tv["hold"].iloc[split:]))
    windows = [
        ("2022 full", "2022-01", "2022-12"),
        ("2024H1", "2024-01", "2024-06"),
        ("2024-01..02 (tight rangebound)", "2024-01", "2024-02"),
        ("2022-01..04 (early-22 whipsaw)", "2022-01", "2022-04"),
    ]
    for label, lo, hi in windows:
        seg = tv.loc[lo:hi]
        print(f"WHIP  {label}: trend={_cum(seg['strat'])} hold={_cum(seg['hold'])} "
              f"months={len(seg)} avg_n_held={round(float(seg['n_held'].mean()), 2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
