"""B082 F002 — 红利低波 defensive-sleeve backtest runner (three-tier 利差 rule).

Reads the frozen snapshot (``data/research/b082/``; ``--refetch`` regenerates it via
``scripts/research/b082_fetch_snapshot.py``) and runs, with the SPEC-先验 三档利差 rule
(禁止扫参 — thresholds are constants in parameters.py):

PRIMARY 口径 (H20269 total-return index, 2005→今, no cost, fractional, T+1 index-close):
  three-tier strategy  vs  buy-and-hold baseline  — full-sample + WF 70/30 OOS + CPCV-lite.

IMPLEMENTABLE 口径 (512890 ETF sina bars 2019→今, cost=2.5bp佣金+5bp滑点, NO 印花税, 100股/手,
  管理费 0.5%/yr drag, exec at next OPEN):  strategy vs buy-hold at BOTH 10万 / 100万 capital.
  ⚠ sina ETF bars are UNADJUSTED (no dividend) → the ETF layer measures IMPLEMENTABILITY /
  cost / turnover, NOT total return; the TR index is the return 口径 (探针 §3/§4).

DRAWDOWN 对照 (defensive-sleeve验收 focus): 2022 full year + 2024-01~02 踩踏窗口 —
  strategy(index) vs buy-hold(index) vs HS300.

Output: ``data/research/b082/backtest_results.json`` (all numbers, reproducible) + a
human summary to stdout. The report ``docs/test-reports/B082-F002-backtest.md`` lifts
these numbers verbatim.

Usage: .venv/bin/python scripts/research/b082_dividend_lowvol_backtest.py [--refetch]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
from trade.backtest.cn_dividend_lowvol.engine import (
    BacktestResult,
    cpcv_lite_fold_cagrs,
    simulate_single_asset,
    walk_forward_oos_metrics,
    window_max_drawdown,
)
from trade.strategies.cn_dividend_lowvol.parameters import CnDividendLowvolParameters
from trade.strategies.cn_dividend_lowvol.signal import (
    compute_spread,
    month_end_target_weights,
    reconstruct_dividend_yield,
)

SNAPSHOT_DIR = Path("data/research/b082")
RESULTS_JSON = SNAPSHOT_DIR / "backtest_results.json"

# ETF 口径 cost model: NO stamp duty (ETF exempt), commission 2.5bp + slippage 5bp.
ETF_COST = CnCostModel(stamp_duty_bps=0.0, commission_bps=2.5, slippage_bps=5.0)
ETF_ANNUAL_FEE = 0.005  # ~0.5%/yr management+custody drag (探针 §4)
ETF_LOT = 100  # 100 份/手

# Drawdown 对照 windows (defensive-sleeve验收).
WINDOW_2022 = (date(2022, 1, 1), date(2022, 12, 31))
WINDOW_2024_FEB = (date(2024, 1, 1), date(2024, 2, 29))
# 2025 跑输区间 (AI 牛, 红利低波 lagged — 诚实边界, reported separately).
WINDOW_2025 = (date(2025, 1, 1), date(2025, 12, 31))


def _load(name: str, value_col: str) -> pd.Series:
    path = SNAPSHOT_DIR / f"{name}.csv"
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame.set_index("date")[value_col].astype(float).sort_index()


def _metrics_dict(result: BacktestResult) -> dict[str, Any]:
    return {
        **asdict(result.metrics),
        "total_turnover": result.total_turnover,
        "n_rebalances": result.n_rebalances,
    }


def _window_dd(equity: pd.Series) -> dict[str, float]:
    return {
        "dd_2022": window_max_drawdown(equity, *WINDOW_2022),
        "dd_2024_feb": window_max_drawdown(equity, *WINDOW_2024_FEB),
        "dd_2025": window_max_drawdown(equity, *WINDOW_2025),
    }


def _window_return(series: pd.Series, start: date, end: date) -> float:
    sub = series[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
    if len(sub) < 2 or float(sub.iloc[0]) <= 0:
        return float("nan")
    return float(sub.iloc[-1]) / float(sub.iloc[0]) - 1.0


def run() -> dict[str, Any]:
    params = CnDividendLowvolParameters()

    tr = _load("index_h20269", "close")
    pr = _load("index_h30269", "close")
    y10 = _load("cn_10y_yield", "yield")
    etf_close = _load("etf_512890", "close")
    etf_open = _load("etf_512890", "open")
    hs300 = _load("hs300", "close")

    # --- signal (shared) --------------------------------------------------- #
    divy = reconstruct_dividend_yield(tr, pr, params.dividend_yield_lookback_days)
    spread = compute_spread(divy, y10)
    monthly_targets = month_end_target_weights(spread, params)
    hold_targets = pd.Series(1.0, index=monthly_targets.index)  # buy-and-hold baseline

    is_half = (monthly_targets < params.full_weight) & (monthly_targets > params.low_weight)
    tier_counts = {
        "full>=2.5": int((monthly_targets >= params.full_weight).sum()),
        "half": int(is_half.sum()),
        "low<1.5": int((monthly_targets <= params.low_weight).sum()),
    }

    results: dict[str, Any] = {
        "parameter_hash": params.parameter_hash(),
        "thresholds": {
            "saturated_spread_pct": params.saturated_spread_pct,
            "half_spread_pct": params.half_spread_pct,
            "weights": [params.low_weight, params.half_weight, params.full_weight],
            "lookback_days": params.dividend_yield_lookback_days,
        },
        "signal": {
            "divy_first": divy.index[0].date().isoformat(),
            "divy_last": divy.index[-1].date().isoformat(),
            "divy_min_pct": round(float(divy.min()), 3),
            "divy_max_pct": round(float(divy.max()), 3),
            "divy_mean_pct": round(float(divy.mean()), 3),
            "spread_latest_pct": round(float(spread.iloc[-1]), 3),
            "target_latest": float(monthly_targets.iloc[-1]),
            "n_month_ends": int(len(monthly_targets)),
            "tier_counts": tier_counts,
        },
    }

    # --- PRIMARY 口径 (index TR, no cost, fractional) ----------------------- #
    prim_strat = simulate_single_asset(tr, monthly_targets, cost_model=None)
    prim_hold = simulate_single_asset(tr, hold_targets, cost_model=None)
    results["primary_index_tr"] = {
        "window": f"{tr.index[0].date()}..{tr.index[-1].date()}",
        "strategy": {
            **_metrics_dict(prim_strat),
            "wf_oos": asdict(walk_forward_oos_metrics(prim_strat.equity)),
            "cpcv_lite_k4": [
                round(c, 4)
                for c in cpcv_lite_fold_cagrs(prim_strat.equity, monthly_targets, 4)
            ],
            **_window_dd(prim_strat.equity),
        },
        "buy_hold": {
            **_metrics_dict(prim_hold),
            "wf_oos": asdict(walk_forward_oos_metrics(prim_hold.equity)),
            **_window_dd(prim_hold.equity),
        },
    }

    # --- IMPLEMENTABLE 口径 (ETF, cost + lot + fee, dual capital) ----------- #
    # Restrict targets to the ETF window (2019→今).
    etf_start = etf_close.index[0]
    etf_targets = monthly_targets[monthly_targets.index >= etf_start]
    etf_hold = pd.Series(1.0, index=etf_targets.index)
    impl: dict[str, Any] = {
        "window": f"{etf_close.index[0].date()}..{etf_close.index[-1].date()}",
        "note": "sina ETF bars UNADJUSTED (no dividend) — implementability/cost层, NOT return 口径",
        "capitals": {},
    }
    for capital in (100_000.0, 1_000_000.0):
        strat = simulate_single_asset(
            etf_close, etf_targets, initial_capital=capital, cost_model=ETF_COST,
            lot_size=ETF_LOT, annual_fee=ETF_ANNUAL_FEE,
            min_rebalance_weight_delta=params.min_rebalance_weight_delta, exec_prices=etf_open,
        )
        hold = simulate_single_asset(
            etf_close, etf_hold, initial_capital=capital, cost_model=ETF_COST,
            lot_size=ETF_LOT, annual_fee=ETF_ANNUAL_FEE,
            min_rebalance_weight_delta=params.min_rebalance_weight_delta, exec_prices=etf_open,
        )
        impl["capitals"][f"{int(capital)}"] = {
            "strategy": {**_metrics_dict(strat), **_window_dd(strat.equity)},
            "buy_hold": {**_metrics_dict(hold), **_window_dd(hold.equity)},
        }
    results["implementable_etf"] = impl

    # --- DRAWDOWN 对照 (strategy index vs hold index vs HS300) --------------- #
    results["drawdown_comparison"] = {
        "2022": {
            "strategy_index": window_max_drawdown(prim_strat.equity, *WINDOW_2022),
            "buy_hold_index": window_max_drawdown(prim_hold.equity, *WINDOW_2022),
            "hs300": window_max_drawdown(hs300, *WINDOW_2022),
            "strategy_return": _window_return(prim_strat.equity, *WINDOW_2022),
            "buy_hold_return": _window_return(prim_hold.equity, *WINDOW_2022),
            "hs300_return": _window_return(hs300, *WINDOW_2022),
        },
        "2024_jan_feb": {
            "strategy_index": window_max_drawdown(prim_strat.equity, *WINDOW_2024_FEB),
            "buy_hold_index": window_max_drawdown(prim_hold.equity, *WINDOW_2024_FEB),
            "hs300": window_max_drawdown(hs300, *WINDOW_2024_FEB),
            "strategy_return": _window_return(prim_strat.equity, *WINDOW_2024_FEB),
            "buy_hold_return": _window_return(prim_hold.equity, *WINDOW_2024_FEB),
            "hs300_return": _window_return(hs300, *WINDOW_2024_FEB),
        },
        "2025_lag": {  # 诚实边界: 红利低波 2025 AI 牛跑输
            "strategy_return": _window_return(prim_strat.equity, *WINDOW_2025),
            "buy_hold_return": _window_return(prim_hold.equity, *WINDOW_2025),
            "hs300_return": _window_return(hs300, *WINDOW_2025),
            "strategy_dd": window_max_drawdown(prim_strat.equity, *WINDOW_2025),
            "buy_hold_dd": window_max_drawdown(prim_hold.equity, *WINDOW_2025),
        },
    }
    return results


def _print_summary(r: dict[str, Any]) -> None:
    s = r["primary_index_tr"]
    print("\n=== PRIMARY 口径 (H20269 TR index, no cost) ===", file=sys.stderr)
    print(f"  window {s['window']}", file=sys.stderr)
    for name in ("strategy", "buy_hold"):
        m = s[name]
        print(
            f"  {name:9s}: CAGR {m['cagr']*100:6.2f}% Sharpe {m['sharpe']:.3f} "
            f"MaxDD {m['max_drawdown']*100:6.1f}% | OOS CAGR {m['wf_oos']['cagr']*100:6.2f}% "
            f"| DD2022 {m['dd_2022']*100:5.1f}% DD24Feb {m['dd_2024_feb']*100:5.1f}%",
            file=sys.stderr,
        )
    print(f"  CPCV-lite K4 fold CAGRs: {s['strategy']['cpcv_lite_k4']}", file=sys.stderr)
    print("\n=== IMPLEMENTABLE 口径 (512890 ETF, UNADJUSTED) ===", file=sys.stderr)
    for cap, block in r["implementable_etf"]["capitals"].items():
        for name in ("strategy", "buy_hold"):
            m = block[name]
            print(
                f"  @{int(cap):>9d} {name:9s}: CAGR {m['cagr']*100:6.2f}% "
                f"MaxDD {m['max_drawdown']*100:6.1f}% "
                f"turnover {m['total_turnover']:.2f} rebs {m['n_rebalances']}",
                file=sys.stderr,
            )
    print("\n=== DRAWDOWN 对照 ===", file=sys.stderr)
    for win, block in r["drawdown_comparison"].items():
        rounded = {k: round(v, 4) if isinstance(v, float) else v for k, v in block.items()}
        print(f"  {win}: {json.dumps(rounded, ensure_ascii=False)}", file=sys.stderr)
    print(f"\n  tier counts (month-ends): {r['signal']['tier_counts']}", file=sys.stderr)
    sig = r["signal"]
    print(
        f"  latest spread {sig['spread_latest_pct']}% → target {sig['target_latest']}",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refetch", action="store_true",
                        help="Regenerate the frozen snapshot before running.")
    args = parser.parse_args()

    if args.refetch or not (SNAPSHOT_DIR / "index_h20269.csv").exists():
        print("refetching snapshot ...", file=sys.stderr)
        subprocess.run([sys.executable, "scripts/research/b082_fetch_snapshot.py"], check=True)

    results = run()
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    RESULTS_JSON.write_text(payload, encoding="utf-8")
    _print_summary(results)
    print(f"\nwrote {RESULTS_JSON}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
