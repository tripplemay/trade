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


def test_usable_rows_disclose_how_stale_their_backing_report_is() -> None:
    """★可用率会把「有数」与「数够新」混为一谈。

    2014 年实测：可用率 91% 看着健康，但 resolver 拿不到最新一期时会回退到更早期次
    （as-of 语义正确），于是一行「可用」背后可能是一年前的报表。
    """
    rows = [
        PanelRow("A", "20231231", "20230930", _fact(), _cap()),  # 92 天
        PanelRow("B", "20231231", "20221231", _fact(), _cap()),  # 365 天
        PanelRow("C", "20231231", "20220930", _fact(), _cap()),  # 457 天
    ]
    lag = build_funnel(rows, universe_size=3)["report_lag"]

    assert lag["n"] == 3
    assert lag["median_days"] == 365
    assert lag["max_days"] == 457
    assert lag["lag_le_180d"] == 1 / 3
    assert lag["lag_le_450d"] == 2 / 3  # C 连年报都换代了


def test_staleness_ignores_unusable_rows() -> None:
    rows = [
        PanelRow("A", "20231231", "20230930", _fact(), _cap()),
        PanelRow("B", "20231231", "20200331", _fact(FactStatus.FACT_MISSING), _cap()),
    ]
    assert build_funnel(rows, universe_size=2)["report_lag"]["n"] == 1


def test_row_without_an_end_date_has_no_lag_rather_than_a_bogus_zero() -> None:
    row = PanelRow("A", "20231231", "", _fact(), _cap())
    assert row.report_lag_days is None
    assert build_funnel([row], universe_size=1)["report_lag"] == {"n": 0}


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
    # (3) 修订率是区间不是点估计，且注明取自可信窗口
    assert len(disclosures["revision_rate_bounds"]) == 2
    assert "可信窗口" in disclosures["revision_rate_note"]
    # (4) FY 分量单独标风险
    assert "FY 分量" in disclosures["fy_component_risk_note"]
    # 外推警告随附——2013-2017 的率不可信
    assert "不可信" in disclosures["extrapolation_warning"]


def test_revision_bounds_come_only_from_the_trusted_measurement_window() -> None:
    """★★回归：区间必须取自 2018-2021（多版本 65%-91%，检出接近完全）。

    修复前这里是 (0.0047, 0.0088)——来自被静默截断的单次调用。
    若有人把 2013-2017 的低值并进区间，下界会被拉到 0.071%，
    而那个低值是**测不出来**，不是**风险低**。
    """
    disclosures = mandatory_disclosures(
        fact_version_ambiguous=0, flag0_retention_by_period={}
    )
    low, high = disclosures["revision_rate_bounds"]
    assert [low, high] == list(REVISION_RATE_BOUNDS)
    assert low < high

    trusted = disclosures["trusted_measurement_years"]
    fy = disclosures["revision_rate_fy_by_year"]
    assert low == min(fy[year] for year in trusted)
    assert high == max(fy[year] for year in trusted)
    # 不可信年份确实更低——正是不得并入区间的原因
    assert fy["2013"] < low


def test_untrusted_years_are_flagged_by_version_multiplicity_not_hidden() -> None:
    """低多版本占比是「率不可信」的前置判据，必须与率并排出现。"""
    disclosures = mandatory_disclosures(
        fact_version_ambiguous=0, flag0_retention_by_period={}
    )
    multiplicity = disclosures["version_multiplicity_fy"]
    for year in disclosures["trusted_measurement_years"]:
        assert multiplicity[year] >= 0.6
    for year in ("2013", "2015", "2017"):
        assert multiplicity[year] < 0.2
    assert "不可观测" in disclosures["version_multiplicity_note"]


def test_refuted_hypotheses_are_recorded_not_quietly_dropped() -> None:
    """★实测推翻的担忧要留档——否则下一个人会重新担心一遍并重新花钱测。"""
    disclosures = mandatory_disclosures(
        fact_version_ambiguous=0, flag0_retention_by_period={}
    )
    warning = disclosures["extrapolation_warning"]
    assert "已推翻" in warning
    assert "NOT_YET_PUBLISHED=0" in warning  # 覆盖洞假设被推翻
    assert "91 天" in warning  # 陈旧假设被推翻


def test_upstream_fetch_defect_travels_with_every_report() -> None:
    """元缺陷比任何单个数字都重要——它决定所有数字能不能信。"""
    defect = mandatory_disclosures(
        fact_version_ambiguous=0, flag0_retention_by_period={}
    )["upstream_fetch_defect"]
    assert "静默截断" in defect and "非均匀" in defect


# --- 导出精度 ---


def test_export_keeps_decimals_as_strings_not_floats() -> None:
    """★金额转 float 会在导出这一步悄悄丢精度。"""
    payload = to_jsonable({"v": Decimal("45516000000.12"), "nested": [Decimal("0.1")]})
    assert payload == {"v": "45516000000.12", "nested": ["0.1"]}
