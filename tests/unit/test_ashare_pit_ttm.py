"""B110 F001 — PIT TTM 归母净利润的单元测试（离线，不联网）。

被测性质（spec `docs/specs/B110-pure-ep-first-look-spec.md` §3.1 + handoff §6）：

1. **唯一算法**：``SQ1=C_Q1 / SQ2=C_H1-C_Q1 / SQ3=C_Q3-C_H1 / SQ4=C_FY-C_Q3``，
   TTM = 最近连续四个单季之和。
2. ★**四个分量各自独立 as-of**：同一 ``formation_date`` 对每个累计期**重新解析**，
   禁止混用不同知识截止日——混用是最隐蔽的前视形态。
3. **等价式交叉验证** ``FY(y-1) + YTD(y) - YTD(y-1)``；两式不一致 → 失败码，
   **禁止取其一**（与 B109 ``FACT_VERSION_AMBIGUOUS`` 同纪律）。
4. **结构化失败码**：财年变更 / IPO 历史不足 / 分量不可解析 → ``value is None`` + 原因码。
   ★**禁止**用最新年报、线性插值、季度年化填补。
5. ★**负单季是有效经济事实**（单季亏损），绝不能被当作数据错误置空——
   spec §3.4 明确要求负 TTM 单独成组而**不剔除**，一旦这里静默置空，
   整个「双口径」设计就失效了。
6. **全程 Decimal**，不在中途转浮点。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.research.ashare_pit import ttm as ttm_module
from scripts.research.ashare_pit.codes import FactStatus, FactVersion
from scripts.research.ashare_pit.ttm import (
    FORMULA_VERSION,
    STANDARD_QUARTER_ENDS,
    CumulativeFact,
    TTMResult,
    TTMStatus,
    component_lineage,
    compute_ttm,
    periods_required_for,
    quarter_window,
)

# --- 构造辅助（沿用 B109 测试的 `_` 前缀 + 关键字可选参数约定）---


def _version(
    value: str,
    *,
    f_ann: str = "20230420",
    ts_code: str = "000001.SZ",
    end_date: str = "20230331",
    ann: str = "20230420",
    flag: str = "1",
) -> FactVersion:
    return FactVersion(
        ts_code=ts_code,
        end_date=end_date,
        f_ann_date=f_ann,
        ann_date=ann,
        update_flag=flag,
        value=Decimal(value),
    )


def _cumulative(
    period: str, value: str, *, f_ann: str | None = None, ts_code: str = "000001.SZ"
) -> tuple[str, list[FactVersion]]:
    """一个累计期的版本列表。``f_ann`` 默认取该期末后 20 天，保证形成日可见。"""
    announced = f_ann if f_ann is not None else _plus_days(period, 20)
    return period, [_version(value, f_ann=announced, end_date=period, ts_code=ts_code)]


def _plus_days(yyyymmdd: str, days: int) -> str:
    from datetime import date, timedelta

    base = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    return (base + timedelta(days=days)).strftime("%Y%m%d")


def _panel(*entries: tuple[str, list[FactVersion]]) -> dict[str, list[FactVersion]]:
    return dict(entries)


def _full_year_panel(
    year: int, q1: str, h1: str, q3: str, fy: str, *, ts_code: str = "000001.SZ"
) -> dict[str, list[FactVersion]]:
    return _panel(
        _cumulative(f"{year}0331", q1, ts_code=ts_code),
        _cumulative(f"{year}0630", h1, ts_code=ts_code),
        _cumulative(f"{year}0930", q3, ts_code=ts_code),
        _cumulative(f"{year}1231", fy, ts_code=ts_code),
    )


# --- 报告期窗口算术 ---


def test_standard_quarter_ends_are_the_four_calendar_quarters() -> None:
    assert STANDARD_QUARTER_ENDS == ("0331", "0630", "0930", "1231")


def test_quarter_window_at_a_fiscal_year_anchor_is_the_four_quarters_of_that_year() -> None:
    """锚点是年报时，最近四个单季就是该年的 SQ1..SQ4。"""
    assert quarter_window("20231231") == (
        (2023, 4),
        (2023, 3),
        (2023, 2),
        (2023, 1),
    )


def test_quarter_window_at_a_q1_anchor_wraps_into_the_previous_year() -> None:
    """锚点是一季报时，四个单季跨年：SQ1(y) + SQ4/SQ3/SQ2(y-1)。"""
    assert quarter_window("20230331") == (
        (2023, 1),
        (2022, 4),
        (2022, 3),
        (2022, 2),
    )


def test_periods_required_for_q1_anchor_covers_five_cumulative_reports() -> None:
    """★路径 A 严格需要比等价式更多的事实——这正是「不得取其一」的操作含义。"""
    assert periods_required_for("20230331") == (
        "20220331",
        "20220630",
        "20220930",
        "20221231",
        "20230331",
    )


def test_periods_required_for_fy_anchor_is_that_year_only() -> None:
    assert periods_required_for("20231231") == (
        "20230331",
        "20230630",
        "20230930",
        "20231231",
    )


# --- 唯一算法：单季差分与求和 ---


def test_fy_anchor_ttm_equals_the_annual_cumulative_profit() -> None:
    """SQ1+SQ2+SQ3+SQ4 望远镜求和 = C_FY。"""
    panel = _full_year_panel(2023, "100", "250", "400", "600")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    assert result.status is TTMStatus.RESOLVED
    assert result.value == Decimal("600")
    assert result.anchor_end_date == "20231231"


def test_single_quarter_components_are_the_cumulative_differences() -> None:
    panel = _full_year_panel(2023, "100", "250", "400", "600")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    by_role = {item.role: item.value for item in result.components}
    assert by_role == {
        "SQ1": Decimal("100"),
        "SQ2": Decimal("150"),
        "SQ3": Decimal("150"),
        "SQ4": Decimal("200"),
    }


def test_q3_anchor_ttm_spans_two_fiscal_years() -> None:
    """锚点 2023Q3：TTM = SQ1(23)+SQ2(23)+SQ3(23) + SQ4(22)。"""
    panel = {
        **_full_year_panel(2022, "80", "200", "320", "500"),
        **_panel(
            _cumulative("20230331", "100"),
            _cumulative("20230630", "250"),
            _cumulative("20230930", "400"),
        ),
    }
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20231130",
        versions_by_period=panel,
        lookback_periods=("20230930", "20230630", "20230331", "20221231", "20220930"),
    )
    assert result.status is TTMStatus.RESOLVED
    # SQ4(2022) = 500 - 320 = 180；SQ1..SQ3(2023) 累计 400 → 580
    assert result.value == Decimal("580")


def test_a_loss_making_quarter_is_kept_as_a_valid_economic_fact() -> None:
    """★单季亏损（累计值回落）不是数据错误，绝不能置空。

    一旦这里 fail-closed，spec §3.4「负 TTM 主口径不剔除」就被实现层架空了——
    B103-B105 的教训是：静默剔除某一类样本会系统性改变结论。
    """
    panel = _full_year_panel(2023, "100", "60", "40", "-50")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    assert result.status is TTMStatus.RESOLVED
    assert result.value == Decimal("-50")
    by_role = {item.role: item.value for item in result.components}
    assert by_role["SQ2"] == Decimal("-40")
    assert by_role["SQ4"] == Decimal("-90")


def test_values_stay_decimal_and_never_become_float() -> None:
    """全程 Decimal：0.1+0.2 类误差在分组边界上会改变分位归属。"""
    panel = _full_year_panel(2023, "0.1", "0.3", "0.6", "1.0")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    assert isinstance(result.value, Decimal)
    assert result.value == Decimal("1.0")
    assert all(isinstance(item.value, Decimal) for item in result.components)


# --- ★四分量各自独立 as-of ---


def test_each_component_is_resolved_independently_at_the_same_formation_date() -> None:
    """★年报已修订但修订版在形成日之后可见时，必须取**当时**那一版。

    这是 PIT 的核心：用今天的年报回填 2023 年的 TTM = 前视。
    """
    panel = _panel(
        _cumulative("20230331", "100"),
        _cumulative("20230630", "250"),
        _cumulative("20230930", "400"),
        (
            "20231231",
            [
                _version("600", f_ann="20240328", end_date="20231231", flag="0"),
                # 修订版 2025 年才可见——形成日 2024-06-30 看不到
                _version("550", f_ann="20250415", end_date="20231231", flag="1"),
            ],
        ),
    )
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    assert result.status is TTMStatus.RESOLVED
    assert result.value == Decimal("600")
    # ★后续存在更新版本这一事实本身必须留痕（B109 `superseded_later`）
    assert result.superseded_later is True


def test_a_component_not_yet_published_at_formation_date_fails_closed() -> None:
    """分量在形成日尚未披露 → null + 原因码，**不得**用更早/更晚的期次顶替。"""
    panel = _panel(
        _cumulative("20230331", "100"),
        _cumulative("20230630", "250"),
        _cumulative("20230930", "400"),
        _cumulative("20231231", "600", f_ann="20240328"),
    )
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240131",  # 年报尚未披露，但锚点会落到 2023Q3
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    # 锚点退到 Q3 后，SQ4(2022) 需要 2022 年的期次，而 panel 里没有 → 失败
    assert result.value is None
    assert result.status is not TTMStatus.RESOLVED


def test_an_ambiguous_anchor_fails_closed_instead_of_silently_using_an_older_period() -> None:
    """★同一 ``f_ann_date`` 两个不同值 → B109 判定 ``FACT_VERSION_AMBIGUOUS``。

    此时**不得**退到更早的期次假装成功——静默降级正是错值来源。
    """
    panel = {
        **_full_year_panel(2022, "80", "200", "320", "500"),
        "20231231": [
            _version("600", f_ann="20240328", end_date="20231231"),
            _version("900", f_ann="20240328", end_date="20231231"),
        ],
        **_panel(
            _cumulative("20230331", "100"),
            _cumulative("20230630", "250"),
            _cumulative("20230930", "400"),
        ),
    }
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331", "20221231"),
    )
    assert result.status is TTMStatus.ANCHOR_AMBIGUOUS
    assert result.value is None
    assert result.anchor_end_date == "20231231"


# --- 结构化失败码 ---


def test_no_visible_report_at_all_is_its_own_status() -> None:
    panel = _panel(_cumulative("20231231", "600", f_ann="20240328"))
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20230630",
        versions_by_period=panel,
        lookback_periods=("20231231",),
    )
    assert result.status is TTMStatus.NO_VISIBLE_REPORT
    assert result.value is None


def test_missing_history_for_a_newly_listed_company_is_insufficient_history() -> None:
    """★IPO 历史不足四个连续单季 → 专有原因码，**禁止**季度年化填补。"""
    panel = _panel(_cumulative("20230331", "100"))
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20230630",
        versions_by_period=panel,
        lookback_periods=("20230331", "20221231", "20220930", "20220630", "20220331"),
    )
    assert result.status is TTMStatus.INSUFFICIENT_HISTORY
    assert result.value is None
    assert "20221231" in " ".join(result.failures)


def test_a_period_never_fetched_is_a_coverage_defect_not_a_data_fact() -> None:
    """★「没拉过这一期」与「公司没披露这一期」必须区分开。

    前者是我们的覆盖缺陷（H4：不得静默 dropna），后者是真实的历史不足。
    把前者算作后者，会把抓取 bug 伪装成数据特征。
    """
    panel = _panel(_cumulative("20230331", "100"))
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20230630",
        versions_by_period=panel,
        lookback_periods=("20230331",),  # 更早的期次根本没进 lookback
    )
    assert result.status is TTMStatus.PERIOD_NOT_FETCHED
    assert result.value is None


def test_a_non_calendar_fiscal_year_end_is_rejected_with_its_own_code() -> None:
    """财年变更 → null + 原因码（handoff §6 明令，不得用最新年报顶替）。"""
    panel = _full_year_panel(2023, "100", "250", "400", "600")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
        fiscal_year_end="0630",
    )
    assert result.status is TTMStatus.FISCAL_CALENDAR_IRREGULAR
    assert result.value is None


# --- 等价式交叉验证 ---


def test_equivalence_value_is_computed_alongside_the_single_quarter_sum() -> None:
    """等价式 ``FY(y-1) + YTD(y) - YTD(y-1)`` 必须被真的算出来并留痕。"""
    panel = {
        **_full_year_panel(2022, "80", "200", "320", "500"),
        **_panel(
            _cumulative("20230331", "100"),
            _cumulative("20230630", "250"),
            _cumulative("20230930", "400"),
        ),
    }
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20231130",
        versions_by_period=panel,
        lookback_periods=("20230930", "20230630", "20230331", "20221231", "20220930"),
    )
    # FY(2022) 500 + YTD_Q3(2023) 400 - YTD_Q3(2022) 320 = 580
    assert result.equivalence_value == Decimal("580")
    assert result.value == result.equivalence_value


def test_equivalence_mismatch_fails_closed_and_never_picks_a_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """★两式不一致 → 失败码，``value is None``。禁止「取其一」。

    只能靠打桩触发：见下一条测试——两式在精确算术下恒等，数据构造不出不一致。
    这个分支是**防实现 bug 的守卫**，必须存在且必须 fail-closed。
    """
    panel = {
        **_full_year_panel(2022, "80", "200", "320", "500"),
        **_panel(
            _cumulative("20230331", "100"),
            _cumulative("20230630", "250"),
            _cumulative("20230930", "400"),
        ),
    }
    monkeypatch.setattr(
        ttm_module, "sum_single_quarters", lambda components: Decimal("999")
    )
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20231130",
        versions_by_period=panel,
        lookback_periods=("20230930", "20230630", "20230331", "20221231", "20220930"),
    )
    assert result.status is TTMStatus.EQUIVALENCE_MISMATCH
    assert result.value is None
    assert result.equivalence_value == Decimal("580")


def test_the_two_paths_are_algebraically_identical_by_construction() -> None:
    """★★诚实结论：等价式在精确算术下**恒等**于单季求和，不是对数据的独立验证。

    路径 A 的中间累计值全部望远镜相消，展开后逐项等于路径 B。下面对四个锚点、
    多组任意数值（含负值、小数）穷举验证这一点。

    ★因此**禁止**把这项检查转述为「数据已交叉验证」——那是自欺，同型于 B109
    审计器「可裁定样本仅 16.7% 而一致率 100%」。真正的数据校验需要外部真值锚。
    """
    samples = [
        ("80", "200", "320", "500", "100", "250", "400", "600"),
        ("-10", "-30", "5", "-2", "0.1", "-0.4", "0.25", "3.75"),
        ("1000", "1000", "1000", "1000", "-1", "-2", "-3", "-4"),
    ]
    anchors = ("20230331", "20230630", "20230930", "20231231")
    for prior in samples:
        p1, p2, p3, p4, c1, c2, c3, c4 = prior
        panel = {
            **_full_year_panel(2022, p1, p2, p3, p4),
            **_full_year_panel(2023, c1, c2, c3, c4),
        }
        lookback = tuple(
            f"{year}{end}" for year in (2022, 2023) for end in STANDARD_QUARTER_ENDS
        )
        for anchor in anchors:
            result = compute_ttm(
                ts_code="000001.SZ",
                formation_date=_plus_days(anchor, 25),
                versions_by_period=panel,
                lookback_periods=lookback,
            )
            assert result.status is TTMStatus.RESOLVED, (anchor, result.failures)
            assert result.anchor_end_date == anchor
            assert result.value == result.equivalence_value


# --- ★lineage：四分量各自的版本与风险，不得混合平均 ---


def test_lineage_records_each_component_with_its_own_fact_versions() -> None:
    panel = _full_year_panel(2023, "100", "250", "400", "600")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    rows = component_lineage(result)
    assert {row["component_role"] for row in rows} == {"SQ1", "SQ2", "SQ3", "SQ4"}
    for row in rows:
        assert row["feature_id"] == "000001.SZ|20240630"
        assert row["formula_version"] == FORMULA_VERSION
        assert row["source_f_ann_dates"]


def test_lineage_exposes_per_component_revision_risk_not_a_blended_average() -> None:
    """★B109 实测 FY 分量修订率是 Q1 的 10.2 倍（0.747% vs 0.073%）。

    SQ4 = C_FY - C_Q3 直接吃 FY 的风险；SQ1 只吃 Q1 的。用混合平均披露会把
    「风险集中在一个分量上」这个最重要的结论抹平。
    """
    panel = _full_year_panel(2023, "100", "250", "400", "600")
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20240630",
        versions_by_period=panel,
        lookback_periods=("20231231", "20230930", "20230630", "20230331"),
    )
    exposure = {
        row["component_role"]: row["revision_rate_exposure"] for row in component_lineage(result)
    }
    assert exposure["SQ4"] == pytest.approx(0.00747)
    assert exposure["SQ1"] == pytest.approx(0.00073)
    assert exposure["SQ4"] > exposure["SQ1"] * 10


def test_lineage_is_empty_for_an_unresolved_result_but_failures_are_not() -> None:
    result = compute_ttm(
        ts_code="000001.SZ",
        formation_date="20230630",
        versions_by_period={},
        lookback_periods=("20230331",),
    )
    assert isinstance(result, TTMResult)
    assert component_lineage(result) == []
    assert result.failures


def test_cumulative_fact_carries_its_report_type_label() -> None:
    fact = CumulativeFact(
        end_date="20231231",
        period_label="FY",
        resolved=_resolved_stub(),
    )
    assert fact.period_label == "FY"
    assert fact.revision_rate == pytest.approx(0.00747)


def _resolved_stub() -> object:
    from scripts.research.ashare_pit.codes import ResolvedFact

    return ResolvedFact(
        status=FactStatus.RESOLVED,
        value=Decimal("1"),
        selected=_version("1"),
        formation_date="20240630",
        candidates=(_version("1"),),
    )
