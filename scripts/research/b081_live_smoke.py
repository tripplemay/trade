#!/usr/bin/env python
"""B081 F005 — smoke: does compute_cn_attack_live_target run WITHOUT error under the
NEW default config (lot_rounding/partial_rebalance/suspension/delist/price_limit all
True, capital 100k)? De-risks the next production precompute (07-05 timer). Uses the
B070 cached prices as a stand-in dataset (the question is 'does it crash', not the
exact numbers). Reports rebalanced flag / n names / cash weight / would_be_turnover."""

from __future__ import annotations

import json
import os
from pathlib import Path

_B070_ROOT = Path("data/research/b070")
_PIT = _B070_ROOT / "snapshots" / "universe" / "cn_pit_universe.csv"
_PRICES_CACHE = _B070_ROOT / "b081_prices_cache.pkl"
os.environ["WORKBENCH_DATA_ROOT"] = str(_B070_ROOT.resolve())


def main() -> int:
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.engine import CnAttackBacktestConfig
    from trade.backtest.cn_attack_momentum_quality.live import compute_cn_attack_live_target
    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.strategies.cn_attack_momentum_quality.parameters import (
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    prices = pd.read_pickle(_PRICES_CACHE)  # noqa: S301 trusted cache
    hist = load_cn_universe_history(universe_path=_PIT)
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, weighting_scheme=WEIGHTING_SCHEME_EQUAL
    )
    for label, cfg in (
        ("new_default", CnAttackBacktestConfig()),  # B081 new defaults, 100k
        ("old_lot_off", CnAttackBacktestConfig(lot_rounding=False, partial_rebalance=False)),
    ):
        t = compute_cn_attack_live_target(
            params, cfg, prices=prices, universe_history=hist
        )
        out = {
            "config": label,
            "as_of": str(t.as_of_date),
            "rebalanced": t.rebalanced,
            "n_target_names": len(t.target_weights),
            "cash_weight": round(t.cash_weight, 4),
            "would_be_turnover": round(t.would_be_turnover, 4),
            "weights_sum": round(sum(t.target_weights.values()), 4),
            "n_profit_take": len(t.profit_take),
        }
        print("LIVE_SMOKE " + json.dumps(out, ensure_ascii=False), flush=True)
    print("LIVE_SMOKE_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
