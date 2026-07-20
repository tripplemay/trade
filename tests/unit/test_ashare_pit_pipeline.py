"""B109 F002 — 月末面板与覆盖漏斗的纯逻辑单测（离线，不联网）。

被测的核心性质：**每一条流失都有归因**（H4），且 F001 裁定的四项披露不可省略。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_pit.codes import (
    FactStatus,
    MarketCapStatus,
    ResolvedFact,
)
from scripts.research.ashare_pit.marketcap import MarketCapPoint
from scripts.research.ashare_pit.pipeline import (
    REVISION_RATE_BOUNDS,
    PanelRow,
    build_funnel,
    flag0_retention,
    last_trade_date_on_or_before,
    mandatory_disclosures,
    month_end_dates,
    select_latest_resolved,
    summarize_panel,
    to_jsonable,
)


def _fact(status: FactStatus = FactStatus.RESOLVED, value: str = "100") -> ResolvedFact:
    return ResolvedFact(
        status=status,
        value=Decimal(value) if status is FactStatus.RESOLVED else None,
        selected=None,
        formation_date="20231231",
        candidates=(),
    )


def _cap(status: MarketCapStatus = MarketCapStatus.RESOLVED) -> MarketCapPoint:
    return MarketCapPoint(
        ts_code="000001.SZ",
        trade_date="20231229",
        close=Decimal("10"),
        total_share_wan=Decimal("100"),
        total_mv_wan=Decimal("1000"),
        total_mv_cny=Decimal("10000000"),
        identity_error=Decimal(0),
        status=status,
    )


def _row(
    ts_code: str = "000001.SZ",
    *,
    fact: ResolvedFact | None = None,
    cap: MarketCapPoint | None = None,
) -> PanelRow:
    return PanelRow(
        ts_code=ts_code,
        formation_date="20231231",
        end_date="20230930",
        fact=fact if fact is not None else _fact(),
        market_cap=cap,
    )


# --- 月末形成日 ---


def test_month_end_dates_handles_leap_years_and_year_rollover() -> None:
    assert month_end_dates("202311", "202403") == [
        "20231130",
        "20231231",
        "20240131",
        "20240229",  # 闰年
        "20240331",
    ]


def test_single_month_range_is_inclusive() -> None:
    assert month_end_dates("202302", "202302") == ["20230228"]


def test_trade_date_never_looks_forward() -> None:
    """★不晚于形成日——向后取一天就是前视。"""
    dates = ["20231228", "20231229", "20240102"]
    assert last_trade_date_on_or_before(dates, "20231231") == "20231229"
    assert last_trade_date_on_or_before(dates, "20231227") is None


# --- 期次选择 ---


def test_latest_period_wins() -> None:
    end_date, fact = select_latest_resolved(
        {"20230331": _fact(), "20230930": _fact(value="200"), "20230630": _fact()}
    )
    assert end_date == "20230930"
    assert fact.value == Decimal("200")


def test_ambiguous_latest_period_does_not_silently_fall_back_to_an_older_one() -> None:
    """★退回上一期看似「还有数可用」，实则用旧数据冒充当期事实——fail-closed 要拦的正是这个。"""
    end_date, fact = select_latest_resolved(
        {
            "20230630": _fact(value="100"),
            "20230930": _fact(FactStatus.FACT_VERSION_AMBIGUOUS),
        }
    )
    assert end_date == "20230930"
    assert fact.status is FactStatus.FACT_VERSION_AMBIGUOUS
    assert fact.value is None


def test_no_usable_period_returns_none() -> None:
    assert select_latest_resolved({"20230930": _fact(FactStatus.NOT_YET_PUBLISHED)}) == (
        None,
        None,
    )
    assert select_latest_resolved({}) == (None, None)


# --- 覆盖漏斗 ---


def test_every_dropped_row_lands_on_a_structured_reason() -> None:
    rows = [
        _row("A", cap=_cap()),
        _row("B", fact=_fact(FactStatus.NOT_YET_PUBLISHED), cap=_cap()),
        _row("C", fact=_fact(FactStatus.FACT_VERSION_AMBIGUOUS), cap=_cap()),
        _row("D", cap=None),  # 分母缺失
        _row("E", cap=_cap(MarketCapStatus.MARKET_CAP_IDENTITY_FAILED)),
    ]
    funnel = build_funnel(rows, universe_size=7)

    assert funnel["usable"] == 1
    assert funnel["panel_rows"] == 5
    # 宇宙里有、但连一条待解析记录都没有的部分——最容易被漏掉的一段
    assert funnel["no_record_at_all"] == 2
    assert funnel["usable_fraction"] == 1 / 7
    assert funnel["drop_reasons"] == {
        "FACT_VERSION_AMBIGUOUS": 1,
        "MARKET_CAP_IDENTITY_FAILED": 1,
        "NOT_YET_PUBLISHED": 1,
        "TOTAL_MARKET_CAP_MISSING": 1,
    }
    # 流失总数必须等于漏斗差额，不允许有「消失」的行
    assert sum(funnel["drop_reasons"].values()) == funnel["panel_rows"] - funnel["usable"]


def test_ambiguous_count_is_reported_separately_from_generic_drops() -> None:
    """fail-closed 的代价必须单独可见——它不是「缺数据」，是「有数据但分不清版本」。"""
    rows = [_row("A", fact=_fact(FactStatus.FACT_VERSION_AMBIGUOUS), cap=_cap())]
    assert build_funnel(rows, universe_size=1)["fact_version_ambiguous"] == 1


def test_summary_keeps_the_worst_month_visible() -> None:
    """★只给平均数会掩盖单月塌陷。"""
    funnels = [
        build_funnel([_row("A", cap=_cap())], universe_size=1),
        build_funnel([_row("A", fact=_fact(FactStatus.FACT_MISSING), cap=_cap())], universe_size=1),
    ]
    summary = summarize_panel(funnels)
    assert summary["n_formation_dates"] == 2
    assert summary["pooled_usable_fraction"] == 0.5
    assert summary["worst_month_usable_fraction"] == 0.0


def test_empty_panel_does_not_fabricate_a_summary() -> None:
    assert summarize_panel([])["n_formation_dates"] == 0


# --- flag=0 保留率 ---


def test_flag0_retention_is_per_security_not_per_row() -> None:
    """一个证券只要有任一条 flag=0 就算「有检出能力」，多行不得重复计数。"""
    rows = [
        {"ts_code": "A", "update_flag": "0"},
        {"ts_code": "A", "update_flag": "1"},
        {"ts_code": "B", "update_flag": "1"},
        {"ts_code": "C", "update_flag": "1"},
        {"ts_code": "D", "update_flag": "0"},
    ]
    assert flag0_retention(rows) == 0.5
    assert flag0_retention([]) == 0.0


# --- F001 强制披露 ---


def test_all_four_mandatory_disclosures_are_present() -> None:
    """★F001 裁定的四项，任缺其一都会让下游误读数据质量。"""
    disclosures = mandatory_disclosures(
        fact_version_ambiguous=4,
        flag0_retention_by_period={"20231231": 0.105, "20211231": 0.954},
    )

    # (1) 歧义计数
    assert disclosures["fact_version_ambiguous_count"] == 4
    # (2) 逐期 flag=0 保留率（且按期排序，便于逐期读）
    assert list(disclosures["flag0_retention_by_period"]) == ["20211231", "20231231"]
    # (3) 修订率——★区间已撤回（见下条测试），但话必须说清楚而不是留空
    assert "撤回" in disclosures["revision_rate_note"]
    # (4) FY 分量单独标风险
    assert "FY 分量" in disclosures["fy_component_risk_note"]
    # 外推警告随附——2013-2020 是未测的洞
    assert "不可外推" in disclosures["extrapolation_warning"]


def test_withdrawn_revision_rate_is_none_not_a_stale_number() -> None:
    """★★回归：F001 的区间来自被静默截断的单次调用，分页重测后 2021FY 修订率
    从 0.525% 跳到 1.325%（2.5 倍）。

    留一个已知偏低的数比留空更糟——下游会把它当作已验证的事实引用。
    修复前这里是硬编码的 (0.0047, 0.0088)。
    """
    disclosures = mandatory_disclosures(
        fact_version_ambiguous=0, flag0_retention_by_period={}
    )
    assert REVISION_RATE_BOUNDS is None
    assert disclosures["revision_rate_bounds"] is None
    assert disclosures["revision_rate_by_report_type"] is None

    # 只列实际分页重测过的期次，不外推补全
    remeasured = disclosures["revision_rate_remeasured_paged"]
    assert remeasured["20211231"] == 0.01325
    assert all(0.0 <= rate <= 1.0 for rate in remeasured.values())

    # 元缺陷本身必须随每份报告出现——它比任何单个数字都重要
    defect = disclosures["upstream_fetch_defect"]
    assert "静默截断" in defect and "非均匀" in defect


# --- 导出精度 ---


def test_export_keeps_decimals_as_strings_not_floats() -> None:
    """★金额转 float 会在导出这一步悄悄丢精度。"""
    payload = to_jsonable({"v": Decimal("45516000000.12"), "nested": [Decimal("0.1")]})
    assert payload == {"v": "45516000000.12", "nested": ["0.1"]}
