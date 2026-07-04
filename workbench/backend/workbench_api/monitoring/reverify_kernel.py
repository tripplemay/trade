"""B080 F003 — frozen re-validation kernel (ported from the b070 comparison script).

Re-runs the de-biased cn_attack backtest with **parameters completely frozen** — the
entrypoint :func:`run_frozen_revalidation` accepts NO tunable argument; it constructs
``CnAttackParameters`` only from the module-level ``FROZEN_*`` constants. This is a
re-validation, not a re-training: the same rule is re-checked on appended data, never
re-fitted. ``_run_one`` + :func:`judge` are ported verbatim from
``scripts/research/b070_survivorship_comparison.py`` (the exact precedent
``monitoring/ic.py`` set for the b077 functions); the CPCV-lite per-split evaluation is
new. ``trade`` is imported lazily inside the functions (§12.10 producer discipline).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any

from workbench_api.monitoring.cpcv import CPCV_LITE_LABEL, cpcv_lite_splits

# ── FROZEN configuration (the guard's teeth: no caller can change these) ──────────
FROZEN_FACTOR_VARIANT = "pure_momentum"
FROZEN_WEIGHTING = "equal"
FROZEN_START = date(2019, 4, 1)
IN_SAMPLE_FRACTION = 0.7  # walk-forward 70/30 split (matches the b070 comparison)
PIT_RELPATH = ("snapshots", "universe", "cn_pit_universe.csv")
CONTROL_RELPATH = ("snapshots", "universe", "cn_pit_universe_current_control.csv")


def _frozen_params() -> Any:
    """Build the FROZEN CnAttackParameters — pure_momentum + equal weighting, all
    other knobs at their tested defaults. No value here is caller-derived."""

    from trade.strategies.cn_attack_momentum_quality.parameters import (  # type: ignore[import-untyped]
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
        weighting_scheme=WEIGHTING_SCHEME_EQUAL,
    )


def _run_one(
    label: str, universe_path: Path, prices: Any, start: date, end: date | None
) -> dict[str, Any]:
    """Run the frozen strategy on one universe → full + IS/OOS metrics (ported)."""

    import pandas as pd  # type: ignore[import-untyped]
    from trade.backtest.cn_attack_momentum_quality.engine import (  # type: ignore[import-untyped]
        run_cn_attack_backtest,
    )
    from trade.backtest.us_quality_momentum.metrics import (  # type: ignore[import-untyped]
        annualized_return,
        max_drawdown,
        sharpe_ratio,
    )
    from trade.data.cn_attack_universe import (  # type: ignore[import-untyped]
        load_cn_universe_history,
    )

    history = load_cn_universe_history(universe_path=universe_path)
    result = run_cn_attack_backtest(
        _frozen_params(), start=start, end=end, prices=prices, universe_history=history
    )
    curve = result.equity_curve

    def _seg(lo: Any, hi: Any) -> tuple[float, float, float]:
        seg = curve[(curve["date"] >= lo) & (curve["date"] <= hi)].reset_index(drop=True)
        if len(seg) < 2:
            return 0.0, 0.0, 0.0
        rets = seg.set_index("date")["equity"].pct_change().dropna()
        return annualized_return(seg), sharpe_ratio(rets), max_drawdown(seg)

    split = None
    if len(curve) >= 4:
        dates = curve["date"].tolist()
        idx = max(1, min(len(dates) - 2, int(len(dates) * IN_SAMPLE_FRACTION)))
        split = pd.Timestamp(dates[idx])
    if split is None:
        is_cagr = is_sharpe = oos_cagr = oos_sharpe = oos_dd = 0.0
        split_iso = None
    else:
        first = pd.Timestamp(curve["date"].iloc[0])
        last = pd.Timestamp(curve["date"].iloc[-1])
        is_cagr, is_sharpe, _ = _seg(first, split)
        oos_cagr, oos_sharpe, oos_dd = _seg(split, last)
        split_iso = split.date().isoformat()

    return {
        "label": label,
        "universe_breadth": max((len(m) for m in history.values()), default=0),
        "rebalance_count": result.rebalance_count,
        "exit_count": result.exit_count,
        "full_cagr": round(result.metrics.annualized_return, 4),
        "full_sharpe": round(result.metrics.sharpe_ratio, 3),
        "full_max_drawdown": round(result.metrics.max_drawdown, 4),
        "turnover": round(result.total_turnover, 2),
        "total_cost": round(result.total_cost, 2),
        "is_split_date": split_iso,
        "is_cagr": round(is_cagr, 4),
        "is_sharpe": round(is_sharpe, 3),
        "oos_cagr": round(oos_cagr, 4),
        "oos_sharpe": round(oos_sharpe, 3),
        "oos_max_drawdown": round(oos_dd, 4),
    }


def judge(pit: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    """The research verdict: does the strategy survive de-biasing? (ported)."""

    degenerate = pit["rebalance_count"] == 0 or pit["full_cagr"] == 0.0
    pit_holds = pit["oos_cagr"] > 0 and pit["oos_sharpe"] > 0
    if degenerate:
        verdict = "INCONCLUSIVE"
        reason = (
            "PIT backtest degenerate (no rebalances / flat equity) — NOT a real "
            "result; check data."
        )
    elif pit_holds:
        verdict = "SURVIVES_DEBIASING"
        reason = (
            "De-biased (PIT) OOS still positive CAGR AND Sharpe → the momentum edge is "
            "NOT purely a survivorship mirage (still research-only)."
        )
    else:
        verdict = "COLLAPSES_DEBIASING"
        reason = (
            "De-biased (PIT) OOS non-positive → the strong OOS was substantially a "
            "survivorship mirage; the strategy does not hold with delisted losers in."
        )
    return {
        "verdict": verdict,
        "reason": reason,
        "survivorship_bias_full_cagr": round(control["full_cagr"] - pit["full_cagr"], 4),
        "survivorship_bias_oos_cagr": round(control["oos_cagr"] - pit["oos_cagr"], 4),
        "survivorship_bias_oos_sharpe": round(control["oos_sharpe"] - pit["oos_sharpe"], 3),
        "pit_oos_cagr": pit["oos_cagr"],
        "pit_oos_sharpe": pit["oos_sharpe"],
        "control_oos_cagr": control["oos_cagr"],
        "control_oos_sharpe": control["oos_sharpe"],
    }


def _cpcv_lite(
    prices: Any, universe_path: Path, start: date, end: date
) -> dict[str, Any]:
    """Run the frozen strategy over each CPCV-lite OOS window → per-split OOS metric
    distribution (NOT full CPCV — labelled)."""


    from trade.backtest.cn_attack_momentum_quality.engine import run_cn_attack_backtest
    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
        sharpe_ratio,
    )
    from trade.data.cn_attack_universe import load_cn_universe_history

    history = load_cn_universe_history(universe_path=universe_path)
    splits = cpcv_lite_splits(start, end)
    per_split: list[dict[str, Any]] = []
    for sp in splits:
        result = run_cn_attack_backtest(
            _frozen_params(),
            start=sp.oos_start,
            end=sp.oos_end,
            prices=prices,
            universe_history=history,
        )
        curve = result.equity_curve
        if len(curve) < 2:
            continue
        rets = curve.set_index("date")["equity"].pct_change().dropna()
        per_split.append(
            {
                "index": sp.index,
                "oos_start": sp.oos_start.isoformat(),
                "oos_end": sp.oos_end.isoformat(),
                "oos_cagr": round(annualized_return(curve), 4),
                "oos_sharpe": round(sharpe_ratio(rets), 3),
            }
        )
    cagrs = [s["oos_cagr"] for s in per_split]
    sharpes = [s["oos_sharpe"] for s in per_split]
    return {
        "label": CPCV_LITE_LABEL,
        "n_splits": len(per_split),
        "splits": per_split,
        "oos_cagr_mean": round(mean(cagrs), 4) if cagrs else None,
        "oos_sharpe_mean": round(mean(sharpes), 3) if sharpes else None,
        # honest: positive-OOS split fraction is a robustness readout, not a signal.
        "oos_positive_frac": (
            round(sum(1 for c in cagrs if c > 0) / len(cagrs), 3) if cagrs else None
        ),
    }


def run_frozen_revalidation(data_root: Path, *, end: date | None = None) -> dict[str, Any]:
    """Frozen re-validation over the data at ``data_root`` (a reverify snapshot copy).

    Points the trade loaders at ``data_root`` (never production), runs the frozen
    PIT vs biased-control comparison + CPCV-lite, and returns the full payload
    (pit / control / judgment / cpcv_lite / window). Takes NO strategy parameter —
    that is the freeze contract the guard test enforces.
    """

    os.environ["WORKBENCH_DATA_ROOT"] = str(Path(data_root).resolve())

    import pandas as pd
    from trade.data.us_quality_universe import load_prices  # type: ignore[import-untyped]

    prices = load_prices()
    pit = _run_one(
        "survivorship_free_pit", Path(data_root).joinpath(*PIT_RELPATH),
        prices, FROZEN_START, end,
    )
    control = _run_one(
        "biased_control", Path(data_root).joinpath(*CONTROL_RELPATH),
        prices, FROZEN_START, end,
    )
    verdict = judge(pit, control)
    window_end = end or pd.Timestamp(prices["date"].max()).date()
    cpcv = _cpcv_lite(
        prices, Path(data_root).joinpath(*PIT_RELPATH), FROZEN_START, window_end
    )
    return {
        "batch": "reverify_frozen_revalidation",
        "window": f"{FROZEN_START.isoformat()}..{window_end.isoformat()}",
        "factor_variant": FROZEN_FACTOR_VARIANT,
        "weighting_scheme": FROZEN_WEIGHTING,
        "pit": pit,
        "control": control,
        "judgment": verdict,
        "cpcv_lite": cpcv,
    }
