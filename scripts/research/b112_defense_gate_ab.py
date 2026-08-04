"""B112 F001 — cn_attack 防御闸（MA200）冻结 A/B 运行器（★只算不裁 H7）。

跑 spec §1 冻结矩阵：2 mode（pure/quality）× 2 臂（V0 现状 / V1 闸开）
× 2 本金档（10 万 / 100 万），窗口 2019-04-01→2026-07-31，IS/OOS = 窗口交易日
机械 70/30 切分。判据输入（ΔMaxDD 全样本/OOS、ΔCAGR、ΔSharpe）与并列披露
（换手/成本/分年/闸逐月状态）全部进产物；**不含任何裁定措辞**（机器禁词判据）。

数据来源（留痕，H6）：

- 价格：`b070/b081_prices_cache.pkl`（2018-01→2026-06-18，去偏 PIT 1310 只）
  + `b112_prices_ext.pkl`（生产延伸 06-22→07-31，复权连续性已抽查）。
- 宇宙：`b070/cn_pit_universe.csv`（2019-03→2026-03 共 29 块）+ 生产 2026-06-30 块。
- 基本面：`fundamentals_full.csv`（本批 akshare 深历史回填 + 生产新鲜段，CSRC 披露死线口径）。
- 指数：`b112_csi300.pkl`（生产 cn_csi300.csv，2002→2026-08）。

## 可恢复（§45 教训）

每个 cell 的结果 pickle 到 `data/research/b112/ab_cache/`，重跑跳过已完成 cell。
"""

from __future__ import annotations

import argparse
import json
import pickle
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.defense_gate import DefenseGateConfig
from trade.backtest.cn_attack_momentum_quality.engine import (
    CnAttackBacktestConfig,
    CnAttackBacktestResult,
    run_cn_attack_backtest,
)
from trade.backtest.us_quality_momentum.metrics import compute_performance_metrics
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    CnAttackParameters,
)

# ★spec §1 冻结窗口（含 2026-07 崩盘月——预注册，非挑选）。
WINDOW_START = date(2019, 4, 1)
WINDOW_END = date(2026, 7, 31)
IS_FRACTION = 0.70  # WF 70/30（B066/B070/B081 传统），分割点由窗口机械导出
CAPITALS = (100_000.0, 1_000_000.0)  # B081 容量教训：双本金档并排
MODES = (FACTOR_VARIANT_PURE_MOMENTUM, FACTOR_VARIANT_QUALITY_MOMENTUM)

_PRICES_BASE = Path("data/research/b070/b081_prices_cache.pkl")
_PRICES_EXT = Path("data/research/b112/b112_prices_ext.pkl")
_UNIVERSE_BASE = Path("data/research/b070/snapshots/universe/cn_pit_universe.csv")
_UNIVERSE_EXT = Path("data/research/b112/b112_universe.pkl")
_FUNDAMENTALS = Path("data/research/b112/fundamentals_full.csv")
_CSI300 = Path("data/research/b112/b112_csi300.pkl")
_CACHE_DIR = Path("data/research/b112/ab_cache")
_DEFAULT_OUT_JSON = Path("docs/research/B112-F001-defense-gate-ab.json")

#: §B.0 同款诚实性声明原样入产物（本批判据预注册；Generator 只算不裁）。
HONESTY_STATEMENT = (
    "本批次的判据与口径先于任何 A/B 结果冻结（spec §1/§2）；前向 −41% 只作触发背景，"
    "未用于拟合闸参数或挑选窗口。本产物只含原始统计，裁定归 F002 的 Codex（H7）。"
)


def load_fundamentals_frame(path: Path) -> pd.DataFrame:
    """读回填基本面 CSV 并归一到 loader 契约（B112-F001-2 修复点）。

    - ``report_date`` / ``fiscal_quarter_end`` → datetime64（quality 因子按
      ``report_date <= cutoff`` 比较，字符串会 TypeError——远端 HEAD 复跑即
      死在这里，因为修复最初只在本地未提交）；
    - ``pe/pb/ev_ebitda/earnings_yield`` 缺列补 NaN（quality_score 的
      _ensure_columns 契约；CN composite 不读这四列）。
    """

    frame = pd.read_csv(path)
    for column in ("report_date", "fiscal_quarter_end"):
        frame[column] = pd.to_datetime(frame[column])
    for column in ("pe", "pb", "ev_ebitda", "earnings_yield"):
        if column not in frame.columns:
            frame[column] = float("nan")
    return frame


