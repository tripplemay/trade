"""B108 F001 — 三个独立来源的抽取（spec §3.1）。

- ``S1`` 合并利润表「归属于母公司所有者的净利润」
- ``S2`` 主要会计数据表「归属于上市公司股东的净利润」
- ``S3`` 数量级哨兵（只否决，不确认）

**期间语义必须对齐（否则 S1/S2 会系统性误报冲突）。** 两个来源一律取
「年初至报告期末」口径：三季报的主要会计数据表同时有「本报告期」（单季）和
「年初至报告期末」（累计）两列，选错列会让 S2 拿到单季、S1 拿到累计，
于是每一份三季报都变成冲突。列选择因此按表头文字定优先级，不按列号。
"""

from __future__ import annotations

import re
from decimal import Decimal

from scripts.research.ashare_ep.codes import FailureCode, SourceValue
from scripts.research.ashare_ep.layout import (
    Column,
    Row,
    assign_column,
    build_rows,
    find_header_columns,
    parse_number,
    resolve_unit,
    unit_scale,
)

# 目标列表头，按优先级排列。「年初至报告期末」必须排在「本报告期」之前（见模块 docstring）。
_TARGET_HEADERS: tuple[str, ...] = (
    "年初至报告期末",
    "本期金额",
    "本期发生额",
    "本报告期",
    "本年",
    "本期",
)

# 排除列。优先级高于 _TARGET_HEADERS：「年初至报告期末比上年同期增减」同时命中两边，判为排除。
_EXCLUDED_HEADERS: tuple[str, ...] = ("上年", "上期", "去年", "同期", "增减", "变动", "%", "％")

_YEAR_HEADER_PATTERN = re.compile(r"^(\d{4})\s*年?$")

# 无列模型、仅靠「整行只有一个数值」取到的命中。可能来自叙述性文字，
# 因此在 _extract 里让位给真正的表格行（E07）。
SINGLE_VALUE_COLUMN = "<single-value-row>"

# S1：合并利润表的归母净利润
_S1_LABELS: tuple[str, ...] = (
    "归属于母公司所有者的净利润",
    "归属于母公司股东的净利润",
)

# S2：主要会计数据表的归母净利润
_S2_LABELS: tuple[str, ...] = ("归属于上市公司股东的净利润",)

# 两个来源共用的排除词：扣非、综合收益、少数股东都是相邻的**不同**概念，
# 上游报告 §12「归母净利润与扣非归母净利润相邻」点名要求区分。
_LABEL_EXCLUSIONS: tuple[str, ...] = (
    "扣除非经常性损益",
    "扣非",
    "综合收益",
    "少数股东",
    "现金流量",
    "每股",
)

_BASIC_EPS_LABELS: tuple[str, ...] = ("基本每股收益",)
_EPS_EXCLUSIONS: tuple[str, ...] = ("稀释", "扣除非经常性损益", "扣非")

# 数量级哨兵的可信区间（spec §3.1 S3）。
#
# 这不是针对样本调出来的阈值，而是 A 股全市场的结构性事实：最小的上市公司股本在
# 千万股量级，最大的（工商银行 ~3.56e11 股）在千亿股量级。下界 1e6、上界 1e12
# 各自比真实宇宙宽 1-2 个数量级，因此只会对 10^3 及以上的粗错误报警，
# 不会对任何真实公司误伤。判据作用在**推算股本**上，不作用在利润值本身。
_MIN_PLAUSIBLE_SHARES = Decimal("1e6")
_MAX_PLAUSIBLE_SHARES = Decimal("1e12")

# EPS 太接近 0 时相除会放大噪声，此时放弃哨兵而不是误报
_MIN_SENTINEL_EPS = Decimal("0.01")


def _matches(label: str, wanted: tuple[str, ...], exclusions: tuple[str, ...]) -> bool:
    compact = re.sub(r"\s+", "", label)
    if any(token in compact for token in exclusions):
        return False
    return any(token in compact for token in wanted)


def select_target_column(columns: tuple[Column, ...]) -> Column | None:
    """按表头文字选目标列。取代原实现的硬编码 ``selected_index``（bug ③）。"""
    eligible = [
        column
        for column in columns
        if not column.is_note_column
        and not any(token in column.header for token in _EXCLUDED_HEADERS)
    ]
    if not eligible:
        return None
    for token in _TARGET_HEADERS:
        for column in eligible:
            if token in column.header:
                return column
    # 年报的主要会计数据表常用裸年份作表头（「2023年」「2022年」）——取最大年份 = 本期
    years = [
        (int(match.group(1)), column)
        for column in eligible
        if (match := _YEAR_HEADER_PATTERN.match(column.header.strip()))
    ]
    if years:
        return max(years, key=lambda item: item[0])[1]
    return None


