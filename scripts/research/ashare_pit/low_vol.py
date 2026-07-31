"""B111 F005 — A 股股票层低波 first-look 计算工具（纯逻辑，不联网）。

## ★★H7 硬边界：只算不裁

本模块**只产出原始统计**。产物中**不得出现**「GO」/「NO-GO」/「值得投入」/
「有 edge」一类结论性措辞——裁定权归 F007 的 Codex（铁律 #4）。复用 B110 的机器
判据（`test_ashare_pit_low_vol` 扫描产物 JSON 中的禁用词）。

## ★★B.0 诚实性声明：本方向**不是**干净的预注册

低波的点估计在起草 spec 前已被看到（席位产出）。因此：
- 已观测的点估计是**背景，不是证据**，不得作为「本方向成立」的依据。
- 判据的信息量在 **G1（排序滞后一月）/ G2（流动性）两个证伪**上——
  **执行前**那里答案未知（fix-round 时态修正：两硬门现已执行完毕）。
- 任何阈值**不由观测值反推**：0.90 σ 比来自复利拖累 ≈ σ²/2 的量级要求；
  1.0pp 沿用 B110 冻结的 NO-GO 线；11/12 年沿用 B110「分年」精神对风险声明加严。

## 无前视口径（严格）

排序变量 = 过去 12 个自然月的**月度收益已实现 σ**。形成日 t 只用 t-12…t-1 的
月度收益（G1 变体用 t-13…t-2，滞后一月）。月度收益序列由面板的
`fwd_ret_stub_0.00` 重建：某形成日 f 的 `fwd_ret_stub` 是 [f, f+1月] 的已实现收益，
故 f_i 处「过去 12 月已实现收益」= 形成日 f_{i-12}…f_{i-1} 的 `fwd_ret_stub`，
均在 f_i 之前实现 → 无前视。前向收益 = f_i 处的 `fwd_ret_stub`。
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from scripts.research.ashare_pit.signal_stats import HONEST_LIMITS

N_QUANTILES = 5
LOW_VOL_GROUP = "V1"  # σ 最低（低波组）
HIGH_VOL_GROUP = "V5"  # σ 最高
SIGMA_WINDOW = 12  # 过去 12 个自然月
NEWEY_WEST_LAG = 6
DEFAULT_BOOTSTRAP = 2000
DEFAULT_SEED = 20260721

#: §B.0 诚实性声明——原样进入产物（背景不作证据）。
#: fix-round 时态修正（finding F007-3）：硬门已执行，改历史时态，
#: 原 spec 的「尚未执行」指**执行前**的状态。
HONESTY_STATEMENT: str = (
    "本方向不是干净的预注册：下列点估计在起草 spec 前已被看到，"
    "故为背景不作证据；判据信息量在 G1（排序滞后一月）/ G2（流动性）"
    "两个证伪上——执行前那里答案未知。已观测数字不得作为本方向成立的依据。"
)

#: §B.5 诚实限制 = 沿用 B110 §5 + 本方向特有两条。
LOW_VOL_HONEST_LIMITS: tuple[str, ...] = (
    *HONEST_LIMITS,
    "★数据层可信度分层：B110 统计层已被两路零-import 独立复算逐位证实；"
    "但数据层（PIT total_mv 的 PIT 性、复权/退市终值构造、宇宙幸存者偏差）"
    "仍只有 B110 F004 单方证据且其半数检查已被证明无鉴别力。"
    "本方向建立在同一面板上，继承该不确定性。",
    "★窗口敏感性：B110 实测窗口杠杆（10.89pp）大于数据质量杠杆（2.05~3.96pp）。"
    "本方向窗口冻结 2013-01～2024-12 全区间；分段结果并排披露但不用于挑选。",
)


# --- 基础统计（scipy 未装，全部手写、可被独立复核）---


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: Sequence[float]) -> float | None:
    """样本标准差（ddof=1）。"""
    if len(values) < 2:
        return None
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def geometric_annual(returns: Sequence[float]) -> float | None:
    """``∏(1+r)^(12/n) − 1``（float 版；与 signal_stats.geometric_annual 数值等价，
    由 test_low_vol 交叉验证）。"""
    if not returns:
        return None
    growth = 1.0
    for value in returns:
        growth *= 1.0 + value
    if growth <= 0:
        return -1.0
    return float(growth ** (12.0 / len(returns)) - 1.0)


def arithmetic_annual(returns: Sequence[float]) -> float | None:
    if not returns:
        return None
    return _mean(returns) * 12.0


def annual_standard_error(monthly_excess: Sequence[float]) -> float | None:
    """年化超额标准误 = ``σ_月 × 12 / √n``。"""
    sigma = _stdev(monthly_excess)
    if sigma is None or not monthly_excess:
        return None
    return sigma * 12.0 / math.sqrt(len(monthly_excess))


def newey_west_tstat(monthly_excess: Sequence[float], *, lag: int = NEWEY_WEST_LAG) -> float | None:
    """月度超额均值的 Newey-West t（Bartlett 核，滞后 ``lag``）。

    NW 方差 = γ₀ + 2·Σ_{k=1}^{lag}(1 − k/(lag+1))·γ_k，t = mean / √(NW_var/n)。
    修正自相关；A 股月度收益的自相关会让朴素 t 失真，故并排给出。
    """
    n = len(monthly_excess)
    if n < 2:
        return None
    mean = _mean(monthly_excess)
    dev = [value - mean for value in monthly_excess]
    gamma0 = sum(d * d for d in dev) / n
    variance = gamma0
    for k in range(1, min(lag, n - 1) + 1):
        weight = 1.0 - k / (lag + 1)
        gamma_k = sum(dev[t] * dev[t - k] for t in range(k, n)) / n
        variance += 2.0 * weight * gamma_k
    if variance <= 0:
        return None
    se = math.sqrt(variance / n)
    return mean / se if se > 0 else None


def simple_tstat(monthly_excess: Sequence[float]) -> float | None:
    """朴素月度 t = mean / (σ/√n)（不修正自相关）。"""
    n = len(monthly_excess)
    if n < 2:
        return None
    sigma = _stdev(monthly_excess)
    if sigma is None or sigma == 0:
        return None
    return _mean(monthly_excess) / (sigma / math.sqrt(n))


# --- 面板 → 月度收益矩阵 → 无前视 σ ---


@dataclass(frozen=True)
class LowVolObservation:
    """一个 (证券 × 形成日) 观测：形成日已知的 σ 排序值 + 该形成日的前向收益。"""

    ts_code: str
    sigma: float
    forward_return: float


@dataclass(frozen=True)
class LowVolCrossSection:
    formation_date: str
    #: 组名 V1..V5 → 等权前向收益（V1 = σ 最低）
    group_returns: dict[str, float]
    group_counts: dict[str, int]
    #: B-scored 基准 = 进入五分位的名等权
    benchmark_scored: float
    n_scored: int
    #: B-wide 基准 = 该形成日**全部**有前向收益的名等权（不要求 σ 窗口；
    #: §B.1「同时出 B-wide 与二者之差」——fix-round 补齐）。
    benchmark_wide: float = 0.0
    n_wide: int = 0


def monthly_grid(rows: Iterable[Mapping[str, str]]) -> list[str]:
    """面板中的全部形成日（升序）——月度网格。"""
    return sorted({row["formation_date"] for row in rows})


def return_series(
    rows: Iterable[Mapping[str, str]], *, stub: str
) -> dict[str, dict[str, float]]:
    """``ts_code → {formation_date: fwd_ret_stub}``（只保留可解析的收益）。"""
    column = f"fwd_ret_stub_{stub}"
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        raw = row.get(column, "")
        if not raw or raw == "None":
            continue
        try:
            out[row["ts_code"]][row["formation_date"]] = float(raw)
        except ValueError:
            continue
    return out


def trailing_sigma(
    stock_series: Mapping[str, float],
    grid: Sequence[str],
    idx: int,
    *,
    window: int = SIGMA_WINDOW,
    lag: int = 0,
) -> float | None:
    """形成日 ``grid[idx]`` 的无前视 σ：网格 ``[idx-window-lag, idx-lag)`` 处的月度
    收益已实现 σ。任一月缺失即返回 None（要求完整窗口，严格无前视）。"""
    lo = idx - window - lag
    hi = idx - lag
    if lo < 0:
        return None
    values: list[float] = []
    for j in range(lo, hi):
        value = stock_series.get(grid[j])
        if value is None:
            return None
        values.append(value)
    return _stdev(values)


def assign_low_vol_quantiles(
    observations: Sequence[LowVolObservation], *, n_groups: int = N_QUANTILES
) -> dict[str, str]:
    """按 σ **升序**等数量切组：``V1`` = σ 最低，``V{n}`` = σ 最高。"""
    if len(observations) < n_groups:
        return {}
    ordered = sorted(observations, key=lambda item: item.sigma)
    total = len(ordered)
    out: dict[str, str] = {}
    for index, item in enumerate(ordered):
        bucket = min(index * n_groups // total, n_groups - 1)
        out[item.ts_code] = f"V{bucket + 1}"
    return out


def build_low_vol_section(
    formation_date: str,
    observations: Sequence[LowVolObservation],
    *,
    n_groups: int = N_QUANTILES,
    wide_returns: Sequence[float] | None = None,
) -> LowVolCrossSection | None:
    if len(observations) < n_groups:
        return None
    assignment = assign_low_vol_quantiles(observations, n_groups=n_groups)
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in observations:
        grouped[assignment[item.ts_code]].append(item.forward_return)
    wide = list(wide_returns) if wide_returns is not None else []
    return LowVolCrossSection(
        formation_date=formation_date,
        group_returns={name: _mean(rets) for name, rets in grouped.items()},
        group_counts={name: len(rets) for name, rets in grouped.items()},
        benchmark_scored=_mean([item.forward_return for item in observations]),
        n_scored=len(observations),
        benchmark_wide=_mean(wide) if wide else 0.0,
        n_wide=len(wide),
    )


def build_sections(
    rows: Sequence[Mapping[str, str]],
    *,
    stub: str,
    lag: int = 0,
    window: int = SIGMA_WINDOW,
    liquidity: Mapping[str, Mapping[str, float]] | None = None,
    liquidity_drop_fraction: float = 0.0,
) -> list[LowVolCrossSection]:
    """每个形成日的低波五分位截面。

    ``lag`` = σ 排序滞后月数（G1 用 1）。``liquidity`` = ``{formation_date:
    {ts_code: 日均成交额}}``；给定且 ``liquidity_drop_fraction>0`` 时，在排序**前**
    剔除该形成日流动性最低的一档（G2）。
    """
    series = return_series(rows, stub=stub)
    grid = monthly_grid(rows)
    sections: list[LowVolCrossSection] = []
    for idx, formation_date in enumerate(grid):
        observations: list[LowVolObservation] = []
        wide_returns: list[float] = []
        for ts_code, stock_series in series.items():
            forward = stock_series.get(formation_date)
            if forward is None:
                continue
            # B-wide：全部有前向收益的名（不要求 σ 窗口）。
            wide_returns.append(forward)
            sigma = trailing_sigma(stock_series, grid, idx, window=window, lag=lag)
            if sigma is None:
                continue
            observations.append(LowVolObservation(ts_code, sigma, forward))
        if liquidity is not None and liquidity_drop_fraction > 0.0:
            observations = _apply_liquidity_filter(
                observations, liquidity.get(formation_date, {}), liquidity_drop_fraction
            )
        section = build_low_vol_section(
            formation_date, observations, wide_returns=wide_returns
        )
        if section is not None:
            sections.append(section)
    return sections


def _apply_liquidity_filter(
    observations: Sequence[LowVolObservation],
    turnover_by_stock: Mapping[str, float],
    drop_fraction: float,
) -> list[LowVolObservation]:
    """剔除该形成日成交额最低的 ``drop_fraction`` 一档（G2）。无成交额数据的名一并剔除
    （无法判定流动性）。"""
    withliq = [
        (obs, turnover_by_stock[obs.ts_code])
        for obs in observations
        if obs.ts_code in turnover_by_stock
    ]
    if not withliq:
        return []
    withliq.sort(key=lambda pair: pair[1])
    cut = int(len(withliq) * drop_fraction)
    return [obs for obs, _ in withliq[cut:]]


# --- 已实现 σ 比（主判据的风险声明输入）---


def realized_sigma_ratio(sections: Sequence[LowVolCrossSection]) -> dict[str, object]:
    """V1 组合已实现 σ / 基准 σ（主判据风险声明），及分年成立情况。

    ★这是**投资组合层**已实现 σ（V1 月度收益时序的 σ），不是排序用的个股 σ。
    """
    v1 = [s.group_returns[LOW_VOL_GROUP] for s in sections if LOW_VOL_GROUP in s.group_returns]
    bench = [s.benchmark_scored for s in sections if LOW_VOL_GROUP in s.group_returns]
    sigma_v1 = _stdev(v1)
    sigma_bench = _stdev(bench)
    ratio = sigma_v1 / sigma_bench if sigma_v1 is not None and sigma_bench else None

    by_year_v1: dict[str, list[float]] = defaultdict(list)
    by_year_bench: dict[str, list[float]] = defaultdict(list)
    for section in sections:
        if LOW_VOL_GROUP not in section.group_returns:
            continue
        year = section.formation_date[:4]
        by_year_v1[year].append(section.group_returns[LOW_VOL_GROUP])
        by_year_bench[year].append(section.benchmark_scored)
    by_year: dict[str, object] = {}
    n_years_lower = 0
    for year in sorted(by_year_v1):
        sv = _stdev(by_year_v1[year])
        sb = _stdev(by_year_bench[year])
        lower = sv is not None and sb is not None and sv < sb
        by_year[year] = {"sigma_v1": sv, "sigma_benchmark": sb, "v1_lower": lower}
        if lower:
            n_years_lower += 1
    return {
        "sigma_v1": sigma_v1,
        "sigma_benchmark": sigma_bench,
        "sigma_ratio": ratio,
        "n_years": len(by_year),
        "n_years_v1_lower": n_years_lower,
        "by_year": by_year,
    }


# --- bootstrap ---


def bootstrap_geometric_excess(
    top: Sequence[float],
    benchmark: Sequence[float],
    *,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """对月度 (top, benchmark) 配对重采样，重算几何年化超额的 bootstrap 分布。

    保留月度配对（同月一起抽）以维持截面结构。返回 CI95 与 P(超额>0)。确定性（固定种子）。
    """
    if len(top) != len(benchmark) or len(top) < 2:
        return {"ci95": None, "p_positive": None, "n_boot": n_boot, "seed": seed}
    pairs = list(zip(top, benchmark, strict=True))
    rng = random.Random(seed)
    n = len(pairs)
    stats: list[float] = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        gt = geometric_annual([p[0] for p in sample])
        gb = geometric_annual([p[1] for p in sample])
        if gt is None or gb is None:
            continue
        stats.append(gt - gb)
    if not stats:
        return {"ci95": None, "p_positive": None, "n_boot": n_boot, "seed": seed}
    stats.sort()
    lo = stats[int(0.025 * len(stats))]
    hi = stats[min(int(0.975 * len(stats)), len(stats) - 1)]
    p_positive = sum(1 for s in stats if s > 0) / len(stats)
    return {
        "ci95": [lo, hi],
        "p_positive": p_positive,
        "n_boot": n_boot,
        "seed": seed,
        "n_effective": len(stats),
    }


# --- 汇总（★不含任何裁定措辞，H7）---


def _benchmark_wide_summary(sections: Sequence[LowVolCrossSection]) -> dict[str, object]:
    """B-wide（全市场等权）与 B-scored 的并排 + 差值（§B.1 fix-round 补齐）。

    B-wide 覆盖不要求 σ 窗口的全部名（含新上市/短历史名），B-scored 只含
    进入五分位的名；二者之差 = 可评宇宙的构成效应，必须并排披露。
    """
    wide = [s.benchmark_wide for s in sections]
    scored = [s.benchmark_scored for s in sections]
    ann_wide = geometric_annual(wide)
    ann_scored = geometric_annual(scored)
    n_wide_min = min((s.n_wide for s in sections), default=0)
    n_wide_max = max((s.n_wide for s in sections), default=0)
    return {
        "ann_benchmark_wide_geometric": ann_wide,
        "ann_benchmark_scored_geometric": ann_scored,
        "wide_minus_scored_pp": (
            (ann_wide - ann_scored) * 100.0
            if ann_wide is not None and ann_scored is not None
            else None
        ),
        "n_wide_min": n_wide_min,
        "n_wide_max": n_wide_max,
        "note": "B-wide=全市场等权（不要求 σ 窗口）；B-scored=进入五分位的名等权。",
    }


def summarize_low_vol(
    sections: Sequence[LowVolCrossSection], *, label: str
) -> dict[str, object]:
    """一个口径（主 / G1 / G2）下的全部低波统计。★只算不裁。"""
    if not sections:
        return {"label": label, "n_months": 0}
    top = [s.group_returns[LOW_VOL_GROUP] for s in sections if LOW_VOL_GROUP in s.group_returns]
    bench = [s.benchmark_scored for s in sections if LOW_VOL_GROUP in s.group_returns]
    excess_monthly = [t - b for t, b in zip(top, bench, strict=True)]

    ann_top = geometric_annual(top)
    ann_bench = geometric_annual(bench)
    excess_geo = (
        ann_top - ann_bench if ann_top is not None and ann_bench is not None else None
    )
    se = annual_standard_error(excess_monthly)
    ci95_analytical = (
        [excess_geo - 1.96 * se, excess_geo + 1.96 * se]
        if excess_geo is not None and se
        else None
    )
    sigma = realized_sigma_ratio(sections)
    bootstrap = bootstrap_geometric_excess(top, bench)

    # 五分位年化并排（含单调性材料，不作判据）
    group_series: dict[str, list[float]] = defaultdict(list)
    for section in sections:
        for name, value in section.group_returns.items():
            group_series[name].append(value)
    group_annual = {
        name: geometric_annual(values) for name, values in sorted(group_series.items())
    }

    return {
        "label": label,
        "n_months": len(sections),
        # 复利声明（副判据输入）
        "excess_ann_geometric_vs_scored": excess_geo,
        "ann_v1_geometric": ann_top,
        "ann_benchmark_scored_geometric": ann_bench,
        # ★B-wide 基准与二者之差（§B.1 fix-round 补齐）：B-wide = 全市场等权
        # （不要求 σ 窗口），差值 = 可评宇宙（B-scored）相对全市场的构成效应。
        "benchmark_wide": _benchmark_wide_summary(sections),
        "group_annual_geometric": group_annual,
        # ★算术并排 + t / NW-t / CI95（★强制披露，本方案不依赖它）
        "arithmetic_side_by_side": {
            "excess_ann_arithmetic": arithmetic_annual(excess_monthly),
            "monthly_excess_t_simple": simple_tstat(excess_monthly),
            "monthly_excess_t_newey_west_lag6": newey_west_tstat(excess_monthly),
            "se_ann": se,
            "ci95_ann_analytical": ci95_analytical,
            "role": "disclosed_not_relied_upon_this_design_does_not_depend_on_it",
        },
        # ★复利声明的 bootstrap（副判据：P(>0) ≥ 0.90 是阈值，此处只报数不裁）
        "bootstrap_geometric_excess": bootstrap,
        # ★风险声明（主判据输入：σ 比 ≤ 0.90 且 ≥11/12 年——阈值在此陈述，不在此裁定）
        "realized_sigma": sigma,
        # 判据阈值（陈述值，供 F007 裁定用；本模块不施加）
        "criterion_thresholds": {
            "main_risk_sigma_ratio_max": 0.90,
            "main_risk_years_required": 11,
            "main_risk_years_total": 12,
            "secondary_geometric_excess_min": 0.0,
            "secondary_bootstrap_p_positive_min": 0.90,
            "hard_gate_excess_min_pp": 1.0,
            "note": "阈值为陈述值，独立于观测；施加与裁定归 F007（H7）。",
        },
        "honest_limits": LOW_VOL_HONEST_LIMITS,
    }


# --- §B.1 可实施口径：N=100 只、半年调仓（fix-round 补齐）---

SEMIANNUAL_N = 100
SEMIANNUAL_HOLD_MONTHS = 6


def build_semiannual_n100(
    rows: Sequence[Mapping[str, str]],
    *,
    stub: str,
    sections: Sequence[LowVolCrossSection],
    top_n: int = SEMIANNUAL_N,
    hold_months: int = SEMIANNUAL_HOLD_MONTHS,
    window: int = SIGMA_WINDOW,
) -> dict[str, object]:
    """§B.1 冻结的可实施口径：σ 最低 N=100 名等权、半年调仓（fix-round 补齐）。

    冻结约定（先于看到结果）：
    - 调仓形成日 = 月度网格上每隔 6 个月一个，首个可评形成日（idx 12，σ 需
      12 个月 burn-in）起：idx 12, 18, 24, …。
    - 持有期收益 = 各持有名在持有窗内月度前向收益的复利；持有窗内**缺月按
      0.0 计入**并计入 ``n_missing_months`` 披露（退市终值已在面板 stub 内，
      停牌/缺数按平盘如实处理——H4 不静默 dropna）。
    - 只保留**完整** 6 个月持有窗；面板末的不完整窗丢弃并计入
      ``n_incomplete_windows_dropped``。
    - 基准 = 同一批持有窗上 **B-scored** 等权月度收益的复利（``sections``
      逐月基准，与主口径同源）。
    - 不建交易成本模型（§B.5 沿用：无交易成本（G2 之外）），只报毛收益。
    """
    series = return_series(rows, stub=stub)
    grid = monthly_grid(rows)
    bench_by_month = {section.formation_date: section.benchmark_scored for section in sections}
    windows: list[dict[str, object]] = []
    n_missing_months = 0
    n_incomplete = 0
    for idx in range(window, len(grid), hold_months):
        if idx + hold_months > len(grid):
            n_incomplete += 1
            continue
        month_keys = grid[idx : idx + hold_months]
        if any(month_key not in bench_by_month for month_key in month_keys):
            n_incomplete += 1
            continue
        # σ 排序（与主口径同一函数、同一无前视窗口）。
        ranked: list[tuple[str, float]] = []
        for ts_code, stock_series in series.items():
            sigma = trailing_sigma(stock_series, grid, idx, window=window, lag=0)
            if sigma is None:
                continue
            ranked.append((ts_code, sigma))
        ranked.sort(key=lambda pair: pair[1])
        held = ranked[:top_n]
        if not held:
            continue
        # 组合与基准的持有窗复利。
        held_growth: list[float] = []
        for ts_code, _sigma in held:
            stock_series = series[ts_code]
            growth = 1.0
            for month_key in month_keys:
                value = stock_series.get(month_key)
                if value is None:
                    n_missing_months += 1
                    value = 0.0
                growth *= 1.0 + value
            held_growth.append(growth - 1.0)
        port_ret = _mean(held_growth)
        bench_growth = 1.0
        for month_key in month_keys:
            bench_growth *= 1.0 + bench_by_month[month_key]
        bench_ret = bench_growth - 1.0
        windows.append(
            {
                "formation_date": grid[idx],
                "hold_months": len(month_keys),
                "n_held": len(held),
                "portfolio_window_return": port_ret,
                "benchmark_window_return": bench_ret,
                "excess_window": port_ret - bench_ret,
            }
        )

    total_months = sum(int(w["hold_months"]) for w in windows)
    port_series = [float(w["portfolio_window_return"]) for w in windows]
    bench_series = [float(w["benchmark_window_return"]) for w in windows]
    ann_port = geometric_annual_semiannual(port_series, total_months)
    ann_bench = geometric_annual_semiannual(bench_series, total_months)
    sigma_port = _stdev(port_series)
    sigma_bench = _stdev(bench_series)
    return {
        "label": f"n{top_n}_semiannual_stub_{stub}",
        "top_n": top_n,
        "hold_months": hold_months,
        "n_windows": len(windows),
        "total_months": total_months,
        "n_missing_months_in_windows": n_missing_months,
        "n_incomplete_windows_dropped": n_incomplete,
        "ann_portfolio_geometric": ann_port,
        "ann_benchmark_geometric": ann_bench,
        "excess_ann_geometric": (
            ann_port - ann_bench if ann_port is not None and ann_bench is not None else None
        ),
        "window_sigma_ratio": (
            sigma_port / sigma_bench
            if sigma_port is not None and sigma_bench is not None and sigma_bench > 0
            else None
        ),
        "windows": windows,
        "note": (
            "毛收益口径：无成本、无行业中性、无涨跌停可执行性（§B.5）；"
            "持有窗内缺月按 0.0 计入并已计数披露。"
        ),
    }


def geometric_annual_semiannual(
    window_returns: Sequence[float], total_months: int
) -> float | None:
    """持有窗收益序列的几何年化：``∏(1+w)^(12/total_months) − 1``。"""
    if not window_returns or total_months <= 0:
        return None
    growth = 1.0
    for value in window_returns:
        growth *= 1.0 + value
    if growth <= 0:
        return -1.0
    return float(growth ** (12.0 / total_months) - 1.0)


# --- §B.5 窗口敏感性：分段并排（fix-round 补齐；冻结分段，不用于挑选）---

#: 冻结分段（按可评年份 2014-2024 的 4/4/3 年三分，先于看到结果；§B.5 禁挑选）。
FROZEN_SEGMENTS: tuple[tuple[str, str, str], ...] = (
    ("2014-2017", "2014", "2017"),
    ("2018-2021", "2018", "2021"),
    ("2022-2024", "2022", "2024"),
)


def summarize_segments(
    sections: Sequence[LowVolCrossSection], *, label: str
) -> dict[str, object]:
    """把主口径 sections 按 FROZEN_SEGMENTS 切分，各段复用 summarize_low_vol
    全套统计并排披露（§B.5：分段结果不得用于挑选窗口）。"""
    segments: dict[str, object] = {}
    for name, start_year, end_year in FROZEN_SEGMENTS:
        sub = [
            section
            for section in sections
            if start_year <= section.formation_date[:4] <= end_year
        ]
        segments[name] = summarize_low_vol(sub, label=f"{label}__{name}")
    return {
        "label": f"{label}__segments",
        "frozen_segments": [name for name, _, _ in FROZEN_SEGMENTS],
        "note": "分段为冻结披露（4/4/3 年三分），不得用于挑选窗口（§B.5）。",
        "segments": segments,
    }
