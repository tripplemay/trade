"""B111 F005 — A 股低波 first-look 运行器（离线读 B110 面板；★只算不裁 H7）。

产出一份**原始统计** JSON，交给 F007 的 Codex 裁定。产物中不得出现
GO / NO-GO / 值得投入 / 有 edge 一类措辞——该边界由
`tests/unit/test_ashare_pit_low_vol.py` 的机器判据锁住。

## 跑哪些口径（全部并排，禁事后挑选）

| key | 说明 |
|---|---|
| `main_stub_0.00` | 主口径：无滞后，全宇宙，退市 stub=0 |
| `g1_lag1_stub_0.00` | **★硬门 G1**：σ 排序滞后一月（t-13…t-2） |
| `g2_liquidity_stub_0.00` | **★硬门 G2**：剔除最低 30% 日均成交额（需 --liquidity） |
| `main_stub_-0.30` / `-1.00` | 退市 stub 敏感带（并排，不挑选） |

★★两个硬门是本方向唯一有信息量的部分（§B.2）：答案未知，任一不过即由 F007 裁定 NO-GO。
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.research.ashare_pit.low_vol import (
    HONESTY_STATEMENT,
    LOW_VOL_HONEST_LIMITS,
    build_sections,
    summarize_low_vol,
)

STUBS = ("0.00", "-0.30", "-1.00")
LIQUIDITY_DROP_FRACTION = 0.30


def read_detail(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_liquidity(path: Path) -> dict[str, dict[str, float]]:
    """读 G2 流动性 CSV（``formation_date, ts_code, amount``）→
    ``{formation_date: {ts_code: 日均成交额}}``。透明支持 ``.csv`` 与 ``.csv.gz``。"""
    opener = gzip.open if path.suffix == ".gz" else open
    out: dict[str, dict[str, float]] = {}
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                amount = float(row["amount"])
            except (KeyError, ValueError):
                continue
            out.setdefault(row["formation_date"], {})[row["ts_code"]] = amount
    return out


def run(
    rows: Sequence[Mapping[str, str]],
    *,
    liquidity: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    variants: dict[str, Any] = {}

    # 主口径（无滞后）+ 退市 stub 敏感带。
    for stub in STUBS:
        key = f"main_stub_{stub}"
        variants[key] = summarize_low_vol(
            build_sections(list(rows), stub=stub, lag=0), label=key
        )

    # ★硬门 G1：σ 排序滞后一月。
    g1_key = "g1_lag1_stub_0.00"
    variants[g1_key] = summarize_low_vol(
        build_sections(list(rows), stub="0.00", lag=1), label=g1_key
    )

    # ★硬门 G2：流动性过滤（需 --liquidity）。
    g2_key = "g2_liquidity_stub_0.00"
    if liquidity is not None:
        variants[g2_key] = summarize_low_vol(
            build_sections(
                list(rows),
                stub="0.00",
                lag=0,
                liquidity=liquidity,
                liquidity_drop_fraction=LIQUIDITY_DROP_FRACTION,
            ),
            label=g2_key,
        )
        g2_status = "executed"
    else:
        variants[g2_key] = {
            "label": g2_key,
            "status": "not_executed",
            "reason": (
                "缺 --liquidity（daily_basic.amount）；G2 是本方向唯一 API 成本，"
                "由 low_vol_liquidity_fetch.py 落盘后重跑。"
            ),
        }
        g2_status = "not_executed"

    dates = sorted({row["formation_date"] for row in rows})
    return {
        "honesty_statement": HONESTY_STATEMENT,
        "window": {
            "start": dates[0] if dates else None,
            "end": dates[-1] if dates else None,
            "n_months": len(dates),
            "frozen": "2013-01～2024-12 全区间；分段并排不用于挑选（§B.5）",
        },
        "hard_gates": {
            "role": (
                "★这两个尚未执行的证伪是本方向唯一有信息量的部分（§B.2）："
                "答案未知，阈值 +1.0pp 几何超额；施加与裁定归 F007（H7）。"
            ),
            "G1_lag_one_month": {
                "variant": g1_key,
                "threshold_geometric_excess_pp": 1.0,
                "rationale": "规模因子头条 >50% 死在这一刀下（lag0→1 断崖）；须实测不得推理。",
            },
            "G2_liquidity_filter": {
                "variant": g2_key,
                "status": g2_status,
                "drop_fraction": LIQUIDITY_DROP_FRACTION,
                "threshold_geometric_excess_pp": 1.0,
                "rationale": "低波溢价若住在流动性尾部，则对任何实盘规模不可执行。",
            },
        },
        "variants": variants,
        "honest_limits": LOW_VOL_HONEST_LIMITS,
        "generator_boundary": (
            "H7：本产物只含原始统计，不含任何裁定。主判据（σ 比 ≤0.90 且 ≥11/12 年）"
            "与副判据（几何超额>0 且 bootstrap P(>0)≥0.90）的施加、以及 G1/G2 硬门的判读，"
            "全部归 F007 的 Codex（铁律 #4）。已观测点估计是背景不作证据（§B.0）。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B111 F005 低波 first-look（只算不裁）")
    parser.add_argument(
        "--detail", type=Path, default=Path("data/research/B110/ep_panel.csv.gz")
    )
    parser.add_argument(
        "--liquidity",
        type=Path,
        default=None,
        help="G2 流动性 CSV（formation_date,ts_code,amount）；缺省则 G2 not_executed",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/audits/B111-F005-low-vol-first-look.json")
    )
    args = parser.parse_args(argv)

    rows = read_detail(args.detail)
    liquidity = read_liquidity(args.liquidity) if args.liquidity else None
    result = run(rows, liquidity=liquidity)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    main_variant = result["variants"]["main_stub_0.00"]
    g1 = result["variants"]["g1_lag1_stub_0.00"]
    print(f"月数(主): {main_variant['n_months']}  月数(G1): {g1['n_months']}")
    print(f"主 几何年化超额 V1-基准: {main_variant['excess_ann_geometric_vs_scored']}")
    print(f"G1 几何年化超额: {g1['excess_ann_geometric_vs_scored']}")
    print(f"主 已实现 σ 比 V1/基准: {main_variant['realized_sigma']['sigma_ratio']}")
    print(
        f"主 分年 V1 更低波: {main_variant['realized_sigma']['n_years_v1_lower']}"
        f"/{main_variant['realized_sigma']['n_years']}"
    )
    side = main_variant["arithmetic_side_by_side"]
    print(f"主 月度算术超额 t(简单/NW6): {side['monthly_excess_t_simple']}"
          f" / {side['monthly_excess_t_newey_west_lag6']}")
    print(f"主 bootstrap P(超额>0): {main_variant['bootstrap_geometric_excess']['p_positive']}")
    print(f"→ {args.out}（★裁定归 F007，本产物不含裁定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
