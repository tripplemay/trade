#!/usr/bin/env python
"""B081 F005 evaluator follow-up — isolate capacity vs strategy-change in new_all_on.

- new_all_on@1M: the shipped baseline at capacity-adequate capital (does the -6.6%
  reverse? if yes, the red card's unconditional '策略样本外亏损' is capital-specific).
- fidelity_only@100k / @1M: lot+suspension+delist+price_limit+stamp5 but partial=False
  (pure execution-fidelity, WITHOUT the partial_rebalance strategy-cadence change) —
  the clean fidelity baseline the red card SHOULD rest on, at 100k vs 1M.

Reuses the B070 cached prices. Persists to b081_audit_followup.json.
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
_OUT = _B070_ROOT / "b081_audit_followup.json"
os.environ["WORKBENCH_DATA_ROOT"] = str(_B070_ROOT.resolve())


def _metrics(result) -> dict[str, Any]:
    import pandas as pd

    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
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
        "ending": round(result.ending_value, 0),
        "turnover": round(result.total_turnover, 2),
        "cost": round(result.total_cost, 0),
        "oos_cagr": round(annualized_return(oos), 4),
        "oos_sharpe": round(sharpe_ratio(oos_rets), 3),
        "rebs": result.rebalance_count,
    }


def main() -> int:
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import (
        CnAttackBacktestConfig,
        run_cn_attack_backtest,
    )
    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.strategies.cn_attack_momentum_quality.parameters import (
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    prices = pd.read_pickle(_PRICES_CACHE)  # noqa: S301
    hist = load_cn_universe_history(universe_path=_PIT)
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, weighting_scheme=WEIGHTING_SCHEME_EQUAL
    )

    new_all = dict(
        lot_rounding=True, partial_rebalance=True, suspension_halt=True,
        delist_liquidation=True, price_limit_gating=True,
    )
    fidelity_only = dict(
        lot_rounding=True, partial_rebalance=False, suspension_halt=True,
        delist_liquidation=True, price_limit_gating=True,
    )
    runs = [
        ("new_all_on@1M", 1_000_000.0, new_all, 5.0),
        ("fidelity_only@100k", 100_000.0, fidelity_only, 5.0),
        ("fidelity_only@1M", 1_000_000.0, fidelity_only, 5.0),
    ]
    state: dict[str, Any] = {}
    if _OUT.is_file():
        state = json.loads(_OUT.read_text(encoding="utf-8"))
    for label, cap, kw, stamp in runs:
        if label in state:
            print(f"{label}: cached", flush=True)
            continue
        cfg = CnAttackBacktestConfig(
            starting_capital=cap,
            cost_model=CnCostModel(stamp_duty_bps=stamp, commission_bps=2.5, slippage_bps=5.0),
            **kw,
        )
        result = run_cn_attack_backtest(
            params, cfg, _START, None, prices=prices, universe_history=hist
        )
        state[label] = _metrics(result)
        _OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"FOLLOWUP {label}: {json.dumps(state[label])}", flush=True)
    print("FOLLOWUP_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
