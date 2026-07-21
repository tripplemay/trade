"""B110 F003 — 信号统计计算工具的单元测试（离线，不联网）。

被测性质：

1. ★★**拆腿归因的算术**（本批次最重要的一段）。B103-B105 的教训是 IC ~0.15 看着很好，
   但**纸面收益的 90-107% 落在 A 股不可做空的短腿上**。含一个「全部收益来自空头腿」
   的极端 fixture —— 带符号占比必须能报出 >100%，即多头腿 alpha 为负。
2. ★**单调性**（B077 驼峰教训）：top-bottom 同号 **不等于** 方向真实。
3. ★**负 E/P 参与排序**（spec §3.4 + 附录 D3），实现层不得有任何符号过滤。
4. ★★**H7 硬边界**：产物中不得出现 GO / NO-GO / 值得投入 / 有 edge 一类结论性措辞。
   这一条用机器判据锁住，而不是靠人自觉。
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from scripts.research.ashare_pit.signal_stats import (
    HONEST_LIMITS,
    MonthlyCrossSection,
    Observation,
    arithmetic_annual,
    assign_quantiles,
    build_cross_section,
    geometric_annual,
    leg_attribution,
    monotonicity,
    observations_from_rows,
    spearman,
    summarize,
    yearly_excess,
)

# --- 构造辅助 ---


def _obs(code: str, ep: str, ret: str, *, mv: str | None = None) -> Observation:
    return Observation(
        ts_code=code,
        formation_date="20240630",
        ep=Decimal(ep),
        forward_return=Decimal(ret),
        total_mv_cny=Decimal(mv) if mv else None,
    )


def _section(
    date: str, groups: dict[str, str], benchmark: str, *, wide: str | None = None
) -> MonthlyCrossSection:
    return MonthlyCrossSection(
        formation_date=date,
        group_returns={name: Decimal(value) for name, value in groups.items()},
        group_counts=dict.fromkeys(groups, 100),
        benchmark_scored=Decimal(benchmark),
        benchmark_wide=Decimal(wide if wide is not None else benchmark),
        ic=0.05,
        n_scored=500,
        n_wide=500,
    )


def _flat_series(
    top: str, bottom: str, benchmark: str, *, months: int = 24
) -> list[MonthlyCrossSection]:
    return [
        _section(
            f"20{13 + index // 12:02d}{index % 12 + 1:02d}28",
            {"Q1": bottom, "Q2": benchmark, "Q3": benchmark, "Q4": benchmark, "Q5": top},
            benchmark,
        )
        for index in range(months)
    ]


# --- Spearman ---


def test_spearman_is_one_for_a_perfectly_increasing_pair() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == pytest.approx(1.0)


def test_spearman_is_minus_one_for_a_perfectly_decreasing_pair() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == pytest.approx(-1.0)


def test_spearman_uses_average_ranks_for_ties() -> None:
    """★A 股涨跌停会造成大量并列；不用平均秩会让相关系数系统性偏移。"""
    assert spearman([1.0, 1.0, 2.0, 3.0], [1.0, 1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_spearman_returns_none_rather_than_a_fake_zero_on_thin_samples() -> None:
    assert spearman([1.0], [2.0]) is None
    assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None


# --- 年化 ---


def test_geometric_and_arithmetic_annualization_differ_as_expected() -> None:
    """★D2 冻结几何为裁定口径。高波动下算术版系统性偏高（方差拖累被忽略）。"""
    volatile = [Decimal("0.5"), Decimal("-0.3")] * 6
    arithmetic = arithmetic_annual(volatile)
    geometric = geometric_annual(volatile)
    assert arithmetic == pytest.approx(1.2)
    # (1.5 × 0.7)^6 − 1 ≈ 0.34 —— 方差拖累让几何值只有算术值的三分之一不到
    assert geometric is not None and geometric < arithmetic / 2


def test_geometric_annualization_of_a_flat_series_is_flat() -> None:
    assert geometric_annual([Decimal("0")] * 12) == pytest.approx(0.0)


# --- ★负 E/P 参与排序 ---


def test_negative_ep_names_take_part_in_the_ranking_and_land_at_the_bottom() -> None:
    """★spec §3.4 主口径不剔除。任何符号过滤都会架空「双口径」设计。"""
    observations = [
        _obs("A", "0.20", "0.01"),
        _obs("B", "0.10", "0.01"),
        _obs("C", "0.05", "0.01"),
        _obs("D", "0.01", "0.01"),
        _obs("E", "-0.30", "0.01"),
    ]
    assignment = assign_quantiles(observations)
    assert assignment["A"] == "Q5"
    assert assignment["E"] == "Q1"
    assert len(assignment) == 5


def test_a_cross_section_reports_the_negative_overlay_separately() -> None:
    """D3：负 E/P 名**既**参与排序**又**作为 overlay 单独出收益。"""
    observations = [
        _obs("A", "0.20", "0.05"),
        _obs("B", "0.10", "0.02"),
        _obs("C", "0.05", "0.00"),
        _obs("D", "0.01", "-0.01"),
        _obs("E", "-0.30", "-0.10"),
    ]
    section = build_cross_section("20240630", observations)
    assert section is not None
    assert section.negative_overlay_count == 1
    assert section.negative_overlay_return == Decimal("-0.10")
    # 同时 E 仍在 Q1 里
    assert section.group_counts["Q1"] == 1


# --- ★★拆腿归因 ---


def test_leg_identity_holds_exactly_on_monthly_arithmetic_returns() -> None:
    sections = _flat_series("0.02", "-0.01", "0.005")
    result = leg_attribution(sections)
    assert result["monthly_identity_max_residual"] == pytest.approx(0.0, abs=1e-12)


def test_all_of_the_paper_edge_sitting_in_the_short_leg_is_reported_as_over_100_percent() -> None:
    """★★B103-B105 的实质结论：多头腿 alpha 为负 → 带符号占比 >100%。

    多头腿 −0.5%/年、空头腿 +8.0%/年 → 8.0/7.5 = 106.7%。
    ★若用绝对值占比 8.0/8.5 = 94.1%，永远 ≤100%，**永远看不出多头腿是负的**，
    会被读成「多头也有一点贡献」——那正是当年差点得出的相反结论。
    """
    # 基准 0；顶层 −0.5%/年 → 每月 −0.000416667；底层 −8.0%/年 → 每月 −0.00666667
    sections = [
        _section(
            f"2013{index % 12 + 1:02d}28",
            {
                "Q1": "-0.0066666666666667",
                "Q2": "0",
                "Q3": "0",
                "Q4": "0",
                "Q5": "-0.0004166666666667",
            },
            "0",
        )
        for index in range(12)
    ]
    result = leg_attribution(sections)
    assert result["a_long_ann"] == pytest.approx(-0.005, abs=1e-6)
    assert result["a_short_ann"] == pytest.approx(0.08, abs=1e-6)
    share = result["share_short"]
    assert share is not None and share == pytest.approx(1.0667, abs=1e-3)
    assert share > 1.0


def test_a_near_zero_long_short_denominator_suppresses_the_share_instead_of_exploding() -> None:
    """两腿几乎抵消时占比无意义 —— 报 None + 原因码，不报一个爆炸的数。"""
    sections = _flat_series("0.0001", "0.0001", "0.0001")
    result = leg_attribution(sections)
    assert result["share_short"] is None
    assert result["share_short_unavailable_reason"] == "SHORT_SHARE_DENOMINATOR_NEAR_ZERO"


def test_leg_attribution_is_labelled_as_diagnostic_only() -> None:
    """★占比对 long-only 裁定没有投票权，决策变量是 a_long_ann 单独一个数。"""
    result = leg_attribution(_flat_series("0.02", "-0.01", "0.005"))
    assert result["role"] == "diagnostic_only_not_a_criterion"


# --- ★单调性（B077 驼峰）---


def test_a_humped_profile_is_not_reported_as_monotone_even_though_top_beats_bottom() -> None:
    """★B077 教训：极端组均值回归会造成驼峰。top-bottom 同号 ≠ 方向真实。"""
    sections = [
        _section(
            f"2013{index % 12 + 1:02d}28",
            {"Q1": "-0.01", "Q2": "0.03", "Q3": "0.04", "Q4": "0.02", "Q5": "0.01"},
            "0.0",
        )
        for index in range(12)
    ]
    result = monotonicity(sections)
    assert result["strictly_monotone_literal"] is False
    assert result["top_group_is_best_literal"] is False


def test_a_genuinely_increasing_profile_passes_the_literal_criterion() -> None:
    # 逐月加一点噪声：全同的序列方差为 0，斜率 t 按定义无法定义（此时返回 None 是对的）
    sections = [
        _section(
            f"2013{index % 12 + 1:02d}28",
            {
                "Q1": f"{-0.01 + index * 0.001:.4f}",
                "Q2": f"{0.00 + index * 0.001:.4f}",
                "Q3": f"{0.01 + index * 0.001:.4f}",
                "Q4": f"{0.02 + index * 0.001:.4f}",
                "Q5": f"{0.03 + index * 0.001:.4f}",
            },
            "0.01",
        )
        for index in range(12)
    ]
    result = monotonicity(sections)
    assert result["strictly_monotone_literal"] is True
    assert result["top_group_is_best_literal"] is True
    assert result["slope_t_stat"] is not None


def test_monotonicity_reports_standard_errors_alongside_the_literal_verdict() -> None:
    """★相邻组年化差 SE ≈ 2.5%/年。字面判据不放宽，但 SE 必须并排出现。"""
    result = monotonicity(_flat_series("0.02", "-0.01", "0.005"))
    assert "top_vs_group" in result
    assert all("se_ann" in value for value in result["top_vs_group"].values())  # type: ignore[union-attr]


# --- 分年与统计功效 ---


def test_yearly_excess_counts_positive_years_and_states_the_null_rate() -> None:
    sections = _flat_series("0.02", "-0.01", "0.005", months=24)
    result = yearly_excess(sections)
    assert result["n_years"] == 2
    assert result["n_positive_years"] == 2
    assert "19.4%" in str(result["null_hypothesis_note"])


def test_the_point_estimate_never_appears_without_its_standard_error() -> None:
    """★3.0% 的点估计对应 t ≈ 2.0，95% CI 横跨三档全部。缺 SE 会被读成「证明了」。"""
    result = summarize(_flat_series("0.02", "-0.01", "0.005"), label="main")
    assert result["excess_ann_geometric_vs_scored"] is not None
    assert result["se_ann"] is not None
    assert result["t_stat"] is not None
    assert result["ci95_ann"] is not None


def test_the_coverage_composition_effect_is_always_reported() -> None:
    """★D1：B-scored 与 B-wide 之差 >1.0pp 时 spec §4 的 INCONCLUSIVE 档触发。"""
    sections = [
        _section(
            f"2013{index % 12 + 1:02d}28",
            {"Q1": "0.0", "Q2": "0.0", "Q3": "0.0", "Q4": "0.0", "Q5": "0.01"},
            "0.005",
            wide="0.003",
        )
        for index in range(12)
    ]
    result = summarize(sections, label="main")
    effect = result["coverage_composition_effect"]
    assert effect is not None and effect > 0


def test_honest_limits_ride_along_with_every_summary() -> None:
    """★spec §5：诚实限制不得从统计产物上剥离。"""
    result = summarize(_flat_series("0.02", "-0.01", "0.005"), label="main")
    assert result["honest_limits"] == HONEST_LIMITS
    assert any("上界" in item for item in HONEST_LIMITS)


# --- ★★H7：机器判据锁住「不下裁定」 ---

_FORBIDDEN = (
    "GO",
    "NO-GO",
    "NOGO",
    "值得投入",
    "有 edge",
    "有edge",
    "建议投入",
    "应当继续",
    "结论是",
)


def test_the_output_contains_no_verdict_language_anywhere() -> None:
    """★★H7 硬边界：Generator 只算不裁，裁定权归 F004 的 Codex（铁律 #4）。

    用机器判据锁住而不是靠自觉 —— first-look 的产出是一个决定大额工程投入的开关，
    实施方下裁定等于自己批准自己的后续工作。
    """
    payload = json.dumps(
        summarize(_flat_series("0.02", "-0.01", "0.005"), label="main"),
        ensure_ascii=False,
        default=str,
    )
    for word in _FORBIDDEN:
        assert word not in payload, f"产物中出现了结论性措辞: {word}"


def test_ic_is_labelled_as_diagnostic_not_a_criterion() -> None:
    """spec §2 冻结：IC 高而多头腿无超额 = NO-GO 而非 INCONCLUSIVE —— 故 IC 不作判据。"""
    result = summarize(_flat_series("0.02", "-0.01", "0.005"), label="main")
    assert "diagnostic_only" in str(result["ic_role"])


# --- 明细读取 ---


def test_observations_are_grouped_by_formation_date_per_stub() -> None:
    rows = [
        {
            "ts_code": "A",
            "formation_date": "20240131",
            "ep": "0.1",
            "fwd_ret_stub_0.00": "0.02",
            "fwd_ret_stub_-0.30": "0.02",
            "delisted_later": "0",
            "total_mv_cny": "1000",
        },
        {
            "ts_code": "B",
            "formation_date": "20240131",
            "ep": "-0.05",
            "fwd_ret_stub_0.00": "-0.6",
            "fwd_ret_stub_-0.30": "-0.72",
            "delisted_later": "1",
            "total_mv_cny": "500",
        },
    ]
    base = observations_from_rows(rows, stub="0.00")
    stressed = observations_from_rows(rows, stub="-0.30")
    assert base["20240131"][1].forward_return == Decimal("-0.6")
    assert stressed["20240131"][1].forward_return == Decimal("-0.72")
    assert stressed["20240131"][1].delisted_later is True


def test_rows_without_a_return_for_the_chosen_stub_are_skipped_not_defaulted() -> None:
    rows = [{"ts_code": "A", "formation_date": "20240131", "ep": "0.1", "fwd_ret_stub_0.00": ""}]
    assert observations_from_rows(rows, stub="0.00") == {}