def load_inputs(*, include_fundamentals: bool = True) -> dict[str, Any]:
    base = pd.read_pickle(_PRICES_BASE)
    ext = pd.read_pickle(_PRICES_EXT)
    prices = pd.concat([base, ext], ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"])

    # ★宇宙口径（2026-08-04 调试实证后冻结）：只用 b070 去偏 PIT 研究宇宙
    #（800 名季度块，B070/B081 已验证基线同源）。生产宇宙（~1500 名、B075 扩口径、
    # 方法论不同）不得并集混入（同 as_of 会并出伪宇宙）；2026-04 起的日子按 PIT 规则
    # 解析最近块（2026-03-31）——研究与生产的宇宙口径差在报告中如实披露。
    universe = pd.read_csv(_UNIVERSE_BASE)
    universe["as_of_date"] = pd.to_datetime(universe["as_of_date"]).dt.date
    universe = universe.sort_values(["as_of_date", "rank"])
    universe_history = {
        day: tuple(group["ticker"])
        for day, group in universe.groupby("as_of_date")
    }

    fundamentals = None
    if include_fundamentals:
        if not _FUNDAMENTALS.is_file():
            raise FileNotFoundError(
                f"fundamentals 尚未回填完成：{_FUNDAMENTALS}（quality mode 必需；"
                "pure mode 可用 include_fundamentals=False）"
            )
        fundamentals = load_fundamentals_frame(_FUNDAMENTALS)
    csi300 = pd.read_pickle(_CSI300)
    index_close = pd.Series(
        pd.to_numeric(csi300["close"]).to_numpy(),
        index=pd.to_datetime(csi300["date"]),
    ).sort_index()
    return {
        "prices": prices,
        "fundamentals": fundamentals,
        "universe_history": universe_history,
        "index_close": index_close,
    }


def _segment_metrics(result: CnAttackBacktestResult, split: pd.Timestamp) -> dict[str, Any]:
    """全样本 + OOS 段指标（OOS 段自分割点重定基；MaxDD 为段内口径）。"""
    curve = result.equity_curve
    out: dict[str, Any] = {"full": result.metrics.as_dict()}
    oos = curve[curve["date"] > split].copy()
    if len(oos) >= 2:
        rebase = float(curve.loc[curve["date"] <= split, "equity"].iloc[-1])
        oos["equity"] = oos["equity"] / rebase
        oos_returns = oos.set_index("date")["equity"].pct_change().dropna()
        out["oos"] = compute_performance_metrics(
            oos, oos_returns, result.total_turnover
        ).as_dict()
    else:
        out["oos"] = None
    return out


def _per_year_returns(result: CnAttackBacktestResult) -> dict[str, float]:
    curve = result.equity_curve.set_index("date")["equity"]
    out: dict[str, float] = {}
    for year, group in curve.groupby(curve.index.year):
        out[str(year)] = float(group.iloc[-1] / group.iloc[0] - 1.0)
    return out


def _input_coverage(inputs: dict[str, Any]) -> dict[str, Any]:
    """H6 覆盖分母（B112-F001-4）：宇宙/指数/基本面/价格的覆盖与缺口统计，
    结构化入产物，不静默。"""
    universe_history = inputs["universe_history"]
    block_sizes = {str(day): len(members) for day, members in universe_history.items()}
    prices = inputs["prices"]
    index = inputs["index_close"]
    coverage: dict[str, Any] = {
        "universe": {
            "source": "见报告数据源表（b070 去偏 PIT 块）",
            "n_blocks": len(block_sizes),
            "block_sizes": block_sizes,
            "size_min": min(block_sizes.values()),
            "size_max": max(block_sizes.values()),
        },
        "prices": {
            "rows": int(len(prices)),
            "tickers": int(prices["ticker"].nunique()),
            "date_min": str(prices["date"].min().date()),
            "date_max": str(prices["date"].max().date()),
            "splice": "b081 cache（→2026-06-18）+ 生产延伸（2026-06-22→07-31）",
        },
        "index": {
            "series_days": int(len(index)),
            "window_days_covered": int(
                pd.to_datetime(pd.Series(pd.date_range(WINDOW_START, WINDOW_END))).isin(
                    index.index
                ).sum()
            ),
        },
    }
    failures_path = Path("data/research/b112/fundamentals_backfill_failures.txt")
    if _FUNDAMENTALS.is_file():
        fund = pd.read_csv(_FUNDAMENTALS)
        coverage["fundamentals"] = {
            "rows": int(len(fund)),
            "tickers": int(fund["ticker"].nunique()),
            "nonnull_rates": {
                column: round(float(fund[column].notna().mean()), 4)
                for column in ("roe", "gross_margin", "fcf_yield", "debt_to_assets")
            },
            "backfill_failures": (
                sum(1 for _ in failures_path.open()) if failures_path.is_file() else 0
            ),
            "note": "fcf_yield 在部分中报季为 NaN（akshare 字段固有缺口，生产同口径）。",
        }
    return coverage


def _run_cell(
    inputs: dict[str, Any], mode: str, variant: str, capital: float
) -> dict[str, Any]:
    """单 cell：mode × (V0|V1) × 本金档。带 pickle 缓存（可恢复）。"""
    key = f"{mode}__{variant}__{int(capital)}"
    cache_path = _CACHE_DIR / f"{key}.pkl"
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            return pickle.load(handle)
    config = CnAttackBacktestConfig(
        starting_capital=capital,
        defense_gate=DefenseGateConfig() if variant == "v1_gate" else None,
    )
    result = run_cn_attack_backtest(
        CnAttackParameters(factor_variant=mode),
        config,
        WINDOW_START,
        WINDOW_END,
        prices=inputs["prices"],
        fundamentals=(
            inputs["fundamentals"]
            if mode != FACTOR_VARIANT_PURE_MOMENTUM
            else None
        ),
        universe_history=inputs["universe_history"],
        index_close=inputs["index_close"],
    )
    split_index = int(len(result.equity_curve) * IS_FRACTION)
    split = pd.Timestamp(result.equity_curve["date"].iloc[split_index])
    payload = {
        "mode": mode,
        "variant": variant,
        "capital": capital,
        "split_date": split.date().isoformat(),
        "ending_value": result.ending_value,
        "total_turnover": result.total_turnover,
        # B112-F001-4 — 年化换手（判据/披露输入）：总换手 ÷（交易日/252）。
        "annual_turnover": result.total_turnover / (result.trading_days / 252.0),
        "total_cost": result.total_cost,
        "rebalance_count": result.rebalance_count,
        "trading_days": result.trading_days,
        "segments": _segment_metrics(result, split),
        "per_year_returns": _per_year_returns(result),
        "gate_states": [asdict(state) for state in result.gate_states],
    }
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(payload, handle)
    return payload


def _deltas(v0: dict[str, Any], v1: dict[str, Any]) -> dict[str, Any]:
    """V1 − V0 的判据输入（pp 单位）。"""
    out: dict[str, Any] = {}
    for segment in ("full", "oos"):
        a = v0["segments"].get(segment)
        b = v1["segments"].get(segment)
        if not a or not b:
            out[segment] = None
            continue
        out[segment] = {
            # MaxDD 为负值；V1 − V0 > 0 = 回撤变浅 = 改善（与 spec 门槛同向）。
            "delta_max_drawdown_pp": (b["max_drawdown"] - a["max_drawdown"]) * 100.0,
            "delta_cagr_pp": (b["annualized_return"] - a["annualized_return"]) * 100.0,
            "delta_sharpe": b["sharpe_ratio"] - a["sharpe_ratio"],
        }
    return out


def run_matrix(out_json: Path, modes: tuple[str, ...] = MODES) -> dict[str, Any]:
    needs_quality = any(mode != FACTOR_VARIANT_PURE_MOMENTUM for mode in modes)
    inputs = load_inputs(include_fundamentals=needs_quality)
    cells: dict[str, Any] = {}
    for mode in modes:
        for variant in ("v0_current", "v1_gate"):
            for capital in CAPITALS:
                cell = _run_cell(inputs, mode, variant, capital)
                cells[f"{mode}__{variant}__{int(capital)}"] = cell
                print(f"  done {mode}/{variant}/{int(capital)}", flush=True)

    comparisons: dict[str, Any] = {}
    for mode in modes:
        for capital in CAPITALS:
            v0 = cells[f"{mode}__v0_current__{int(capital)}"]
            v1 = cells[f"{mode}__v1_gate__{int(capital)}"]
            comparisons[f"{mode}__{int(capital)}"] = {
                "v0": v0,
                "v1": v1,
                "deltas": _deltas(v0, v1),
            }

    payload = {
        "honesty_statement": HONESTY_STATEMENT,
        "frozen_window": {
            "start": WINDOW_START.isoformat(),
            "end": WINDOW_END.isoformat(),
            "is_oos": "交易日机械 70/30（分割日见各 cell split_date）",
        },
        "gate_caliber": (
            "月末 CSI300 收盘 < 200 日 SMA（≤评估日）→ 次月 100% 现金；"
            "MA200 冻结；fail-open 留痕"
        ),
        "criterion_thresholds": {
            "main_full_maxdd_improve_min_pp": 5.0,
            "main_oos_maxdd_improve_min_pp": 3.0,
            "secondary_delta_cagr_min_pp": -2.0,
            "secondary_delta_sharpe_min": -0.05,
            "note": "阈值为陈述值，独立于观测；施加与裁定归 F002（H7）。",
        },
        "input_coverage": _input_coverage(inputs),
        "comparisons": comparisons,
        "generator_boundary": (
            "H7：本产物只含原始统计与判据输入，不含任何裁定；"
            "判据的施加与裁定归 F002 的 Codex（铁律 #4）。"
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 F001 防御闸冻结 A/B（只算不裁）")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT_JSON)
    parser.add_argument(
        "--modes",
        type=str,
        default=",".join(MODES),
        help="逗号分隔（pure_momentum 不需要基本面，可先跑）",
    )
    args = parser.parse_args(argv)
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    payload = run_matrix(args.out, modes)
    for comp_key, comp in payload["comparisons"].items():
        full = comp["deltas"]["full"]
        oos = comp["deltas"]["oos"]
        print(
            f"{comp_key}: ΔMaxDD full {full['delta_max_drawdown_pp']:+.2f}pp"
            f" / OOS {oos['delta_max_drawdown_pp']:+.2f}pp"
            f"  ΔCAGR {full['delta_cagr_pp']:+.2f}pp  ΔSharpe {full['delta_sharpe']:+.3f}"
        )
    print(f"→ {args.out}（★裁定归 F002，本产物不含裁定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
