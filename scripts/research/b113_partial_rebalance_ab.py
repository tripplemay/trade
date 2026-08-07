#!/usr/bin/env python
"""B113 F002 — cn_attack partial_rebalance 冻结 A/B 运行器（★只算不裁 H7）。

跑 spec §B.0 冻结矩阵：2 mode（pure/quality）× 2 臂（V0 全 band 现状 /
V1 partial_rebalance=True）× 2 本金档（10 万 / 100 万），窗口 2019-04-01→2026-07-31，
IS/OOS 机械 70/30。**数据链完全复用 B112 fix-round 产物**（top-1500 PIT 宇宙、
拼接价格、回填基本面、CSI300）——零新 API 成本。防御闸关闭（单自变量）。

判据输入（OOS ΔCAGR、OOS ΔMaxDD、年化换手倍率）与并列披露全部进产物；
**不含任何裁定措辞**（机器禁词判据）。cell 级 pickle 缓存可恢复（§45）。
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

# 复用 B112 的数据加载与统计原语（同一数据链，单一事实源）。
from scripts.research.b112_defense_gate_ab import (
    CAPITALS,
    IS_FRACTION,
    MODES,
    WINDOW_END,
    WINDOW_START,
    _deltas,
    _per_year_returns,
    _segment_metrics,
    load_inputs,
)
from trade.backtest.cn_attack_momentum_quality.engine import (
    CnAttackBacktestConfig,
    CnAttackBacktestResult,
    run_cn_attack_backtest,
)
from trade.strategies.cn_attack_momentum_quality.parameters import CnAttackParameters

_CACHE_DIR = Path("data/research/b113/ab_cache")
_DEFAULT_OUT_JSON = Path("docs/research/B113-F002-partial-rebalance-ab.json")

#: 诚实性声明原样入产物（判据预注册；Generator 只算不裁）。
HONESTY_STATEMENT = (
    "本批次的判据与口径先于任何 A/B 结果冻结（B113 spec §B.0/B.1）；partial_rebalance "
    "的 B081 实测值（OOS +28.4%→+32.7%）只作背景，不用于拟合或挑选窗口。"
    "本产物只含原始统计，裁定归 F003 的 Codex（H7）。"
)


def _run_cell(
    inputs: dict[str, Any], mode: str, variant: str, capital: float
) -> dict[str, Any]:
    """单 cell：mode × (V0 全 band | V1 partial) × 本金档。带 pickle 缓存。"""
    key = f"{mode}__{variant}__{int(capital)}"
    cache_path = _CACHE_DIR / f"{key}.pkl"
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            return pickle.load(handle)
    config = CnAttackBacktestConfig(
        starting_capital=capital,
        partial_rebalance=(variant == "v1_partial"),
    )
    result: CnAttackBacktestResult = run_cn_attack_backtest(
        CnAttackParameters(factor_variant=mode),
        config,
        WINDOW_START,
        WINDOW_END,
        prices=inputs["prices"],
        fundamentals=(
            inputs["fundamentals"] if mode != "pure_momentum" else None
        ),
        universe_history=inputs["universe_history"],
        index_close=inputs["index_close"],
    )
    curve = result.equity_curve
    split_index = int(len(curve) * IS_FRACTION)
    import pandas as pd

    split = pd.Timestamp(curve["date"].iloc[split_index])
    payload = {
        "mode": mode,
        "variant": variant,
        "capital": capital,
        "split_date": split.date().isoformat(),
        "ending_value": result.ending_value,
        "total_turnover": result.total_turnover,
        "annual_turnover": result.total_turnover / (result.trading_days / 252.0),
        "total_cost": result.total_cost,
        "rebalance_count": result.rebalance_count,
        "trading_days": result.trading_days,
        "segments": _segment_metrics(result, split),
        "per_year_returns": _per_year_returns(result),
    }
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(payload, handle)
    return payload


def _comparison(v0: dict[str, Any], v1: dict[str, Any]) -> dict[str, Any]:
    """判据输入：OOS/全样本 Δ + 年化换手倍率（V1/V0）。"""
    deltas = _deltas(v0, v1)
    ratio = (
        v1["annual_turnover"] / v0["annual_turnover"]
        if v0["annual_turnover"] > 0
        else None
    )
    return {
        "v0": v0,
        "v1": v1,
        "deltas": deltas,
        "annual_turnover_ratio": ratio,
    }


def run_matrix(out_json: Path) -> dict[str, Any]:
    inputs = load_inputs(include_fundamentals=True)
    cells: dict[str, Any] = {}
    for mode in MODES:
        for variant in ("v0_full_band", "v1_partial"):
            for capital in CAPITALS:
                cell = _run_cell(inputs, mode, variant, capital)
                cells[f"{mode}__{variant}__{int(capital)}"] = cell
                print(f"  done {mode}/{variant}/{int(capital)}", flush=True)

    comparisons: dict[str, Any] = {}
    for mode in MODES:
        for capital in CAPITALS:
            v0 = cells[f"{mode}__v0_full_band__{int(capital)}"]
            v1 = cells[f"{mode}__v1_partial__{int(capital)}"]
            comparisons[f"{mode}__{int(capital)}"] = _comparison(v0, v1)

    payload = {
        "honesty_statement": HONESTY_STATEMENT,
        "frozen_window": {
            "start": WINDOW_START.isoformat(),
            "end": WINDOW_END.isoformat(),
            "is_oos": "交易日机械 70/30（分割日见各 cell split_date）",
        },
        "ab_caliber": (
            "V0=partial_rebalance False（生产现状全 band）vs V1=True"
            "（per-name 阈值 0.5%，聚合计量带绕过）；防御闸关闭，单自变量"
        ),
        "criterion_thresholds": {
            "main_oos_delta_cagr_min_pp": 1.0,
            "secondary_oos_delta_maxdd_min_pp": -2.0,
            "secondary_annual_turnover_ratio_max": 3.0,
            "note": "阈值为陈述值，独立于观测；施加与裁定归 F003（H7）。",
        },
        "input_coverage": "复用 B112 数据链（见其产物 input_coverage，同源同文件）",
        "comparisons": comparisons,
        "generator_boundary": (
            "H7：本产物只含原始统计与判据输入，不含任何裁定；"
            "判据的施加与裁定归 F003 的 Codex（铁律 #4）。"
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B113 F002 partial_rebalance A/B（只算不裁）")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = run_matrix(args.out)
    for comp_key, comp in payload["comparisons"].items():
        oos = comp["deltas"]["oos"]
        print(
            f"{comp_key}: OOS ΔCAGR {oos['delta_cagr_pp']:+.2f}pp"
            f"  OOS ΔMaxDD {oos['delta_max_drawdown_pp']:+.2f}pp"
            f"  年化换手倍率 ×{comp['annual_turnover_ratio']:.2f}"
        )
    print(f"→ {args.out}（★裁定归 F003，本产物不含裁定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
