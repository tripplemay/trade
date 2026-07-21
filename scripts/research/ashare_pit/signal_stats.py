"""B110 F003 — 信号统计**计算工具**（纯逻辑，不联网）。

## ★★H7 硬边界：只算不裁

本模块**只产出原始统计**。产物与任何由它生成的报告中**不得出现**
「GO」/「NO-GO」/「值得投入」/「有 edge」一类结论性措辞——裁定权归 F004 的 Codex
（铁律 #4：不得自己评估自己）。

这个分工是有意的：B103-B105 正是 Codex 在验收阶段拆腿，才推翻了 IC ~0.15 的纸面结论
（**90-107% 的收益落在 A 股不可做空的短腿上**）。让实施方既算信号又下裁定，
等于自己批准自己的后续工作。

## 冻结口径（`docs/specs/B110-frozen-conventions-addendum.md`，2026-07-21 用户裁定）

| | |
|---|---|
| **D1 基准** | **B-scored** = 进入五分位的名等权。同时出 B-wide 与覆盖构成效应 |
| **D2 年化** | **几何** `∏(1+r)^(12/n) − 1`；算术版并排不参与裁定 |
| **D3 负 TTM** | 按 E/P 数值**参与排序**（落底部分位）+ overlay 单独出收益；对照组 = 剔负重分位 |
| **D6 退市** | 最后成交价 + `{0, −0.30, −1.00}` 三档 stub **全跑并排** |

## ★三条必须随统计一同呈现的算术事实

1. **拆腿的加法恒等式只在月度算术下成立**，对几何年化不成立（残差可达 0.22pp）。
   故拆腿一段固定用 `mean_monthly × 12`，与 D2 的几何裁定口径并存。
2. **空头腿占比是带符号占比** `a_short / (a_long + a_short)`。>100% 恰恰等价于
   **多头腿 alpha 为负**——这正是 B103-B105 的实质结论。★禁用绝对值占比：
   它永远 ≤100%，**永远看不出多头腿是负的**。
3. **相邻五分位的年化差 SE ≈ 2.5%/年**（组间相关 ρ≈0.95）。任何依赖相邻组排序的
   判据都在测噪声。字面单调性判据照常输出（预注册锁死），但必须并排给出 SE。

## ★统计功效（必须原样进入产物）

顶层组月度超额 σ ≈ 1.5% → `SE(年化超额) = 1.5% × 12 / √144 ≈ 1.5%/年`。
点估计 3.0% 对应 t ≈ 2.0，**95% CI ≈ [0.0%, 6.0%]，横跨三档全部**。
本设计在统计上无法区分预注册的三档；阈值是**投资决策线，不是统计推断**。
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

#: 分位数。Q5 = E/P 最高。
N_QUANTILES = 5
TOP_GROUP = "Q5"
BOTTOM_GROUP = "Q1"
#: 单调性斜率组合权重（Σ|w| = 1），M1 诊断用。
_SLOPE_WEIGHTS: tuple[float, ...] = (-2 / 6, -1 / 6, 0.0, 1 / 6, 2 / 6)


@dataclass(frozen=True)
class Observation:
    """一个 (证券 × 形成日) 观测。``ep`` 与 ``forward_return`` 都必须非空。"""

    ts_code: str
    formation_date: str
    ep: Decimal
    forward_return: Decimal
    delisted_later: bool = False
    total_mv_cny: Decimal | None = None


@dataclass(frozen=True)
class MonthlyCrossSection:
    formation_date: str
    #: 组名 → 该组等权月度收益
    group_returns: dict[str, Decimal]
    group_counts: dict[str, int]
    benchmark_scored: Decimal
    benchmark_wide: Decimal
    ic: float | None
    n_scored: int
    n_wide: int
    #: D3 overlay：负 E/P 名单独成组的等权收益（它们**同时**已参与五分位排序）。
    negative_overlay_return: Decimal | None = None
    negative_overlay_count: int = 0
    group_median_mv: dict[str, Decimal | None] = field(default_factory=dict)
    delisted_later_by_group: dict[str, int] = field(default_factory=dict)


# --- 基础统计（scipy 未安装，全部手写并可被独立复核）---


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def rank_average_ties(values: Sequence[float]) -> list[float]:
    """平均秩（并列取均值）。Spearman 的前置步骤。"""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2 + 1
        for index in range(position, end + 1):
            ranks[order[index]] = average
        position = end + 1
    return ranks


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    """秩相关。★scipy 未安装，此处手写；并列用平均秩（A 股涨跌停会造成大量并列）。"""
    if len(left) != len(right) or len(left) < 3:
        return None
    x, y = rank_average_ties(left), rank_average_ties(right)
    mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
    dx = [value - mean_x for value in x]
    dy = [value - mean_y for value in y]
    denominator = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / denominator


def geometric_annual(returns: Sequence[Decimal]) -> float | None:
    """D2 裁定口径：``∏(1+r)^(12/n) − 1``。任一期 ≤ −100% 则整体归零后无意义。"""
    if not returns:
        return None
    growth = Decimal(1)
    for value in returns:
        growth *= Decimal(1) + value
    if growth <= 0:
        return -1.0
    return float(growth ** (Decimal(12) / Decimal(len(returns)))) - 1.0


def arithmetic_annual(returns: Sequence[Decimal]) -> float | None:
    """并排披露口径；★拆腿归因**固定用它**（加法恒等式只在算术下成立）。"""
    if not returns:
        return None
    return float(_mean(returns)) * 12


def _stdev(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def annual_standard_error(monthly_excess: Sequence[Decimal]) -> float | None:
    """年化超额的标准误 = ``σ_月 × 12 / √n``。★必须与点估计并排输出。"""
    values = [float(value) for value in monthly_excess]
    sigma = _stdev(values)
    if sigma is None or not values:
        return None
    return sigma * 12 / math.sqrt(len(values))


# --- 分组 ---


def assign_quantiles(
    observations: Sequence[Observation], *, n_groups: int = N_QUANTILES
) -> dict[str, str]:
    """按 E/P **降序**等数量切组，``Q{n_groups}`` = E/P 最高。

    ★D3：负 E/P **照常参与排序**（自然落到底部组）。这里**没有**任何符号过滤——
    一旦有，spec §3.4 的双口径设计在实现层就被架空了。
    """
    if len(observations) < n_groups:
        return {}
    ordered = sorted(observations, key=lambda item: item.ep, reverse=True)
    total = len(ordered)
    out: dict[str, str] = {}
    for index, item in enumerate(ordered):
        bucket = min(index * n_groups // total, n_groups - 1)
        out[item.ts_code] = f"Q{n_groups - bucket}"
    return out


def build_cross_section(
    formation_date: str,
    scored: Sequence[Observation],
    *,
    wide_returns: Sequence[Decimal] = (),
    n_groups: int = N_QUANTILES,
) -> MonthlyCrossSection | None:
    """一个形成日的分组、基准与 IC。

    ``scored`` = 有 E/P 且有前向收益者（D1 的 **B-scored** 样本池）。
    ``wide_returns`` = 全宇宙中**有前向收益者**的收益（含无 E/P 的名），
    用于 B-wide 基准与覆盖污染项——★它不参与裁定，但必须出。
    """
    if len(scored) < n_groups:
        return None
    assignment = assign_quantiles(scored, n_groups=n_groups)
    grouped: dict[str, list[Observation]] = {}
    for item in scored:
        grouped.setdefault(assignment[item.ts_code], []).append(item)

    group_returns = {
        name: _mean([item.forward_return for item in members])
        for name, members in grouped.items()
    }
    negatives = [item for item in scored if item.ep < 0]
    return MonthlyCrossSection(
        formation_date=formation_date,
        group_returns=group_returns,
        group_counts={name: len(members) for name, members in grouped.items()},
        benchmark_scored=_mean([item.forward_return for item in scored]),
        benchmark_wide=_mean(list(wide_returns)) if wide_returns else _mean(
            [item.forward_return for item in scored]
        ),
        ic=spearman(
            [float(item.ep) for item in scored],
            [float(item.forward_return) for item in scored],
        ),
        n_scored=len(scored),
        n_wide=len(wide_returns) if wide_returns else len(scored),
        # ★D3 overlay：负 E/P 名已参与排序，这里额外单独出一次收益。
        negative_overlay_return=(
            _mean([item.forward_return for item in negatives]) if negatives else None
        ),
        negative_overlay_count=len(negatives),
        group_median_mv={
            name: _median([item.total_mv_cny for item in members if item.total_mv_cny])
            for name, members in grouped.items()
        },
        delisted_later_by_group={
            name: sum(1 for item in members if item.delisted_later)
            for name, members in grouped.items()
        },
    )


# --- 拆腿归因（★本批次最重要的一段）---


def leg_attribution(sections: Sequence[MonthlyCrossSection]) -> dict[str, object]:
    """把多空收益拆成「多头腿相对基准」+「空头腿相对基准」。

    ★恒等式 ``r_LS = a_long + a_short`` **只在月度算术下成立**，故全段用算术均值 ×12。

    ★占比是**带符号**的 ``a_short / (a_long + a_short)``：>100% 恰恰等价于多头腿
    alpha 为负，这正是 B103-B105 的实质结论。绝对值占比永远 ≤100%，
    **永远看不出多头腿是负的**，会被读成「多头也有一点贡献」。
    """
    long_leg: list[Decimal] = []
    short_leg: list[Decimal] = []
    spread: list[Decimal] = []
    for section in sections:
        top = section.group_returns.get(TOP_GROUP)
        bottom = section.group_returns.get(BOTTOM_GROUP)
        if top is None or bottom is None:
            continue
        benchmark = section.benchmark_scored
        long_leg.append(top - benchmark)
        short_leg.append(benchmark - bottom)
        spread.append(top - bottom)
    if not spread:
        return {"role": "diagnostic_only_not_a_criterion", "n_months": 0}

    a_long = float(_mean(long_leg)) * 12
    a_short = float(_mean(short_leg)) * 12
    total = a_long + a_short
    share: float | None = None
    reason = None
    if abs(total) < 0.01:  # <100bp/年，占比无意义
        reason = "SHORT_SHARE_DENOMINATOR_NEAR_ZERO"
    else:
        share = a_short / total
    residual = max(
        abs(float(s) - float(long_leg[i]) - float(short_leg[i]))
        for i, s in enumerate(spread)
    )
    return {
        "role": "diagnostic_only_not_a_criterion",
        "n_months": len(spread),
        "a_long_ann": a_long,
        "a_short_ann": a_short,
        "long_short_ann_arithmetic": float(_mean(spread)) * 12,
        "share_short": share,
        "share_short_unavailable_reason": reason,
        "monthly_identity_max_residual": residual,
        "note": (
            "拆腿占比对 long-only 判据**没有投票权**：决策变量是 a_long_ann 单独一个数。"
            "须防的反向误用是「空头腿只占 40%，说明多头腿也不错」——不成立，"
            "a_long_ann 是绝对值判据。★带符号占比 >100% 等价于多头腿 alpha 为负。"
        ),
    }


# --- 单调性 ---


def monotonicity(sections: Sequence[MonthlyCrossSection]) -> dict[str, object]:
    """字面判据（预注册，裁定用）+ 统计诊断（不改判据，只给材料）。

    ★B077 驼峰教训：极端组均值回归会让 top-bottom 同号而中间塌陷，
    **不得据 top-bottom 同号就称方向真实**。
    """
    names = [f"Q{index}" for index in range(1, N_QUANTILES + 1)]
    series = {name: [s.group_returns[name] for s in sections if name in s.group_returns]
              for name in names}
    annual = {name: geometric_annual(values) for name, values in series.items()}
    known = [annual[name] for name in names if annual[name] is not None]
    strictly_increasing = len(known) == N_QUANTILES and all(
        known[index] < known[index + 1] for index in range(len(known) - 1)
    )
    top = annual.get(TOP_GROUP)
    top_is_best = top is not None and all(
        top >= value for value in known if value is not None
    )

    # M1 斜率组合 t（功效远高于排序检验）
    slope: list[float] = []
    for section in sections:
        if not all(name in section.group_returns for name in names):
            continue
        slope.append(
            sum(
                weight * float(section.group_returns[name])
                for weight, name in zip(_SLOPE_WEIGHTS, names, strict=True)
            )
        )
    slope_sigma = _stdev(slope)
    slope_t = (
        (sum(slope) / len(slope)) / (slope_sigma / math.sqrt(len(slope)))
        if slope and slope_sigma
        else None
    )

    # M2 非反转带：Q5 显著输给某组才算真反转
    inversions: dict[str, object] = {}
    for name in names[:-1]:
        pairs = [
            s.group_returns[TOP_GROUP] - s.group_returns[name]
            for s in sections
            if TOP_GROUP in s.group_returns and name in s.group_returns
        ]
        if not pairs:
            continue
        se = annual_standard_error(pairs)
        mean_ann = float(_mean(pairs)) * 12
        inversions[name] = {
            "mean_ann": mean_ann,
            "se_ann": se,
            "significantly_inverted": se is not None and mean_ann < -se,
        }

    return {
        "group_annual_geometric": annual,
        # ★字面判据 = 预注册锁死的那一条，不因统计限制放宽
        "strictly_monotone_literal": strictly_increasing,
        "top_group_is_best_literal": top_is_best,
        # 以下只是材料，不改判据
        "slope_t_stat": slope_t,
        "slope_n_months": len(slope),
        "top_vs_group": inversions,
        "note": (
            "相邻五分位年化差的 SE 约 2.5%/年（组间相关 ρ≈0.95），字面单调性判据在"
            "统计上功效极低。字面结果与统计诊断必须并排呈现，由 Codex 裁定。"
        ),
    }


# --- 汇总 ---


def summarize(
    sections: Sequence[MonthlyCrossSection],
    *,
    label: str,
) -> dict[str, object]:
    """一个口径（主口径 / 对照组 / 某档 stub）下的全部统计。★不含任何裁定措辞。"""
    if not sections:
        return {"label": label, "n_months": 0}
    top = [s.group_returns[TOP_GROUP] for s in sections if TOP_GROUP in s.group_returns]
    scored = [s.benchmark_scored for s in sections]
    wide = [s.benchmark_wide for s in sections]
    excess_monthly = [
        s.group_returns[TOP_GROUP] - s.benchmark_scored
        for s in sections
        if TOP_GROUP in s.group_returns
    ]

    ann_top = geometric_annual(top)
    ann_scored = geometric_annual(scored)
    ann_wide = geometric_annual(wide)
    excess_scored = (
        ann_top - ann_scored if ann_top is not None and ann_scored is not None else None
    )
    excess_wide = ann_top - ann_wide if ann_top is not None and ann_wide is not None else None
    contamination = (
        ann_scored - ann_wide if ann_scored is not None and ann_wide is not None else None
    )
    se = annual_standard_error(excess_monthly)
    t_stat = excess_scored / se if excess_scored is not None and se else None

    ics = [s.ic for s in sections if s.ic is not None]
    ic_mean = sum(ics) / len(ics) if ics else None
    ic_sigma = _stdev(ics)

    return {
        "label": label,
        "n_months": len(sections),
        # D2：几何为裁定口径，算术并排
        "excess_ann_geometric_vs_scored": excess_scored,
        "excess_ann_geometric_vs_wide": excess_wide,
        "excess_ann_arithmetic_vs_scored": arithmetic_annual(excess_monthly),
        # ★D1：>1.0pp 时 spec §4 的 INCONCLUSIVE_COVERAGE_LIMITED 触发
        "coverage_composition_effect": contamination,
        "ann_top_geometric": ann_top,
        "ann_benchmark_scored_geometric": ann_scored,
        "ann_benchmark_wide_geometric": ann_wide,
        # ★统计功效：点估计必须与 SE / t / CI 一同出现
        "se_ann": se,
        "t_stat": t_stat,
        "ci95_ann": (
            [excess_scored - 1.96 * se, excess_scored + 1.96 * se]
            if excess_scored is not None and se
            else None
        ),
        "yearly_excess": yearly_excess(sections),
        # IC 是**辅助诊断，不作判据**（spec §2 冻结）
        "ic_mean": ic_mean,
        "ic_std": ic_sigma,
        "ic_ir": (ic_mean / ic_sigma) if ic_mean is not None and ic_sigma else None,
        "ic_role": "diagnostic_only_ic_high_with_flat_long_leg_is_not_inconclusive",
        "monotonicity": monotonicity(sections),
        "legs": leg_attribution(sections),
        "negative_overlay": {
            "months_with_negative_names": sum(
                1 for s in sections if s.negative_overlay_count
            ),
            "mean_count": (
                sum(s.negative_overlay_count for s in sections) / len(sections)
            ),
            "ann_geometric": geometric_annual(
                [
                    value
                    for s in sections
                    if (value := s.negative_overlay_return) is not None
                ]
            ),
        },
        "group_median_mv_last": sections[-1].group_median_mv,
        "delisted_later_by_group_total": _sum_by_group(sections),
        "honest_limits": HONEST_LIMITS,
    }


def _sum_by_group(sections: Sequence[MonthlyCrossSection]) -> dict[str, int]:
    out: dict[str, int] = {}
    for section in sections:
        for name, count in section.delisted_later_by_group.items():
            out[name] = out.get(name, 0) + count
    return dict(sorted(out.items()))


def yearly_excess(sections: Sequence[MonthlyCrossSection]) -> dict[str, object]:
    """分年超额（供「正超额年份 ≥60%」一档用）。

    ★12 × 0.6 = 7.2 → 需 **≥8 年**（7 年 = 58.3% < 60%）。
    ★纯噪声下 ``P(≥8/12) = 794/4096 = 19.4%``——这一档单独看有 19.4% 假阳性率，
    且与「年化 ≥3%」正相关，**不是独立确认**。
    """
    by_year: dict[str, list[Decimal]] = {}
    for section in sections:
        top = section.group_returns.get(TOP_GROUP)
        if top is None:
            continue
        by_year.setdefault(section.formation_date[:4], []).append(top - section.benchmark_scored)
    annual = {
        year: arithmetic_annual(values) for year, values in sorted(by_year.items())
    }
    positive = sum(1 for value in annual.values() if value is not None and value > 0)
    return {
        "by_year_arithmetic": annual,
        "n_years": len(annual),
        "n_positive_years": positive,
        "positive_fraction": positive / len(annual) if annual else 0.0,
        "null_hypothesis_note": (
            "纯噪声下 P(≥8/12 年为正) = 794/4096 = 19.4%；该档与年化档正相关，"
            "不构成独立确认。"
        ),
    }


#: ★spec §5：随任何统计产物一同呈现，不得剥离引用。
HONEST_LIMITS: tuple[str, ...] = (
    "无行业中性 / 规模中性（handoff §4.6 的 PIT 行业根本不存在）",
    "无停牌 / 涨跌停 / ST 可执行性检查（handoff G3b 未建）→ 有些「买入」实际买不到",
    "无交易成本、无冲击成本、无换手率约束",
    "无公司行动处置（handoff §4.7 未建）→ 退市证券最终现金去向以最后成交价近似",
    "不是 handoff 的 G5/G9 级 lineage 与连续面板",
    "★因此任何正向结果都是**上界**，不是可实现收益；结论只能用于"
    "「值不值得继续建地基」这一个决策，不得外推为收益预期。",
)


def observations_from_rows(
    rows: Iterable[Mapping[str, str]], *, stub: str
) -> dict[str, list[Observation]]:
    """把 F002 的明细 CSV 读成按形成日分组的观测。``stub`` 选 D6 的哪一档。"""
    by_date: dict[str, list[Observation]] = {}
    column = f"fwd_ret_stub_{stub}"
    for row in rows:
        raw_return = row.get(column, "")
        raw_ep = row.get("ep", "")
        if not raw_return or not raw_ep or raw_ep == "None":
            continue
        mv = row.get("total_mv_cny", "")
        by_date.setdefault(row["formation_date"], []).append(
            Observation(
                ts_code=row["ts_code"],
                formation_date=row["formation_date"],
                ep=Decimal(raw_ep),
                forward_return=Decimal(raw_return),
                delisted_later=row.get("delisted_later", "0") == "1",
                total_mv_cny=Decimal(mv) if mv else None,
            )
        )
    return by_date
