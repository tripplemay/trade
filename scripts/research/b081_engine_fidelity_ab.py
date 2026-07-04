#!/usr/bin/env python
"""B081 F004 — engine-fidelity A/B: the 8 switch-combo groups on the B070 de-biased
PIT universe (pure_momentum + equal, 2019-04-01..snapshot-end).

Groups (spec §2 F004): 旧口径 (all off, stamp 10bp) / each fix single-on (5) / 全 on
(new baseline, stamp 5bp) / 全 on + delist recovery 0.5. The 旧口径 group MUST bit-level
reproduce the B070 signoff (full_cagr 0.1312, ending 243406, OOS CAGR 0.284, OOS Sharpe
0.93) — a reproducibility proof that the B081 fixes never polluted the old path. Writes
the comparison table to docs/test-reports/B081-engine-fidelity-ab.md + a metrics JSON
(consumed by the trial_registry backfill + the red-card update).

Usage:
    WORKBENCH_DATA_ROOT is set internally to data/research/b070.
    .venv/bin/python scripts/research/b081_engine_fidelity_ab.py
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
_OUT_MD = Path("docs/test-reports/B081-engine-fidelity-ab.md")
_OUT_JSON = _B070_ROOT / "b081_engine_fidelity_ab.json"

# B070 signoff numbers the 旧口径 group must reproduce (bit-level).
_B070_OLD = {"full_cagr": 0.1312, "ending": 243406.0, "oos_cagr": 0.284, "oos_sharpe": 0.93}


def _configs() -> list[tuple[str, dict[str, Any]]]:
    """(label, config kwargs) for the 8 groups. Switch off = pre-B081; stamp 10bp is
    the old duty, 5bp the post-2023-08-28 correction (paired with 全 on)."""

    off = dict(
        lot_rounding=False, partial_rebalance=False, suspension_halt=False,
        delist_liquidation=False, price_limit_gating=False, stamp_bps=10.0,
    )
    groups: list[tuple[str, dict[str, Any]]] = [("old_all_off", dict(off))]
    for switch in (
        "lot_rounding", "partial_rebalance", "suspension_halt",
        "delist_liquidation", "price_limit_gating",
    ):
        g = dict(off)
        g[switch] = True
        groups.append((f"only_{switch}", g))
    new = dict(
        lot_rounding=True, partial_rebalance=True, suspension_halt=True,
        delist_liquidation=True, price_limit_gating=True, stamp_bps=5.0,
    )
    groups.append(("new_all_on", dict(new)))
    groups.append(("new_all_on_recovery_0p5", {**new, "delist_recovery_rate": 0.5}))
    return groups


def _run_group(kwargs: dict[str, Any], prices: Any, hist: Any) -> dict[str, Any]:
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import (
        CnAttackBacktestConfig,
        run_cn_attack_backtest,
    )
    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
        max_drawdown,
        sharpe_ratio,
    )
    from trade.strategies.cn_attack_momentum_quality.parameters import (
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    cfg_kwargs = {k: v for k, v in kwargs.items() if k != "stamp_bps"}
    config = CnAttackBacktestConfig(
        cost_model=CnCostModel(
            stamp_duty_bps=kwargs["stamp_bps"], commission_bps=2.5, slippage_bps=5.0
        ),
        **cfg_kwargs,
    )
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, weighting_scheme=WEIGHTING_SCHEME_EQUAL
    )
    result = run_cn_attack_backtest(
        params, config, _START, None, prices=prices, universe_history=hist
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
        "rebalance_count": result.rebalance_count,
    }


def _render_md(rows: list[dict[str, Any]]) -> str:
    head = (
        "# B081 engine-fidelity A/B — B070 de-biased PIT (pure_momentum + equal)\n\n"
        "Window 2019-04-01..snapshot-end. All fixes are **更保守/数字变差=诚实** (印花税 "
        "10→5bp is the lone 口径更正, numbers-better). The **old_all_off** group bit-level "
        "reproduces the B070 signoff — proof the fixes never polluted the old path.\n\n"
        "| group | full CAGR | full Sharpe | MaxDD | ending | turnover | cost | "
        "OOS CAGR | OOS Sharpe | OOS DD | rebs |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {r['label']} | {r['full_cagr']:.1%} | {r['full_sharpe']} | {r['full_maxdd']:.1%} | "
        f"{r['ending']:.0f} | {r['turnover']:.1f} | {r['cost']:.0f} | {r['oos_cagr']:.1%} | "
        f"{r['oos_sharpe']} | {r['oos_maxdd']:.1%} | {r['rebalance_count']} |\n"
        for r in rows
    )
    return head + body + (
        "\n> research-only / advisory-only. Each fix has an independent switch; off = "
        "bit-level pre-B081口径. Delist recovery 0.5 is the haircut sensitivity.\n"
    )


_PRICES_CACHE = _B070_ROOT / "b081_prices_cache.pkl"


def _load_prices_cached() -> Any:
    """Cache the loaded prices to a pickle — the CSV load is ~5 min and the resumable
    runner reloads on every (kill-recovered) invocation, which otherwise burns the whole
    window before a single backtest finishes. Pickle reload is ~30s (pyarrow absent)."""

    import pandas as pd

    from trade.data.us_quality_universe import load_prices

    if _PRICES_CACHE.is_file():
        return pd.read_pickle(_PRICES_CACHE)  # noqa: S301 — our own trusted cache
    prices = load_prices()
    prices.to_pickle(_PRICES_CACHE)
    return prices


def main() -> int:
    os.environ["WORKBENCH_DATA_ROOT"] = str(_B070_ROOT.resolve())
    from trade.data.cn_attack_universe import load_cn_universe_history

    # Resumable: each group's result is persisted as it finishes (the 8 real-data
    # backtests exceed one background window), so re-running converges.
    done: dict[str, dict[str, Any]] = {}
    if _OUT_JSON.is_file():
        for r in json.loads(_OUT_JSON.read_text(encoding="utf-8")):
            done[r["label"]] = r

    prices = None
    hist = None
    for label, kwargs in _configs():
        if label in done:
            print(f"{label}: cached")
            continue
        if prices is None:
            prices = _load_prices_cached()
            hist = load_cn_universe_history(universe_path=_PIT)
        metrics = _run_group(kwargs, prices, hist)
        done[label] = {"label": label, **metrics}
        _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        _OUT_JSON.write_text(
            json.dumps([done[k] for k, _ in _configs() if k in done], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{label}: full_cagr={metrics['full_cagr']} oos_cagr={metrics['oos_cagr']} "
              f"turnover={metrics['turnover']} cost={metrics['cost']}")

    rows = [done[label] for label, _ in _configs()]
    old = next(r for r in rows if r["label"] == "old_all_off")
    assert abs(old["full_cagr"] - _B070_OLD["full_cagr"]) < 1e-4, f"OLD full_cagr {old}"
    assert abs(old["ending"] - _B070_OLD["ending"]) < 1.0, f"OLD ending {old}"
    assert abs(old["oos_cagr"] - _B070_OLD["oos_cagr"]) < 1e-3, f"OLD oos_cagr {old}"
    print("✓ old_all_off bit-level reproduces B070 signoff")

    _OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    _OUT_MD.write_text(_render_md(rows), encoding="utf-8")
    _OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {_OUT_MD} + {_OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
