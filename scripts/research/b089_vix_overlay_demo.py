#!/usr/bin/env python
"""B089 F001 — VIX tail-overlay comparison: pure SPY vs SPY + X% VIXY.

Fetches SPY + VIXY (akshare stock_us_daily / Sina US, dodges the Eastmoney rate-limit),
builds the monthly-rebalanced overlay, and reports BOTH sides objectively: tail-loss
reduction (2020 + 2022 stress-window max-drawdown) and the negative-carry cost (full-period
CAGR drag). The hedge is not free — the report shows the drag alongside the protection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trade.analysis.vix_overlay import cagr, max_drawdown, static_overlay_returns

_CACHE = Path("data/research/b089_vix")
_WEIGHTS = (0.05, 0.10)  # 先验 (禁扫参)
_STRESS = {"2020_covid": ("2020-02-19", "2020-03-23"), "2022_bear": ("2022-01-03", "2022-10-14")}


def _load_prices() -> Any:
    import pandas as pd

    cache = _CACHE / "prices.pkl"
    if cache.is_file():
        return pd.read_pickle(cache)  # noqa: S301 — our own trusted cache
    import akshare as ak

    frames = {}
    for sym in ("SPY", "VIXY"):
        df = ak.stock_us_daily(symbol=sym)
        frames[sym] = pd.Series(df["close"].to_numpy(), index=pd.to_datetime(df["date"]), name=sym)
    prices = pd.concat(frames, axis=1, sort=True).dropna()
    _CACHE.mkdir(parents=True, exist_ok=True)
    prices.to_pickle(cache)
    return prices


def _stress_mdd(returns: Any, start: str, end: str) -> Any:
    window = returns.loc[start:end]
    return round(max_drawdown(window), 4) if len(window) else None


def run() -> dict[str, Any]:
    prices = _load_prices()
    spy_ret = prices["SPY"].pct_change().dropna()
    vixy_ret = prices["VIXY"].pct_change().reindex(spy_ret.index).fillna(0.0)

    variants: dict[str, Any] = {"pure_SPY": spy_ret}
    for w in _WEIGHTS:
        variants[f"overlay_{w:.0%}"] = static_overlay_returns(spy_ret, vixy_ret, w)

    rows = []
    for name, ret in variants.items():
        rows.append(
            {
                "variant": name,
                "full_cagr": round(cagr(ret), 4),
                "full_maxdd": round(max_drawdown(ret), 4),
                **{f"mdd_{k}": _stress_mdd(ret, s, e) for k, (s, e) in _STRESS.items()},
            }
        )
    return {
        "n_days": int(len(spy_ret)),
        "window": f"{spy_ret.index[0].date()}..{spy_ret.index[-1].date()}",
        "variants": rows,
    }


def main() -> int:
    import json

    print(json.dumps(run(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
