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
from scripts.research.ashare_ep.layout import build_rows, parse_number, resolve_unit, split_cells
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


def test_unit_falls_back_to_document_scope_when_table_has_none() -> None:
    lines = ["单位：万元", *["填充行"] * 20, "项目            本期金额        上期金额"]
    unit, origin, ambiguous = resolve_unit(lines, header_line=21)
    assert (unit, origin) == ("万元", "document")


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
