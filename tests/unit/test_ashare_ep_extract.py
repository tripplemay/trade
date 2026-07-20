"""B108 F001 — 多源交叉验证抽取器单测。

★H2 边界：本文件只用**合成** fixture。原 pilot 的 50 份真实样本已进入 Generator 上下文
（= 样本内），不得作为测试素材，否则最终评测数字失去意义。

每一个针对 spec §3.4 四类 bug 的测试都构造成「原实现会答错、新实现应答对」的形态，
这样 Evaluator 可以逐条对照 bug 类别验收。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_ep.codes import FailureCode, Status
from scripts.research.ashare_ep.crosscheck import cross_check, relative_error
from scripts.research.ashare_ep.layout import (
    build_rows,
    find_header_columns,
    parse_number,
    resolve_unit,
    split_cells,
)
from scripts.research.ashare_ep.sources import (
    extract_s1,
    extract_s2,
    magnitude_is_plausible,
    parse_document,
)

# --- 合成版面工具：用固定宽度产生字符对齐的表，模拟 pdftotext -layout 输出 ---


def _income_row(label: str, note: str = "", current: str = "", prior: str = "") -> str:
    """合并利润表行：标签 | 附注 | 本期金额 | 上期金额。"""
    return f"{label:<45}{note:>8}{current:>22}{prior:>22}".rstrip()


def _q3_row(label: str, this_q: str, this_q_chg: str, ytd: str, ytd_chg: str) -> str:
    """三季报主要会计数据行：本报告期 | 增减 | 年初至报告期末 | 增减。

    字段宽度必须让相邻表头之间留出 2 个以上空格，否则 ``split_cells`` 会把两个表头
    并成一个单元格——那是 fixture 的失真，不是被测代码的问题。
    """
    return f"{label:<32}{this_q:>20}{this_q_chg:>16}{ytd:>24}{ytd_chg:>18}".rstrip()


_INCOME_STATEMENT = "\n".join(
    [
        "                                                    单位：元",
        "",
        "合并利润表",
        "",
        _income_row("项目", "附注", "本期金额", "上期金额"),
        _income_row("一、营业总收入", "1", "1,500,000,000.00", "1,200,000,000.00"),
        _income_row("二、净利润", "34", "260,000,000.00", "210,000,000.00"),
        _income_row("  归属于母公司所有者的净利润", "35", "252,300,000.00", "198,000,000.00"),
        _income_row("  少数股东损益", "36", "7,700,000.00", "12,000,000.00"),
    ]
)

_MAIN_FINANCIALS_Q3 = "\n".join(
    [
        "                                        单位：元",
        "",
        "一、主要会计数据",
        "",
        _q3_row(
            "项目",
            "本报告期",
            "本报告期比上年同期增减",
            "年初至报告期末",
            "年初至报告期末比上年同期增减",
        ),
        _q3_row("营业收入", "500,000,000.00", "12.50%", "1,500,000,000.00", "10.20%"),
        _q3_row("归属于上市公司股东的净利润", "80,000,000.00", "8.00%", "252,300,000.00", "9.10%"),
        _q3_row(
            "归属于上市公司股东的扣除非经常性损益的净利润",
            "70,000,000.00",
            "7.00%",
            "240,000,000.00",
            "8.10%",
        ),
        _q3_row("基本每股收益（元/股）", "0.08", "8.00%", "0.25", "9.10%"),
    ]
)

_FULL_REPORT = _MAIN_FINANCIALS_Q3 + "\n\n\n" + _INCOME_STATEMENT


# --- 版面原语 ---


def test_split_cells_breaks_on_two_or_more_spaces() -> None:
    cells = split_cells("归属于母公司所有者的净利润       35     252,300,000.00")
    assert [cell.text for cell in cells] == ["归属于母公司所有者的净利润", "35", "252,300,000.00"]


def test_parse_number_handles_separators_and_accounting_negatives() -> None:
    assert parse_number("252,300,000.00") == Decimal("252300000.00")
    assert parse_number("(1,234.50)") == Decimal("-1234.50")
    assert parse_number("（1,234.50）") == Decimal("-1234.50")
    assert parse_number("-1,234.50") == Decimal("-1234.50")
    assert parse_number("－1,234.50") == Decimal("-1234.50")
    assert parse_number("12.50%") is None
    assert parse_number("五、35") is None


# --- bug ① 附注列误认 ---


def test_note_column_is_excluded_structurally() -> None:
    """附注列的裸编号不得被当成金额。

    原实现取「标签后第一个数字」→ 会返回 35。新实现按表头把 35 归到「附注」列，
    该列不是目标列，因此结构性地不可能被选中——不依赖任何「数值太小」的幅度判断。
    """
    rows = parse_document(_INCOME_STATEMENT)
    values, failures = extract_s1(_INCOME_STATEMENT.splitlines(), rows)
    assert not failures
    assert len(values) == 1
    assert values[0].value == Decimal("252300000.00")
    assert values[0].column_header == "本期金额"


# --- bug ② 单位跨表错绑 ---


def test_unit_binds_to_nearest_declaration_above_table() -> None:
    lines = [
        "单位：万元",
        "上一张表的内容",
        "",
        "另一张表",
        "单位：元",
        "项目            本期金额        上期金额",
    ]
    unit, origin, ambiguous = resolve_unit(lines, header_line=5)
    assert (unit, origin, ambiguous) == ("元", "table", False)


def test_unit_search_stops_at_previous_table_data_row() -> None:
    """★E04 回归：单位搜索必须在表边界停，而不是一路向上找到别的表的声明。

    F003 实测 002670 2018 年报：「单位：万元」在合并利润表表头之外 612 行、
    隔着整张主要会计数据表，仍被绑定，把 -544,272,818.63 放大成 -5,442,728,186,300.00。
    原实现只是把越界命中改了个标签叫 document，然后照乘不误。
    """
    lines = [
        "三、其他重要事项",
        "   单位：万元",
        "项目          本期金额        上期金额",
        "营业收入      1,234.00        1,100.00",  # ← 上一张表的数据行 = 表边界
        "",
        "合并利润表",
        "项目          本期金额        上期金额",
    ]
    unit, origin, ambiguous = resolve_unit(lines, header_line=6)
    assert (unit, origin, ambiguous) == ("元", "default", False)


def test_unit_declaration_directly_above_table_still_binds() -> None:
    """边界停止不能误伤正常情形：声明紧贴表头时必须照常生效。"""
    lines = ["合并利润表", "   单位：万元", "项目          本期金额        上期金额"]
    unit, origin, _ = resolve_unit(lines, header_line=2)
    assert (unit, origin) == ("万元", "table")


def test_conflicting_units_in_table_scope_are_flagged_ambiguous() -> None:
    lines = ["单位：万元", "单位：元", "项目            本期金额        上期金额"]
    _, _, ambiguous = resolve_unit(lines, header_line=2)
    assert ambiguous is True


def test_unit_scale_is_applied_to_extracted_value() -> None:
    text = "\n".join(
        [
            "                                                    单位：万元",
            "",
            _income_row("项目", "附注", "本期金额", "上期金额"),
            _income_row("  归属于母公司所有者的净利润", "35", "25,230.00", "19,800.00"),
        ]
    )
    values, _ = extract_s1(text.splitlines(), parse_document(text))
    assert values[0].unit == "万元"
    assert values[0].value == Decimal("252300000.00")


# --- bug ③ 列位选错 ---


def test_q3_selects_ytd_column_not_single_quarter() -> None:
    """三季报必须取「年初至报告期末」（累计），不是「本报告期」（单季）。

    这条同时防两件事：取错口径，以及 S1(累计) 与 S2(单季) 因口径不同而系统性误报冲突。
    """
    rows = parse_document(_MAIN_FINANCIALS_Q3)
    values, failures = extract_s2(_MAIN_FINANCIALS_Q3.splitlines(), rows)
    assert not failures
    assert values[0].value == Decimal("252300000.00")
    assert values[0].column_header == "年初至报告期末"


def test_prior_period_and_change_columns_are_never_selected() -> None:
    rows = parse_document(_INCOME_STATEMENT)
    values, _ = extract_s1(_INCOME_STATEMENT.splitlines(), rows)
    assert values[0].value != Decimal("198000000.00")


def test_deducted_non_recurring_profit_row_is_excluded() -> None:
    """扣非归母净利润与归母净利润相邻，必须区分（上游报告 §12 点名要求）。"""
    rows = parse_document(_MAIN_FINANCIALS_Q3)
    values, _ = extract_s2(_MAIN_FINANCIALS_Q3.splitlines(), rows)
    assert len(values) == 1
    assert values[0].value == Decimal("252300000.00")
    assert "扣除非经常性损益" not in values[0].label


# --- bug ④ 旧模板标签断行 ---


def test_label_split_across_lines_by_numbers_is_rejoined() -> None:
    """折行会把标签从中间劈开，数字夹在两段标签之间。"""
    text = "\n".join(
        [
            "单位：元",
            "项目                                  本报告期            上年同期",
            "归属于上市公司股东的净利",
            "                                 10,919,621.90       15,192,356.22",
            "润（元）",
        ]
    )
    rows = build_rows(text.splitlines())
    rejoined = [row for row in rows if "归属于上市公司股东的净利润" in row.label]
    assert rejoined, f"标签未重连，得到：{[row.label for row in rows]}"

    values, _ = extract_s2(text.splitlines(), rows)
    assert values[0].value == Decimal("10919621.90")


# --- S3 数量级哨兵 ---


def test_magnitude_sentinel_accepts_plausible_share_count() -> None:
    # 2.523 亿利润 / 0.25 元 EPS ≈ 10.09 亿股，A 股常见量级
    assert magnitude_is_plausible(Decimal("252300000"), Decimal("0.25")) is True


def test_magnitude_sentinel_rejects_unit_scale_blowup() -> None:
    # 同样的 EPS 下利润被放大 10^4 → 推算股本 1.009e13，超出任何真实公司
    assert magnitude_is_plausible(Decimal("2523000000000"), Decimal("0.25")) is False


def test_magnitude_sentinel_abstains_when_eps_near_zero() -> None:
    """EPS 接近零时相除会放大噪声——此时必须弃权，而不是误报。"""
    assert magnitude_is_plausible(Decimal("252300000"), Decimal("0.001")) is None
    assert magnitude_is_plausible(Decimal("252300000"), None) is None


# --- 交叉验证终态 ---


def test_cross_check_confirms_when_both_sources_agree() -> None:
    result = cross_check(_FULL_REPORT)
    assert result.status is Status.CONFIRMED
    assert result.value == Decimal("252300000.00")
    assert result.failure_code is None
    assert result.is_usable
    assert {source.source for source in result.sources} == {"S1", "S2"}


def test_cross_check_returns_none_on_conflict() -> None:
    """★本批次的核心行为改变：抽不准就返回 None，不返回猜测值。"""
    tampered = _FULL_REPORT.replace("252,300,000.00", "251,000,000.00", 1)
    result = cross_check(tampered)
    assert result.status is Status.SOURCE_CONFLICT
    assert result.value is None
    assert result.failure_code is FailureCode.SOURCE_CONFLICT
    assert not result.is_usable
    # 候选值必须全部保留，供人工裁定
    assert len(result.sources) == 2


def test_cross_check_reports_single_source_when_only_one_table_present() -> None:
    result = cross_check(_INCOME_STATEMENT)
    assert result.status is Status.SINGLE_SOURCE_UNCONFIRMED
    assert result.value == Decimal("252300000.00")
    assert result.failure_code is FailureCode.SINGLE_SOURCE_UNCONFIRMED
    # 单源值不算可用——必须由调用方显式降级使用
    assert not result.is_usable


def test_cross_check_fails_closed_when_label_absent() -> None:
    result = cross_check("这份文档里没有任何利润表。\n\n单位：元\n")
    assert result.status is Status.EXTRACTION_FAILED
    assert result.value is None
    assert result.failure_code is FailureCode.LABEL_NOT_FOUND


def test_cross_check_revokes_confirmation_on_implausible_magnitude() -> None:
    """两个来源可以同时错——例如单位声明本身就错。哨兵负责兜这一层。

    这里把两张表的单位都改成万元（数字不动，故列对齐不受影响），于是 S1/S2 一致地
    放大 10^4；只有 S3 能发现推算股本已经离谱。
    """
    inflated = _FULL_REPORT.replace("单位：元", "单位：万元")
    result = cross_check(inflated)
    assert result.status is Status.MAGNITUDE_IMPLAUSIBLE
    assert result.value is None
    assert result.failure_code is FailureCode.MAGNITUDE_IMPLAUSIBLE


def test_relative_error_is_guarded_near_zero() -> None:
    assert relative_error(Decimal(0), Decimal(0)) == Decimal(0)
    assert relative_error(Decimal("0.4"), Decimal("0.5")) <= Decimal("0.1")


# --- B108 F003 验收缺陷回归（E02 / E03 / E05 / E07）---
#
# 以下 fixture 全部取自 F003 signoff 已公开点名的版面形态。这些文档已在报告中披露，
# 因此用作回归 fixture 不额外消耗 holdout；但**最终复评必须换新 seed 重抽**，
# 不能在这批上测精确率。


_WRAPPED_MAIN_TABLE = "\n".join(
    [
        "单位：元",
        "项目                        本报告期              上年同期增减        年初至报告期末",
        "营业收入（元）        1,856,031,630.20             -8.37%        4,178,189,526.43",
        "归属于上市公司股东",
        "                       -79,024,133.16           -132.14%          -402,092,072.05",
        "的净利润（元）",
        "经营活动产生的现金",
        "                                   --                 --           505,156,643.19",
        "流量净额（元）",
        "基本每股收益（元/",
        "                              -0.0649           -131.81%                  -0.3309",
        "股）",
    ]
)


def test_label_rejoin_does_not_swallow_the_next_table_row() -> None:
    """★E02 回归：标签重连不得跨越已完成的表格行。

    F003 实测 300432：`营业收入（元）` 与 `归属于上市公司股东的净利润（元）` 被并成一行，
    且营业收入的单元格排在前面 → 返回营业收入 41.8 亿当归母净利润（真值 -4.02 亿）。
    这是本批次立项要消灭的「自信的错值」，而且比原 bug 更隐蔽。
    """
    rows = build_rows(_WRAPPED_MAIN_TABLE.splitlines())
    merged = [
        row.label
        for row in rows
        if "营业收入" in row.label and "归属于上市公司股东的净利润" in row.label
    ]
    assert not merged, f"标签跨行合并了相邻表格行：{merged}"

    values, _ = extract_s2(_WRAPPED_MAIN_TABLE.splitlines(), rows)
    assert values[0].value == Decimal("-402092072.05")


def test_label_rejoin_stops_after_one_tail_segment() -> None:
    """数字到达后只允许接**一段**标签尾——第二段是下一行的标签头。

    缺这条约束时，`经营活动产生的现金/流量净额` 会继续吞掉 `基本每股收益（元/`，
    于是 EPS 抽成 5.05 亿的经营现金流，S3 哨兵反过来否决正确的归母净利润。
    """
    rows = build_rows(_WRAPPED_MAIN_TABLE.splitlines())
    eps_rows = [row for row in rows if "基本每股收益" in row.label]
    assert eps_rows, "基本每股收益行丢失"
    assert "经营活动" not in eps_rows[0].label


def test_multiline_header_band_is_merged_into_columns() -> None:
    """★E03 回归：真实财报表头跨物理行，只认单行会让列模型整个建不起来。

    F003 实测这一条命中 76 次，是 48.7% EXTRACTION_FAILED 的第一主因。
    """
    lines = [
        "单位：元",
        "                          上年同期              本报告期比上年同期增减",
        "          本报告期",
        "                     调整前          调整后          调整后",
        "归属于上市公司股东的净利润   1,000.00      900.00        950.00        5.26%",
    ]
    columns, band_start, band_end = find_header_columns(lines, before_line=4)
    assert columns, "跨行表头未被识别"
    assert 0 <= band_start <= band_end
    assert any("本报告期" in column.header for column in columns)


def test_unit_declaration_inside_header_band_is_still_found() -> None:
    """★N01 回归：单位声明夹在表头带内部时必须仍能绑定。

    复验实测 601186 的「单位:千元」在 L2971、表头带起点在 L2969——
    从带**起点**向上扫，声明落在扫描起点之下，结构性不可达 → 单位丢失 → 值缩小 10³。
    修法是从带**末端**起扫，覆盖整条带。
    """
    lines = [
        "合并利润表",
        "单位:千元 币种:人民币",
        "项目                    本期金额            上期金额",
        "归属于母公司所有者的净利润     5,330,703.00      4,100,000.00",
    ]
    columns, band_start, band_end = find_header_columns(lines, before_line=3)
    assert columns
    # 声明在带内部：起点在它之上，末端在它之下
    assert band_start <= 1 <= band_end

    values, _ = extract_s1(lines, parse_document("\n".join(lines)))
    assert values[0].unit == "千元"
    assert values[0].value == Decimal("5330703000.00")


def test_bare_year_header_anchors_the_column_model() -> None:
    """★N03 回归：年报主要会计数据表的表头是裸年份，必须能作锚点。

    两轮验收年报都是 0 CONFIRMED，根因是锚点词表不含裸年份 →
    列模型建不起来 → select_target_column 里的裸年份兜底永远等不到被调用。
    锚点词表必须与列选择词表覆盖同一批表头形态。
    """
    lines = [
        "单位：元",
        "                        2018 年              2017 年       本年比上年增减",
        "归属于上市公司股东的净利润   252,300,000.00   198,000,000.00        27.42%",
    ]
    columns, band_start, _ = find_header_columns(lines, before_line=2)
    assert columns, "裸年份表头未能作为锚点"
    assert band_start >= 0

    values, _ = extract_s2(lines, parse_document("\n".join(lines)))
    assert values[0].value == Decimal("252300000.00")
    assert "2018" in values[0].column_header


def test_equity_statement_rows_are_not_treated_as_income_statement() -> None:
    """★N02 回归：所有者权益变动表的「加：本期归属于母公司所有者的净利润」不是 S1。

    复验实测 S1 的 47 次命中里 37 次来自权益变动表。这不只违反 spec §3.1，
    更动摇交叉验证前提——S1/S2 本应是两个独立位置，实测已有 >=3 份两表真的不等。
    """
    lines = [
        "单位：元",
        "合并所有者权益变动表",
        "项目                          本期金额            上期金额",
        "加：本期归属于母公司所有者的净利润   194,825,145.94    150,000,000.00",
    ]
    values, failures = extract_s1(lines, parse_document("\n".join(lines)))
    assert not values, f"权益变动表行被当成了合并利润表：{[v.label for v in values]}"
    assert FailureCode.LABEL_NOT_FOUND in failures


def test_sentinel_also_guards_the_single_source_path() -> None:
    """★E05 回归：S3 哨兵原先只在 CONFIRMED 路径跑，对单源结构性不可达。

    单源恰恰最需要兜底——没有第二个来源可对照。
    """
    text = "\n".join(
        [
            "单位：万元",
            _income_row("项目", "附注", "本期金额", "上期金额"),
            _income_row("  归属于母公司所有者的净利润", "35", "544,272,818.63", "58,064,247.02"),
            "单位：元",
            "项目                        本报告期",
            "基本每股收益（元/股）              0.28",
        ]
    )
    result = cross_check(text)
    # 万元 × 5.44 亿 = 5.44 万亿，配 0.28 元 EPS → 推算股本 1.9e13，远超真实宇宙
    assert result.status is Status.MAGNITUDE_IMPLAUSIBLE
    assert result.value is None


def test_narrative_hit_yields_to_tabled_hit() -> None:
    """★E07 回归：业绩预告/MD&A 的叙述文字命中不得触发假冲突。

    F003 实测 40% 的 SOURCE_CONFLICT 是这样来的，把本来抽对的值也毁掉。
    """
    text = "\n".join(
        [
            "单位：元",
            "二、管理层讨论与分析",
            "报告期内归属于上市公司股东的净利润 12345.00 万元，同比大幅增长。",
            "",
            "一、主要会计数据",
            "项目                        本报告期              上年同期",
            "归属于上市公司股东的净利润    252,300,000.00      198,000,000.00",
        ]
    )
    values, _ = extract_s2(text.splitlines(), parse_document(text))
    assert len(values) == 1
    assert values[0].value == Decimal("252300000.00")
    assert values[0].column_header != "<single-value-row>"
