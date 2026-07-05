#!/usr/bin/env python
"""B085 F001 (screen) — does residual momentum out-predict raw momentum? (rank-IC)

A **cheap, safe screen** before the expensive flagship engine A/B: same forward-return
rank-IC as B083/B084, comparing residual momentum vs raw momentum head-to-head on the
B070 adj_close panel. Touches **no** cn_attack product code (零回归 respected). If residual
momentum's IC does not beat raw's, the engine A/B is unwarranted → INCONCLUSIVE early;
if it does, the engine A/B (fresh context) is justified.

★fair: raw + residual use the **same** window/skip (residual only subtracts β·market).
★no look-ahead: signal at t uses ≤t prices; forward return is t→t+H (single-test lock).
★口径: relative comparison (residual vs raw) shares any survivorship confound, so it is
robust to it even though absolute IC carries the b070-universe bias (honest caveat).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.research.b085_residual_momentum import (
    LOOKBACK_MOM,
    SKIP,
    residual_momentum,
)

_CACHE = Path("data/research/b070/b081_prices_cache.pkl")
_FWD_H = 21  # ~1-month forward return horizon
_OUT = Path("data/research/b070/b085_residual_vs_raw_ic.json")


def _wide_adj_close(df: Any) -> Any:
    return df.pivot_table(
        index="date", columns="ticker", values="adj_close", aggfunc="last"
    ).sort_index()


def raw_momentum(prices: Any) -> Any:
    """Cumulative RAW return over the same [t-SKIP-LOOKBACK_MOM, t-SKIP] window as the
    residual signal — the only difference from residual momentum is the β·market subtraction."""

    rets = prices.pct_change()
    return rets.rolling(LOOKBACK_MOM, min_periods=LOOKBACK_MOM // 2).sum().shift(SKIP)


def forward_return(prices: Any, horizon: int = _FWD_H) -> Any:
    """t → t+horizon forward return (future prices; the target the signal predicts)."""

    return prices.shift(-horizon) / prices - 1.0


def _rank_ic(sig: Any, fwd: Any) -> float | None:
    """Spearman IC = Pearson of ranks (scipy-free, B083 precedent)."""

    import pandas as pd

    pair = pd.DataFrame({"s": sig, "f": fwd}).dropna()
    if len(pair) < 20:
        return None
    return float(pair["s"].rank().corr(pair["f"].rank()))


def compare_ic(prices: Any) -> dict[str, Any]:
    import numpy as np

    def _t_stat(vals: list[float]) -> float:
        return float(np.mean(vals) / (np.std(vals) / np.sqrt(len(vals))))

    resid = residual_momentum(prices)
    raw = raw_momentum(prices)
    fwd = forward_return(prices)
    # monthly sampling → avoid overlapping-window IC autocorrelation inflation
    month_ends = prices.resample("ME").last().index
    ic_resid, ic_raw = [], []
    for t in month_ends:
        if t not in prices.index:
            continue
        r = _rank_ic(resid.loc[t], fwd.loc[t])
        w = _rank_ic(raw.loc[t], fwd.loc[t])
        if r is not None and w is not None:
            ic_resid.append(r)
            ic_raw.append(w)
    paired_delta = [r - w for r, w in zip(ic_resid, ic_raw, strict=True)]  # per-month improvement
    return {
        "n_months": len(ic_resid),
        "residual_ic_mean": round(float(np.mean(ic_resid)), 4),
        "raw_ic_mean": round(float(np.mean(ic_raw)), 4),
        "residual_ic_std": round(float(np.std(ic_resid)), 4),
        "raw_ic_std": round(float(np.std(ic_raw)), 4),
        "delta_mean": round(float(np.mean(paired_delta)), 4),
        # ★the honest test of the RELATIVE claim: is residual > raw significant month-by-month?
        "delta_paired_t": round(_t_stat(paired_delta), 2),
        "residual_ic_t": round(_t_stat(ic_resid), 2),
        "raw_ic_t": round(_t_stat(ic_raw), 2),
    }


def main() -> int:
    import json

    import pandas as pd

    prices = _wide_adj_close(pd.read_pickle(_CACHE))  # noqa: S301 — our own trusted cache
    prices = prices[prices.index >= "2019-04-01"]  # B070 window
    result = compare_ic(prices)
    _OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
