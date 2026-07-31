"""B111 F005 — A 股低波 first-look 运行器（离线读 B110 面板；★只算不裁 H7）。

产出一份**原始统计** JSON，交给 F007 的 Codex 裁定。产物中不得出现
GO / NO-GO / 值得投入 / 有 edge 一类措辞——该边界由
`tests/unit/test_ashare_pit_low_vol.py` 的机器判据锁住。

## 跑哪些口径（全部并排，禁事后挑选）

| key | 说明 |
|---|---|
| `main_stub_0.00` | 主口径：无滞后，全宇宙，退市 stub=0（含 B-wide 基准与差值） |
| `g1_lag1_stub_0.00` | **★硬门 G1**：σ 排序滞后一月（t-13…t-2） |
| `g2_liquidity_stub_0.00` | **★硬门 G2（正式）**：12 个月日均成交额剔最低 30%（dailyavg 文件） |
| `g2_proxy_single_day_stub_0.00` | 单日成交额**代理**（首轮粗口径，仅并排参考，不作正式 G2） |
| `n100_semiannual_stub_0.00` | §B.1 可实施口径：σ 最低 N=100 名、半年调仓 |
| `segments_stub_0.00` | §B.5 冻结分段（2014-2017 / 2018-2021 / 2022-2024）并排，不用于挑选 |
| `main_stub_-0.30` / `-1.00` | 退市 stub 敏感带（并排，不挑选） |

★★两个硬门是本方向唯一有信息量的部分（§B.2）：执行前答案未知，任一不过即由 F007 裁定。
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
    build_semiannual_n100,
    summarize_low_vol,
    summarize_segments,
)

STUBS = ("0.00", "-0.30", "-1.00")
LIQUIDITY_DROP_FRACTION = 0.30


def read_detail(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_liquidity(path: Path) -> dict[str, dict[str, float]]:
    """读 G2 流动性 CSV（``formation_date, ts_code, amount``）→
    ``{formation_date: {ts_code: 成交额}}``。透明支持 ``.csv`` 与 ``.csv.gz``。"""
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


def read_liquidity_dailyavg(path: Path) -> dict[str, dict[str, float]]:
    """读**正式 G2** 的 12 个月日均成交额 CSV（fix-round；
    ``formation_date, ts_code, avg_amount_12m, n_days``）→
    ``{formation_date: {ts_code: 日均成交额}}``。透明支持 ``.csv`` 与 ``.csv.gz``。"""
    opener = gzip.open if path.suffix == ".gz" else open
    out: dict[str, dict[str, float]] = {}
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                amount = float(row["avg_amount_12m"])
            except (KeyError, ValueError):
                continue
            out.setdefault(row["formation_date"], {})[row["ts_code"]] = amount
    return out


def run(
    rows: Sequence[Mapping[str, str]],
    *,
    liquidity: Mapping[str, Mapping[str, float]] | None = None,
    liquidity_dailyavg: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    variants: dict[str, Any] = {}

    # 主口径（无滞后）+ 退市 stub 敏感带。
    main_sections = build_sections(list(rows), stub="0.00", lag=0)
    for stub in STUBS:
        key = f"main_stub_{stub}"
        sections = main_sections if stub == "0.00" else build_sections(list(rows), stub=stub, lag=0)
        variants[key] = summarize_low_vol(sections, label=key)

    # ★硬门 G1：σ 排序滞后一月。
    g1_key = "g1_lag1_stub_0.00"
    variants[g1_key] = summarize_low_vol(
        build_sections(list(rows), stub="0.00", lag=1), label=g1_key
    )

    # ★硬门 G2（正式，fix-round）：12 个自然月日均成交额过滤，剔除最低 30%。
    g2_key = "g2_liquidity_stub_0.00"
    if liquidity_dailyavg is not None:
        variants[g2_key] = summarize_low_vol(
            build_sections(
                list(rows),
                stub="0.00",
                lag=0,
                liquidity=liquidity_dailyavg,
                liquidity_drop_fraction=LIQUIDITY_DROP_FRACTION,
            ),
            label=g2_key,
        )
        g2_status = "executed_daily_average"
    else:
        variants[g2_key] = {
            "label": g2_key,
            "status": "not_executed",
            "reason": (
                "缺 --liquidity-dailyavg（12 个月日均成交额）；正式 G2 由 "
                "low_vol_daily_amount_fetch.py 落盘后重跑。"
            ),
        }
        g2_status = "not_executed"

    # 单日成交额**代理**（首轮口径，已知粗口径限制；仅并排参考，不作正式 G2）。
    g2_proxy_key = "g2_proxy_single_day_stub_0.00"
    if liquidity is not None:
        variants[g2_proxy_key] = summarize_low_vol(
            build_sections(
                list(rows),
                stub="0.00",
                lag=0,
                liquidity=liquidity,
                liquidity_drop_fraction=LIQUIDITY_DROP_FRACTION,
            ),
            label=g2_proxy_key,
        )

    # §B.1 可实施口径：N=100 只、半年调仓。
    n100_key = "n100_semiannual_stub_0.00"
    variants[n100_key] = build_semiannual_n100(
        list(rows), stub="0.00", sections=main_sections
    )

    # §B.5 分段并排（冻结 4/4/3 年三分，不用于挑选）。
    segments_key = "segments_stub_0.00"
    variants[segments_key] = summarize_segments(main_sections, label="main_stub_0.00")

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
                "★这两个证伪（G1/G2）是本方向有信息量的部分（§B.2）："
                "门执行前答案未知，阈值 +1.0pp 几何超额；施加与裁定归 F007（H7）。"
            ),
            "G1_lag_one_month": {
                "variant": g1_key,
                "status": "executed",
                "threshold_geometric_excess_pp": 1.0,
                "rationale": "规模因子头条 >50% 死在这一刀下（lag0→1 断崖）；须实测不得推理。",
            },
            "G2_liquidity_filter": {
                "variant": g2_key,
                "status": g2_status,
                "caliber": (
                    "正式口径（fix-round）：形成日 t 前 12 个自然月（t-12, t] 内全部交易日）"
                    "的日成交额均值；停牌日无记录不视为零成交，覆盖天数随文件披露。"
                ),
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
        help="单日成交额代理 CSV（formation_date,ts_code,amount）；仅并排参考",
    )
    parser.add_argument(
        "--liquidity-dailyavg",
        type=Path,
        default=None,
        help="正式 G2 的 12 个月日均成交额 CSV（fix-round）；缺省则正式 G2 not_executed",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/audits/B111-F005-low-vol-first-look.json")
    )
    args = parser.parse_args(argv)

    rows = read_detail(args.detail)
    liquidity = read_liquidity(args.liquidity) if args.liquidity else None
    liquidity_dailyavg = (
        read_liquidity_dailyavg(args.liquidity_dailyavg) if args.liquidity_dailyavg else None
    )
    result = run(rows, liquidity=liquidity, liquidity_dailyavg=liquidity_dailyavg)

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
    g2 = result["variants"]["g2_liquidity_stub_0.00"]
    if g2.get("n_months"):
        print(f"G2(正式,12月日均) 几何年化超额: {g2['excess_ann_geometric_vs_scored']}")
    n100 = result["variants"]["n100_semiannual_stub_0.00"]
    print(f"N100半年调仓 几何年化超额: {n100['excess_ann_geometric']}  窗口数: {n100['n_windows']}")
    wide = main_variant["benchmark_wide"]
    print(
        f"B-wide/B-scored 几何年化: {wide['ann_benchmark_wide_geometric']}"
        f" / {wide['ann_benchmark_scored_geometric']}"
        f"  差: {wide['wide_minus_scored_pp']}pp"
    )
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
