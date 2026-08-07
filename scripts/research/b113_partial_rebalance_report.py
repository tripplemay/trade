#!/usr/bin/env python
"""B113 F002 — partial_rebalance A/B 报告渲染（JSON → Markdown，★只算不裁 H7）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_DEFAULT_JSON = Path("docs/research/B113-F002-partial-rebalance-ab.json")
_DEFAULT_MD = Path("docs/research/B113-F002-partial-rebalance-ab.md")

_MODE_LABEL = {
    "pure_momentum": "纯动量",
    "quality_momentum": "质量动量",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}pp"


def render(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# B113 F002 — partial_rebalance 冻结 A/B 结果（★只算不裁 H7）")
    lines.append("")
    lines.append("**日期：** 2026-08-06")
    lines.append(f"**窗口：** 冻结 {payload['frozen_window']['start']} → "
                 f"{payload['frozen_window']['end']}（{payload['frozen_window']['is_oos']}）")
    lines.append(f"**口径：** {payload['ab_caliber']}")
    lines.append("")
    lines.append("> ★H7：本报告只含原始统计与判据输入，不含任何裁定。主判据"
                 "（OOS ΔCAGR ≥+1.0pp）与副判据（OOS ΔMaxDD ≥−2.0pp、年化换手倍率 ≤3.0×）"
                 "的施加归 F003 的 Codex（铁律 #4）。")
    lines.append("")

    lines.append("## 判据输入总表（V1 partial − V0 全 band）")
    lines.append("")
    lines.append("| mode | 本金 | OOS ΔCAGR（门 ≥+1.0pp） | OOS ΔMaxDD（门 ≥−2.0pp） | "
                 "年化换手倍率（门 ≤3.0×） |")
    lines.append("|---|---:|---:|---:|---:|")
    for key, comp in sorted(payload["comparisons"].items()):
        mode, capital = key.rsplit("__", 1)
        oos = comp["deltas"]["oos"] or {}
        ratio = comp["annual_turnover_ratio"]
        lines.append(
            f"| {_MODE_LABEL.get(mode, mode)} | {int(capital):,} | "
            f"{_pp(oos.get('delta_cagr_pp'))} | "
            f"{_pp(oos.get('delta_max_drawdown_pp'))} | "
            f"{'—' if ratio is None else f'×{ratio:.2f}'} |"
        )
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
            label = "V0 全 band" if arm == "v0" else "V1 partial"
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
    lines.append("年化换手 = 总换手 ÷（交易日数/252）；换手倍率 = V1 年化换手 ÷ V0 年化换手。")
    lines.append("")

    lines.append("## 分年收益（全样本，V0 → V1）")
    lines.append("")
    years: list[str] = []
    for comp in payload["comparisons"].values():
        for year in comp["v0"]["per_year_returns"]:
            if year not in years:
                years.append(year)
    lines.append("| mode | 本金 | 臂 | " + " | ".join(years) + " |")
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
    lines.append("---")
    lines.append("")
    lines.append("**数据链：** 完全复用 B112 fix-round 产物（top-1500 PIT 宇宙、拼接价格、"
                 "回填基本面、CSI300），覆盖分母见其 `input_coverage`。")
    lines.append("")
    lines.append("**复现：** `python -m scripts.research.b113_partial_rebalance_ab`"
                 "（cell 缓存在 `data/research/b113/ab_cache/`），渲染 `python -m "
                 "scripts.research.b113_partial_rebalance_report`。")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B113 F002 报告渲染")
    parser.add_argument("--input", type=Path, default=_DEFAULT_JSON)
    parser.add_argument("--out", type=Path, default=_DEFAULT_MD)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.write_text(render(payload), encoding="utf-8")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
