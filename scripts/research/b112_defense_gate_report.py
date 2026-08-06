"""B112 F001 — 防御闸 A/B 报告渲染（JSON → 人读 Markdown，★只算不裁 H7）。

读 `docs/research/B112-F001-defense-gate-ab.json`（runner 产物），渲染
`docs/research/B112-F001-defense-gate-ab.md`。判据阈值只作陈述值并列表头，
不施加裁定（禁词机器判据由 tests/unit/test_b112_defense_gate_ab.py 守住）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_DEFAULT_JSON = Path("docs/research/B112-F001-defense-gate-ab.json")
_DEFAULT_MD = Path("docs/research/B112-F001-defense-gate-ab.md")

_MODE_LABEL = {
    "pure_momentum": "纯动量",
    "quality_momentum": "质量动量",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}pp"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:+.3f}"


def render(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# B112 F001 — cn_attack 防御闸（MA200）冻结 A/B 结果（★只算不裁 H7）")
    lines.append("")
    lines.append("**日期：** 2026-08-04")
    lines.append(f"**窗口：** 冻结 {payload['frozen_window']['start']} → "
                 f"{payload['frozen_window']['end']}（{payload['frozen_window']['is_oos']}）")
    lines.append(f"**闸口径：** {payload['gate_caliber']}")
    lines.append("")
    lines.append("> ★H7：本报告只含原始统计与判据输入，不含任何裁定。"
                 "主判据（ΔMaxDD 全样本 ≥+5pp、OOS ≥+3pp）与副判据（ΔCAGR ≥−2pp、"
                 "ΔSharpe ≥−0.05）的施加归 F002 的 Codex（铁律 #4）。")
    lines.append("")

    th = payload["criterion_thresholds"]
    lines.append("## 判据输入总表（V1 − V0，正值=改善）")
    lines.append("")
    lines.append("| mode | 本金 | ΔMaxDD 全样本（门 ≥+5pp） | ΔMaxDD OOS（门 ≥+3pp） | "
                 "ΔCAGR（门 ≥−2pp） | ΔSharpe（门 ≥−0.05） |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for key, comp in sorted(payload["comparisons"].items()):
        mode, capital = key.rsplit("__", 1)
        full = comp["deltas"]["full"] or {}
        oos = comp["deltas"]["oos"] or {}
        lines.append(
            f"| {_MODE_LABEL.get(mode, mode)} | {int(capital):,} | "
            f"{_pp(full.get('delta_max_drawdown_pp'))} | "
            f"{_pp(oos.get('delta_max_drawdown_pp'))} | "
            f"{_pp(full.get('delta_cagr_pp'))} | "
            f"{_num(full.get('delta_sharpe'))} |"
        )
    lines.append("")
    lines.append(f"阈值陈述值（独立于观测）：主 {th['main_full_maxdd_improve_min_pp']:+.1f}pp/"
                 f"{th['main_oos_maxdd_improve_min_pp']:+.1f}pp；副 "
                 f"{th['secondary_delta_cagr_min_pp']:+.1f}pp/"
                 f"{th['secondary_delta_sharpe_min']:+.2f}。")
    lines.append("")

    lines.append("## 两臂绝对水平并排（全样本 | OOS）")
    lines.append("")
    lines.append("| mode | 本金 | 臂 | CAGR 全样本 | CAGR OOS | MaxDD 全样本 | MaxDD OOS | "
                 "Sharpe 全样本 | Sharpe OOS | 年化换手 | 成本 | 调仓次数 |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for key, comp in sorted(payload["comparisons"].items()):
        mode, capital = key.rsplit("__", 1)
        for arm in ("v0", "v1"):
            cell = comp[arm]
            full = cell["segments"]["full"]
            oos = cell["segments"].get("oos") or {}
            label = "V0 现状" if arm == "v0" else "V1 闸开"
            lines.append(
                f"| {_MODE_LABEL.get(mode, mode)} | {int(capital):,} | {label} | "
                f"{_pct(full['annualized_return'])} | "
                f"{_pct(oos.get('annualized_return'))} | "
                f"{_pct(full['max_drawdown'])} | "
                f"{_pct(oos.get('max_drawdown'))} | "
                f"{full['sharpe_ratio']:.3f} | "
                f"{oos.get('sharpe_ratio', 0.0):.3f} | "
                f"{cell['annual_turnover']:.2f} | "
                f"{cell['total_cost']:,.0f} | "
                f"{cell['rebalance_count']} |"
            )
    lines.append("")
    lines.append("年化换手 = 总换手 ÷（交易日数/252）；累计换手见 JSON 的 `total_turnover`。")
    lines.append("")

    lines.append("## 分年收益（全样本，V0 → V1）")
    lines.append("")
    years: list[str] = []
    for comp in payload["comparisons"].values():
        for year in comp["v0"]["per_year_returns"]:
            if year not in years:
                years.append(year)
    header = "| mode | 本金 | 臂 | " + " | ".join(years) + " |"
    lines.append(header)
    lines.append("|---|---:|---|" + "---:|" * len(years))
    for key, comp in sorted(payload["comparisons"].items()):
        mode, capital = key.rsplit("__", 1)
        for arm in ("v0", "v1"):
            per_year = comp[arm]["per_year_returns"]
            label = "V0" if arm == "v0" else "V1"
            row = " | ".join(_pct(per_year.get(year)) for year in years)
            lines.append(
                f"| {_MODE_LABEL.get(mode, mode)} | {int(capital):,} | {label} | {row} |"
            )
    lines.append("")

    lines.append("## 闸逐月状态（V1，留痕）")
    lines.append("")
    for key, comp in sorted(payload["comparisons"].items()):
        mode, capital = key.rsplit("__", 1)
        states = comp["v1"]["gate_states"]
        if not states:
            continue
        active_months = [s["month"] for s in states if s["active"]]
        fail_open = sorted(
            {s["reason"] for s in states if s["reason"].startswith("fail_open")}
        )
        active_str = ", ".join(active_months) if active_months else "无"
        lines.append(
            f"- **{_MODE_LABEL.get(mode, mode)} / {int(capital):,}**："
            f"评估月数 {len(states)}，防守月数 {len(active_months)}（{active_str}）"
            + (f"；fail-open 记录：{', '.join(fail_open)}" if fail_open else "")
        )
    lines.append("")

    # B112-F001-4 — H6 覆盖分母结构化呈现。
    coverage = payload.get("input_coverage")
    if coverage:
        lines.append("## 覆盖分母（H6，结构化披露）")
        lines.append("")
        universe = coverage["universe"]
        lines.append(
            f"- **宇宙**：{universe['n_blocks']} 个季度块，每块 "
            f"{universe['size_min']}–{universe['size_max']} 只；逐块分母见 JSON "
            f"`input_coverage.universe.block_sizes`。来源：{universe['source']}"
        )
        prices = coverage["prices"]
        lines.append(
            f"- **价格**：{prices['rows']:,} 行 / {prices['tickers']} 只，"
            f"{prices['date_min']} → {prices['date_max']}；去重：{prices['dedupe_rule']}"
        )
        for segment in prices["segments"]:
            lines.append(
                f"  - `{segment['name']}`：{segment['rows']:,} 行（{segment['span']}）"
            )
        index = coverage["index"]
        lines.append(
            f"- **指数**：序列 {index['series_days']} 个交易日；窗口交易日覆盖 "
            f"{index['window_trading_days_covered']}/{index['window_trading_days_total']}"
        )
        fundamentals = coverage.get("fundamentals")
        if fundamentals:
            rates = fundamentals["nonnull_rates"]
            lines.append(
                f"- **基本面**：{fundamentals['rows']:,} 行 / {fundamentals['tickers']} 只；"
                f"非空率 roe {rates['roe']:.1%} / 毛利率 {rates['gross_margin']:.1%} / "
                f"fcf_yield {rates['fcf_yield']:.1%} / 资产负债率 {rates['debt_to_assets']:.1%}；"
                f"回填失败 {fundamentals['backfill_failures']} 只（落盘留痕 "
                f"`fundamentals_backfill_failures.txt`）。{fundamentals['note']}"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**复现：** `python -m scripts.research.b112_defense_gate_ab`（cell 缓存在 "
                 "`data/research/b112/ab_cache/`），渲染 `python -m "
                 "scripts.research.b112_defense_gate_report`。")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B112 F001 防御闸 A/B 报告渲染")
    parser.add_argument("--input", type=Path, default=_DEFAULT_JSON)
    parser.add_argument("--out", type=Path, default=_DEFAULT_MD)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.write_text(render(payload), encoding="utf-8")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
