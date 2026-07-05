#!/usr/bin/env python
"""B084 F002 — A股 ETF 时序趋势 first-look（时序动量 vs 买入持有）.

★先验口径（禁扫参）：月末 12-月绝对动量（Moskowitz-Ooi-Pedersen 时序动量）——
signal = price_t / price_{t-12m} - 1 > 0 → 持有该 ETF（等权持有腿），否则退现金。月度调仓。
★无前视：signal 用 ≤ 月 t 的价格 → 交易月 t+1 收益。
★命门：**2022 / 2024-02 震荡切换期分窗口损耗**（趋势策略最大陷阱）显式报。

对照买入持有（等权全 ETF 持有）。first-look = 证据一测（非可配资）：趋势夏普显著 > 买入持有 +
震荡损耗可控 → GO；否则 INCONCLUSIVE 归档。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_PRICES = Path("data/research/b084_etf/prices.csv")
_LOOKBACK_M = 12  # ★先验：12-月时序动量（禁扫参）
_IN_SAMPLE = 0.7
_OUT = Path("data/research/b084_etf/trend_result.json")


def _monthly_panel(prices: Any) -> Any:
    """Wide month-end close panel (date × ticker), forward-filled within listing."""

    import pandas as pd

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    wide = prices.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    ).sort_index()
    return wide.resample("ME").last()


def _metrics(monthly_ret: Any) -> dict[str, Any]:
    """CAGR / Sharpe / MaxDD from a monthly return series (scipy-free)."""

    import numpy as np

    r = monthly_ret.dropna()
    if len(r) < 6:
        return {"cagr": None, "sharpe": None, "maxdd": None, "n": int(len(r))}
    equity = (1.0 + r).cumprod()
    years = len(r) / 12.0
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    sharpe = float(r.mean() / r.std() * np.sqrt(12)) if r.std() > 0 else None
    maxdd = float((equity / equity.cummax() - 1.0).min())
    return {"cagr": round(cagr, 4), "sharpe": round(sharpe, 3) if sharpe else None,
            "maxdd": round(maxdd, 4), "n": int(len(r))}


def trend_vs_hold(panel: Any) -> Any:
    """Per month: 12m absolute momentum signal (≤ t) → equal-weight held legs' t+1 return.
    Returns a DataFrame indexed by month with strategy + buy-hold + held-count columns."""

    import numpy as np
    import pandas as pd

    fwd = panel.pct_change().shift(-1)  # month t → t+1 forward return (no look-ahead)
    mom = panel / panel.shift(_LOOKBACK_M) - 1.0  # 12m momentum known at t
    rows = []
    for t in panel.index:
        signal = mom.loc[t]  # ≤ t
        held = signal[signal > 0].index  # positive-momentum ETFs (else cash)
        f = fwd.loc[t]
        vals = [f[c] for c in held if pd.notna(f[c])]
        strat = float(np.mean(vals)) if vals else 0.0  # cash / all-unpriced held = 0
        priced = f.dropna()
        hold = float(priced.mean()) if len(priced) else np.nan  # equal-weight buy-hold
        rows.append({"month": t, "strat_ret": strat, "hold_ret": hold, "n_held": int(len(held))})
    out = pd.DataFrame(rows).set_index("month")
    return out.iloc[_LOOKBACK_M:-1]  # drop warmup (no momentum) + last (no forward)


def main() -> int:
    import json

    import pandas as pd

    os.environ["WORKBENCH_DATA_ROOT"] = str(Path("data/research/b070").resolve())
    panel = _monthly_panel(pd.read_csv(_PRICES, dtype={"ticker": str}))
    tv = trend_vs_hold(panel)

    n = len(tv)
    split = int(n * _IN_SAMPLE)
    result = {
        "months": n,
        "trend_full": _metrics(tv["strat_ret"]),
        "hold_full": _metrics(tv["hold_ret"]),
        "trend_oos": _metrics(tv["strat_ret"].iloc[split:]),
        "hold_oos": _metrics(tv["hold_ret"].iloc[split:]),
        # ★命门: 震荡切换期分窗口损耗（趋势 vs 买入持有 累计收益）
        "whipsaw_2022": {
            "trend": round(float((1 + tv.loc["2022", "strat_ret"]).prod() - 1), 4),
            "hold": round(float((1 + tv.loc["2022", "hold_ret"]).prod() - 1), 4),
        },
        "whipsaw_2024H1": {
            "trend": round(float((1 + tv.loc["2024-01":"2024-06", "strat_ret"]).prod() - 1), 4),
            "hold": round(float((1 + tv.loc["2024-01":"2024-06", "hold_ret"]).prod() - 1), 4),
        },
        "avg_n_held": round(float(tv["n_held"].mean()), 2),
    }
    _OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