def _row_value(
    lines: list[str],
    row: Row,
    source: str,
) -> tuple[SourceValue | None, FailureCode | None]:
    """从一个逻辑行取出目标列的数值。"""
    numeric = [cell for cell in row.cells if cell.is_number and not cell.is_percent]
    if not numeric:
        return None, FailureCode.EXTRACTION_FAILED

    columns, header_line = find_header_columns(lines, row.line_index)
    if header_line < 0:
        header_line = row.line_index

    if columns:
        target = select_target_column(columns)
        if target is None:
            return None, FailureCode.COLUMN_AMBIGUOUS
        # 附注列的单元格在此被结构性排除（bug ①）：它归属的列表头含「附注」，
        # 不是目标列，因此永远不会被选中——不需要任何「数值太小」的幅度判断。
        candidates = [cell for cell in numeric if assign_column(cell, columns) is target]
        if not candidates:
            return None, FailureCode.COLUMN_AMBIGUOUS
        cell = candidates[0]
        column_header = target.header
    elif len(numeric) == 1:
        # 没有可识别表头，但整行只有一个数值 → 无歧义。
        # 这类命中可能来自叙述性文字，故标记出来供 _extract 降级（E07）。
        cell = numeric[0]
        column_header = SINGLE_VALUE_COLUMN
    else:
        return None, FailureCode.COLUMN_AMBIGUOUS

    raw = parse_number(cell.text)
    if raw is None:
        return None, FailureCode.EXTRACTION_FAILED

    unit, unit_origin, ambiguous = resolve_unit(lines, header_line)
    if ambiguous:
        return None, FailureCode.UNIT_AMBIGUOUS

    return (
        SourceValue(
            source=source,
            value=raw * unit_scale(unit),
            raw_value=raw,
            unit=unit,
            unit_source=unit_origin,
            label=row.label,
            column_header=column_header,
            line_index=row.line_index,
        ),
        None,
    )


def _extract(
    lines: list[str],
    rows: list[Row],
    labels: tuple[str, ...],
    exclusions: tuple[str, ...],
    source: str,
) -> tuple[list[SourceValue], list[FailureCode]]:
    values: list[SourceValue] = []
    failures: list[FailureCode] = []
    for row in rows:
        if not _matches(row.label, labels, exclusions):
            continue
        value, failure = _row_value(lines, row, source)
        if value is not None:
            values.append(value)
        elif failure is not None:
            failures.append(failure)

    # ★E07 修复：表格内命中优先于游离命中。
    #
    # 「归属于上市公司股东的净利润」也会出现在业绩预告、管理层讨论等**叙述性文字**里。
    # 这类命中没有列模型，只是碰巧行内有个数。原实现把它和真正的表格行一视同仁，
    # 于是「同一来源多行不一致」被触发 → 假冲突，把本来抽对的值也毁掉
    # （B108 F003 实测 40% 的冲突是这样来的，002605 / 002382）。
    tabled = [item for item in values if item.column_header != SINGLE_VALUE_COLUMN]
    if tabled:
        values = tabled

    if not values and not failures:
        failures.append(FailureCode.LABEL_NOT_FOUND)
    return values, failures


def extract_s1(lines: list[str], rows: list[Row]) -> tuple[list[SourceValue], list[FailureCode]]:
    """S1 — 合并利润表归母净利润。"""
    return _extract(lines, rows, _S1_LABELS, _LABEL_EXCLUSIONS, "S1")


def extract_s2(lines: list[str], rows: list[Row]) -> tuple[list[SourceValue], list[FailureCode]]:
    """S2 — 主要会计数据表归母净利润。"""
    return _extract(lines, rows, _S2_LABELS, _LABEL_EXCLUSIONS, "S2")


def extract_basic_eps(lines: list[str], rows: list[Row]) -> Decimal | None:
    """基本每股收益。EPS 本身就以元/股计价，不套用表级单位倍数。"""
    for row in rows:
        if not _matches(row.label, _BASIC_EPS_LABELS, _EPS_EXCLUSIONS):
            continue
        value, _ = _row_value(lines, row, "S3")
        if value is not None:
            return value.raw_value
    return None


def magnitude_is_plausible(profit: Decimal, basic_eps: Decimal | None) -> bool | None:
    """S3 数量级哨兵。

    返回 ``None`` 表示**无法判定**（哨兵不适用），不是通过。

    做法是反过来推算股本：``|净利润| / |基本EPS|`` 应落在 A 股股本的合理区间。
    这样不需要从正文里再抽一次总股本（季报正文常常没有），而 10^n 级的单位错误
    会把推算股本推出区间好几个数量级，必然被抓住。

    注意基本 EPS 用的是**加权平均股本**，与期末股本有真实的百分比级偏差——所以这个
    哨兵只能用来否决，绝不能单独确认一个值（spec §3.1）。
    """
    if basic_eps is None or abs(basic_eps) < _MIN_SENTINEL_EPS:
        return None
    implied_shares = abs(profit) / abs(basic_eps)
    return _MIN_PLAUSIBLE_SHARES <= implied_shares <= _MAX_PLAUSIBLE_SHARES


def parse_document(text: str) -> list[Row]:
    """``pdftotext -layout`` 文本 → 逻辑行。"""
    return build_rows(text.splitlines())
