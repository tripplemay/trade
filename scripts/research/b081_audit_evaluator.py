#!/usr/bin/env python
"""B081 F005 evaluator audit — decisive experiments for the four Planner疑点.

1. Capital-granularity: only_lot_rounding at 100k / 1M / 10M starting capital.
   If numbers recover to ~old at 1M+ → the -8.6% is a capacity-floor artifact, not
   a strategy truth. If turnover still explodes at 10M → band/rounding interaction.
2. Affordability probe: on sample rebalance days, how many top-N names cost > their
   target notional in ONE 100-share lot, at 100k vs 1M vs 10M.
3. Event counting (faithful OLD-path replay, validated bit-level against old_all_off):
   count counterfactual "bites" of suspension / delist / price_limit on the REAL old
   held book. bites==0 → NO-OP legitimate; bites>0 while only_X is bit-identical → BUG.

Persists incrementally to data/research/b070/b081_audit_evaluator.json.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

_B070_ROOT = Path("data/research/b070")
_PIT = _B070_ROOT / "snapshots" / "universe" / "cn_pit_universe.csv"
_START = date(2019, 4, 1)
_IN_SAMPLE_FRACTION = 0.7
_PRICES_CACHE = _B070_ROOT / "b081_prices_cache.pkl"
_OUT = _B070_ROOT / "b081_audit_evaluator.json"

os.environ["WORKBENCH_DATA_ROOT"] = str(_B070_ROOT.resolve())


def _persist(state: dict[str, Any]) -> None:
    _OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load() -> tuple[Any, Any]:
    import pandas as pd

    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.data.us_quality_universe import load_prices

    if _PRICES_CACHE.is_file():
        prices = pd.read_pickle(_PRICES_CACHE)  # noqa: S301 trusted cache
    else:
        prices = load_prices()
        prices.to_pickle(_PRICES_CACHE)
    hist = load_cn_universe_history(universe_path=_PIT)
    return prices, hist


def _params():
    from trade.strategies.cn_attack_momentum_quality.parameters import (
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, weighting_scheme=WEIGHTING_SCHEME_EQUAL
    )


def _config(capital: float, kwargs: dict[str, Any]):
    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import CnAttackBacktestConfig

    cfg_kwargs = {k: v for k, v in kwargs.items() if k != "stamp_bps"}
    return CnAttackBacktestConfig(
        starting_capital=capital,
        cost_model=CnCostModel(
            stamp_duty_bps=kwargs["stamp_bps"], commission_bps=2.5, slippage_bps=5.0
        ),
        **cfg_kwargs,
    )


def _metrics(result) -> dict[str, Any]:
    import pandas as pd

    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
        max_drawdown,
        sharpe_ratio,
    )

    curve = result.equity_curve
    dates = curve["date"].tolist()
    idx = max(1, min(len(dates) - 2, int(len(dates) * _IN_SAMPLE_FRACTION)))
    split = pd.Timestamp(dates[idx])
    oos = curve[curve["date"] >= split].reset_index(drop=True)
    oos_rets = oos.set_index("date")["equity"].pct_change().dropna()
    return {
        "full_cagr": round(result.metrics.annualized_return, 4),
        "full_sharpe": round(result.metrics.sharpe_ratio, 3),
        "full_maxdd": round(result.metrics.max_drawdown, 4),
        "ending": round(result.ending_value, 0),
        "turnover": round(result.total_turnover, 2),
        "cost": round(result.total_cost, 0),
        "oos_cagr": round(annualized_return(oos), 4),
        "oos_sharpe": round(sharpe_ratio(oos_rets), 3),
        "oos_maxdd": round(max_drawdown(oos), 4),
        "rebs": result.rebalance_count,
    }


_OFF = dict(
    lot_rounding=False, partial_rebalance=False, suspension_halt=False,
    delist_liquidation=False, price_limit_gating=False, stamp_bps=10.0,
)


def experiment_capital(prices, hist, state) -> None:
    from trade.backtest.cn_attack_momentum_quality.engine import run_cn_attack_backtest

    params = _params()
    runs = [
        ("off@100k", 100_000.0, dict(_OFF)),
        ("lot@100k", 100_000.0, {**_OFF, "lot_rounding": True}),
        ("lot@1M", 1_000_000.0, {**_OFF, "lot_rounding": True}),
        ("lot@10M", 10_000_000.0, {**_OFF, "lot_rounding": True}),
        # cadence isolation for疑点3: full re-target with a near-zero band → rebalance
        # ~daily WITHOUT partial execution. Isolates whether partial's gain is cadence.
        ("fullband0.001@100k", 100_000.0, {**_OFF, "no_trade_band": 0.001}),
    ]
    state.setdefault("capital", {})
    for label, cap, kw in runs:
        if label in state["capital"]:
            continue
        result = run_cn_attack_backtest(
            params, _config(cap, kw), _START, None, prices=prices, universe_history=hist
        )
        state["capital"][label] = _metrics(result)
        _persist(state)
        print(f"[capital] {label}: {state['capital'][label]}", flush=True)


def experiment_affordability(prices, hist, state) -> None:
    """On sample rebalance days generate the signal and count top-N names whose ONE
    100-share lot costs more than their target notional (capital * weight)."""
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.engine import _wide
    from trade.data.cn_attack_universe import resolve_pit_members
    from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal

    params = _params()
    wide_open = _wide(prices, "open")
    trading_dates = [ts.date() for ts in wide_open.index]
    window = [d for d in trading_dates if d >= _START]
    # sample ~ every 6 months
    sample_days = window[::120][:14]
    caps = [100_000.0, 1_000_000.0, 10_000_000.0]
    rows = []
    for day in sample_days:
        members = resolve_pit_members(hist, day)
        if not members:
            continue
        signal = generate_cn_attack_signal(
            params, day, prices=prices, universe_members=members
        )
        weights = signal.weights_dict()
        if not weights:
            continue
        open_row = wide_open.loc[pd.Timestamp(day)]
        n = len(weights)
        prices_per_lot = {}
        for t in weights:
            px = open_row.get(t)
            if px is None or pd.isna(px) or float(px) <= 0:
                continue
            prices_per_lot[t] = float(px) * 100.0
        row: dict[str, Any] = {"date": str(day), "n_names": n}
        for cap in caps:
            unaffordable = sum(
                1 for t, w in weights.items()
                if t in prices_per_lot and prices_per_lot[t] > cap * w
            )
            row[f"unafford@{int(cap)}"] = unaffordable
        # median one-lot cost to show scale
        lot_costs = sorted(prices_per_lot.values())
        row["median_lot_cost"] = round(lot_costs[len(lot_costs) // 2], 0) if lot_costs else None
        row["max_lot_cost"] = round(max(lot_costs), 0) if lot_costs else None
        rows.append(row)
        print(f"[afford] {row}", flush=True)
    state["affordability"] = rows
    _persist(state)


def experiment_events(prices, hist, state) -> None:
    """Faithful OLD-path replay (all switches off) that ALSO computes counterfactual
    suspension / delist / price_limit bites on the REAL old held book. Validated bit
    level against old_all_off (13.1% / 243406 / 194 / 639)."""
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.engine import (
        _current_weights,
        _delist_confirmations,
        _execute_open,
        _forced_exits,
        _limit_hit_names,
        _mark_to_market,
        _Pending,
        _real_bar_mask,
        _wide,
        _would_be_turnover,
    )
    from trade.data.cn_attack_universe import resolve_pit_members
    from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal

    params = _params()
    config = _config(100_000.0, dict(_OFF))  # old path, all switches off

    wide_close = _wide(prices, "adj_close")
    wide_open = _wide(prices, "open")
    trading_dates = [ts.date() for ts in wide_close.index]
    window = [d for d in trading_dates if d >= _START]

    # Counterfactual signals (as if the switches were ON) — used for bite counting only.
    real_bar = _real_bar_mask(prices)
    delist_conf = _delist_confirmations(prices, trading_dates, config.delist_confirm_days)

    shares: dict[str, float] = {}
    cash = config.starting_capital
    entry_price: dict[str, float] = {}
    peak_price: dict[str, float] = {}
    pending = None
    prev_close_row = None

    total_turnover = 0.0
    total_cost = 0.0
    rebalance_count = 0
    equity = cash

    susp_bites = 0            # held-or-targeted no-bar names on pending days
    susp_bite_days = 0
    delist_bites = 0         # held names hitting a confirm date
    delist_bite_days = 0
    pricelimit_bites = 0     # held-or-targeted limit-locked names on pending days
    pricelimit_bite_days = 0
    susp_examples: list[str] = []
    delist_examples: list[str] = []

    for index, day in enumerate(window):
        ts = pd.Timestamp(day)
        open_row = wide_open.loc[ts]
        close_row = wide_close.loc[ts]

        if pending is not None:
            # --- counterfactual bite counting on the REAL (old) state before execution ---
            held_now = {t for t, q in shares.items() if q > 0}
            targ = set(pending.target) if pending.kind == "rebalance" else set()
            relevant = held_now | targ
            row_rb = real_bar.loc[ts]
            nobar = {str(t) for t in row_rb.index if not bool(row_rb[t])}
            susp_hit = relevant & nobar
            if susp_hit:
                susp_bites += len(susp_hit)
                susp_bite_days += 1
                if len(susp_examples) < 12:
                    susp_examples.append(f"{day}:{sorted(susp_hit)[:5]}")
            if prev_close_row is not None:
                locked = _limit_hit_names(open_row, prev_close_row)
                pl_hit = relevant & locked
                if pl_hit:
                    pricelimit_bites += len(pl_hit)
                    pricelimit_bite_days += 1
            # --- faithful OLD execution (switches off) ---
            shares, cash, ex_to, ex_cost = _execute_open(
                shares, cash, open_row, pending, config.cost_model, entry_price,
                peak_price, False, False, config.per_name_rebalance_threshold,
            )
            total_turnover += ex_to
            total_cost += ex_cost
            pending = None

        # delist bite (held names on confirm date) — counterfactual
        dtoday = delist_conf.get(day)
        if dtoday:
            held_now = {t for t, q in shares.items() if q > 0}
            dhit = held_now & dtoday
            if dhit:
                delist_bites += len(dhit)
                delist_bite_days += 1
                if len(delist_examples) < 12:
                    delist_examples.append(f"{day}:{sorted(dhit)[:5]}")

        for ticker in list(peak_price):
            close = float(close_row.get(ticker, 0.0) or 0.0)
            if close > 0:
                peak_price[ticker] = max(peak_price[ticker], close)
        equity = cash + _mark_to_market(shares, close_row)

        if index < len(window) - 1:
            members = resolve_pit_members(hist, day)
            if members:
                signal = generate_cn_attack_signal(
                    params, day, prices=prices, universe_members=members
                )
                forced_exits = _forced_exits(config, shares, close_row, entry_price, peak_price)
                target = {
                    t: w for t, w in signal.weights_dict().items() if t not in forced_exits
                }
                current_w = _current_weights(shares, close_row, equity)
                should = _would_be_turnover(current_w, target) > config.no_trade_band
                if should:
                    pending = _Pending(kind="rebalance", target=target)
                    rebalance_count += 1
                elif forced_exits:
                    pending = _Pending(kind="exit", exits=forced_exits)
        prev_close_row = close_row

    validation = {
        "ending": round(equity, 0),
        "turnover": round(total_turnover, 2),
        "rebs": rebalance_count,
        "matches_old": abs(equity - 243406.0) < 5.0 and rebalance_count == 639,
    }
    state["events"] = {
        "validation": validation,
        "delist_confirmations_total_in_window": sum(
            len(v) for d, v in delist_conf.items() if d >= _START
        ),
        "susp_bites": susp_bites,
        "susp_bite_days": susp_bite_days,
        "susp_examples": susp_examples,
        "delist_bites": delist_bites,
        "delist_bite_days": delist_bite_days,
        "delist_examples": delist_examples,
        "pricelimit_bites": pricelimit_bites,
        "pricelimit_bite_days": pricelimit_bite_days,
    }
    _persist(state)
    print(f"[events] {json.dumps(state['events'], ensure_ascii=False)}", flush=True)


def main() -> int:
    state: dict[str, Any] = {}
    if _OUT.is_file():
        state = json.loads(_OUT.read_text(encoding="utf-8"))
    prices, hist = _load()
    print("loaded prices+hist", flush=True)
    experiment_affordability(prices, hist, state)
    experiment_events(prices, hist, state)
    experiment_capital(prices, hist, state)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
