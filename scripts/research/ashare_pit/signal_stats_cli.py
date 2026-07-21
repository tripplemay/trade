"""B110 F003 — 信号统计的运行器（离线，读 F002 落盘的面板明细）。

## ★★H7：本文件不下裁定

产出是一份**原始统计** JSON，交给 F004 的 Codex 裁定。产物中不得出现
GO / NO-GO / 值得投入 / 有 edge 一类措辞——该边界由
`tests/unit/test_ashare_pit_signal_stats.py` 的机器判据锁住。

## 跑哪些口径（全部并排，禁事后挑选）

| key | 说明 |
|---|---|
| `main_stub_0.00` | **主口径**：不剔除负 TTM，退市残值 stub = 0（附录 D3 + D6） |
| `main_stub_-0.30` / `-1.00` | D6 敏感带的另两档。★跨档翻转须由 Codex 判读 |
| `excl_negative_stub_0.00` | **对照组**：剔除负 TTM 后**重新分位**。仅作稳健性，不得用于裁定 |

★主口径与对照组的差异中，有一部分只是**切点位移**（负 TTM 占比 12–16%，剔除后顶层
20% 的绝对个数少约 10%），不是「剔除亏损股改善了信号」。报告须写清这一点。
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from scripts.research.ashare_pit.pipeline import to_jsonable
from scripts.research.ashare_pit.returns import DELIST_STUBS
from scripts.research.ashare_pit.signal_stats import (
    HONEST_LIMITS,
    MonthlyCrossSection,
    Observation,
    build_cross_section,
    summarize,
)


def read_detail(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _split(
    rows: Sequence[Mapping[str, str]], *, stub: str, exclude_negative: bool
) -> tuple[dict[str, list[Observation]], dict[str, list[Decimal]]]:
    """切成「进入五分位的样本池」与「B-wide 收益池」。

    ★B-wide 含**没有 E/P 但有前向收益**的名。它不参与裁定，但 D1 的
    ``coverage_composition_effect`` 靠它算出来，而那个数 >1.0pp 时判据会变档。
    """
    column = f"fwd_ret_stub_{stub}"
    scored: dict[str, list[Observation]] = {}
    wide: dict[str, list[Decimal]] = {}
    for row in rows:
        raw_return = row.get(column, "")
        if not raw_return:
            continue
        date = row["formation_date"]
        value = Decimal(raw_return)
        wide.setdefault(date, []).append(value)
        raw_ep = row.get("ep", "")
        if not raw_ep:
            continue
        ep = Decimal(raw_ep)
        if exclude_negative and ep < 0:
            continue
        mv = row.get("total_mv_cny", "")
        scored.setdefault(date, []).append(
            Observation(
                ts_code=row["ts_code"],
                formation_date=date,
                ep=ep,
                forward_return=value,
                delisted_later=row.get("delisted_later", "0") == "1",
                total_mv_cny=Decimal(mv) if mv else None,
            )
        )
    return scored, wide


def build_sections(
    rows: Sequence[Mapping[str, str]], *, stub: str, exclude_negative: bool = False
) -> list[MonthlyCrossSection]:
    scored, wide = _split(rows, stub=stub, exclude_negative=exclude_negative)
    sections: list[MonthlyCrossSection] = []
    for date in sorted(scored):
        section = build_cross_section(date, scored[date], wide_returns=wide.get(date, ()))
        if section is not None:
            sections.append(section)
    return sections


def run(detail_path: Path) -> dict[str, Any]:
    rows = read_detail(detail_path)
    variants: dict[str, Any] = {}
    for stub in DELIST_STUBS:
        key = f"main_stub_{stub}"
        variants[key] = summarize(build_sections(rows, stub=str(stub)), label=key)
    control_key = f"excl_negative_stub_{DELIST_STUBS[0]}"
    variants[control_key] = summarize(
        build_sections(rows, stub=str(DELIST_STUBS[0]), exclude_negative=True),
        label=control_key,
    )
    return {
        "adjudication_口径": {
            "primary_variant": f"main_stub_{DELIST_STUBS[0]}",
            "control_variant_not_for_adjudication": control_key,
            "sensitivity_variants": [f"main_stub_{stub}" for stub in DELIST_STUBS[1:]],
            "frozen_by": "docs/specs/B110-frozen-conventions-addendum.md (2026-07-21)",
        },
        "variants": variants,
        "honest_limits": HONEST_LIMITS,
        "generator_boundary": (
            "H7：本产物只含原始统计，不含任何裁定。三档预注册判据的应用与裁定归 F004 "
            "的 Codex（铁律 #4：不得自己评估自己）。主口径与对照组的差异中有一部分只是"
            "分位切点位移（负 TTM 占比 12-16%），不是「剔除亏损股改善了信号」。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B110 F003 信号统计（只算不裁）")
    parser.add_argument(
        "--detail", type=Path, default=Path("data/research/B110/ep_panel.csv.gz")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/audits/B110-F003-signal-stats.json")
    )
    args = parser.parse_args(argv)

    result = run(args.detail)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(to_jsonable(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    primary = result["variants"][result["adjudication_口径"]["primary_variant"]]
    print(f"月数: {primary['n_months']}")
    print(f"顶层组相对 B-scored 几何年化超额: {primary['excess_ann_geometric_vs_scored']}")
    print(f"标准误 / t: {primary['se_ann']} / {primary['t_stat']}")
    print(f"覆盖构成效应 (B-scored − B-wide): {primary['coverage_composition_effect']}")
    print(f"多头腿年化: {primary['legs']['a_long_ann']}")
    print(f"空头腿年化: {primary['legs']['a_short_ann']}")
    print(f"空头腿带符号占比: {primary['legs']['share_short']}")
    print(f"字面严格单调: {primary['monotonicity']['strictly_monotone_literal']}")
    print(f"正超额年份: {primary['yearly_excess']['n_positive_years']}"
          f"/{primary['yearly_excess']['n_years']}")
    print(f"→ {args.out}（★裁定归 F004，本产物不含裁定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
