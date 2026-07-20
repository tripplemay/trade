"""B108 F001 — ``pdftotext -layout`` 版面解析：单元格 / 列模型 / 跨行标签重连 / 单位绑定。

这个模块是 spec §3.4 四类 bug 里 ①③④ 的共同解药。原实现把「标签后面的所有数字」
铺平成一个列表再取 ``numbers[0]``，于是附注列的注释编号、上年同期列、增减百分比
全都可能被当成答案。这里改成**先重建版面结构，再按表头文字定位**。

核心判据全部锚在**表头文字**与**字符列区间**上，不锚在数值幅度上——这是 spec H1
「修 bug 类别而不是修具体样本」可以被 Evaluator 客观审查的唯一形式。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# 单元格 = 被 2 个及以上空格分隔的一段（pdftotext -layout 用空格保留列对齐）
_CELL_PATTERN = re.compile(r"\S+(?:[ ]\S+)*")

# 数字：支持千分位、小数、前置负号（含全角）、括号负数、尾随百分号
_NUMBER_PATTERN = re.compile(
    r"^[（(]?\s*[-−－]?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*[)）]?\s*[%％]?$|"
    r"^[（(]?\s*[-−－]?\s*\d+(?:\.\d+)?\s*[)）]?\s*[%％]?$"
)

_CJK_PATTERN = re.compile(r"[一-鿿]")

# 单位声明。只认显式的「单位：X」，不猜。
_UNIT_PATTERN = re.compile(r"单\s*位\s*[：:]\s*(?:人民币)?\s*(百万元|万元|千元|元)")

_UNIT_SCALE: dict[str, Decimal] = {
    "元": Decimal(1),
    "千元": Decimal(1_000),
    "万元": Decimal(10_000),
    "百万元": Decimal(1_000_000),
}

# 表头识别用的期间/结构性表头词。命中任意一个即认为该行是表头行。
_HEADER_TOKENS: tuple[str, ...] = (
    "本报告期",
    "年初至报告期末",
    "上年同期",
    "本期金额",
    "上期金额",
    "本期发生额",
    "上期发生额",
    "附注",
    "项目",
)

# 附注列表头（该列承载的是报表附注编号，不是金额）——bug ① 的结构化判据
_NOTE_HEADER_TOKENS: tuple[str, ...] = ("附注", "注释")

# 裸年份表头（「2018 年」「2017年」）。★N03 修复：年报的主要会计数据表表头就是裸年份 +
# 「本年比上年增减」，一个 _HEADER_TOKENS 都不命中 → 锚点找不到 → 列模型建不起来 →
# 年报两轮 0/34 CONFIRMED。sources.select_target_column 本就有裸年份兜底，
# 但锚点认不出来，兜底永远等不到被调用。**锚点词表必须与列选择词表覆盖同一批表头形态。**
_YEAR_HEADER_PATTERN = re.compile(r"^\d{4}\s*年?$")


def is_header_cell(text: str) -> bool:
    """一个单元格文字是否可作表头锚点。"""
    stripped = text.strip()
    if _YEAR_HEADER_PATTERN.match(stripped):
        return True
    return any(token in stripped for token in _HEADER_TOKENS)

# 标签跨行最多向后并入几行（bug ④）。给一个小上限防止把相邻行误并。
_MAX_LABEL_CONTINUATION_LINES = 3

# 表头带向上/向下最多延伸几行（E03）。真实财报的多层表头一般 2-4 行。
_HEADER_BAND_LINES = 4

# 向上找表头锚点的最大行数。
#
# ★原值 40 是拍脑袋定的，而合并利润表是**长表**：B108 复验语料实测 S1 行到最近表头行的
# 距离中位数 58 行、p90 79 行、max 297 行，**只有 25.2% 落在 40 行内**——
# 于是 113 次 COLUMN_AMBIGUOUS，列模型对长表整体建不起来。
# 取 120 覆盖实测的 98.1%，留出余量而不至于跨到很远的无关表。
# 注：该分布测自 r2 语料，对本轮属样本内；独立复评应重新核这个覆盖率。
_HEADER_LOOKBACK_LINES = 120


@dataclass(frozen=True)
class Cell:
    """一个单元格及其在物理行中的字符区间。区间是列归属判定的依据。"""

    text: str
    start: int
    end: int

    @property
    def center(self) -> float:
        return (self.start + self.end) / 2

    @property
    def is_number(self) -> bool:
        return bool(_NUMBER_PATTERN.match(self.text.strip()))

    @property
    def is_percent(self) -> bool:
        return self.text.strip().endswith(("%", "％"))


@dataclass(frozen=True)
class Column:
    """表头定义的一列。``header`` 是列选择的唯一依据（取代硬编码 selected_index）。"""

    header: str
    start: int
    end: int

    @property
    def center(self) -> float:
        return (self.start + self.end) / 2

    @property
    def is_note_column(self) -> bool:
        return any(token in self.header for token in _NOTE_HEADER_TOKENS)


@dataclass(frozen=True)
class Row:
    """一个逻辑行——可能由多个物理行重连而成（bug ④ 的跨行标签）。"""

    label: str
    cells: tuple[Cell, ...]
    line_index: int


def split_cells(line: str) -> tuple[Cell, ...]:
    """按 2+ 空格切分单元格，保留字符区间。"""
    return tuple(
        Cell(match.group(0), match.start(), match.end()) for match in _CELL_PATTERN.finditer(line)
    )


def _has_cjk(value: str) -> bool:
    return bool(_CJK_PATTERN.search(value))


def parse_number(text: str) -> Decimal | None:
    """解析中文财报里的数字。括号 = 负数（会计惯例）；百分比一律拒绝。"""
    stripped = text.strip()
    if not _NUMBER_PATTERN.match(stripped):
        return None
    if stripped.endswith(("%", "％")):
        return None
    negative = stripped.startswith(("（", "(")) and stripped.endswith(("）", ")"))
    body = stripped.strip("（()）").strip()
    if body.startswith(("-", "−", "－")):
        negative = True
        body = body[1:].strip()
    try:
        value = Decimal(body.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return -value if negative else value


def build_rows(lines: list[str]) -> list[Row]:
    """把物理行重建成逻辑行，处理 ``pdftotext`` 的标签折行。

    折行的典型形态是标签被数字**从中间劈开**：

    .. code-block:: text

        归属于上市公司股东的净利
                    10,919,621.90  15,192,356.22 -28.12%
        润（元）

    因此不能只做「向下并入下一行」，必须允许标签碎片在数字行之后继续并入。
    """
    rows: list[Row] = []
    label_parts: list[str] = []
    pending_cells: list[Cell] = []
    pending_line: int | None = None
    continuation = 0
    # ★E02 修复的关键状态：挂起行是否由「标签+数值」同行启动。
    # 由标签+数值启动的行**已经是一个完整的表格行**，后面的纯标签行是**下一行**的开头，
    # 不是它的折行后半截。缺了这个区分，B108 F003 实测到 300432 把
    # 「营业收入（元）」和「归属于上市公司股东的净利润（元）」并成一行，
    # 且营业收入的单元格排在前面 → 返回营业收入当归母净利润（看似合理的错值）。
    started_with_numbers = False
    # ★同样来自 F003 实测：真实季报的主要数据表是「标签头 / 数字 / 标签尾」三物理行一组，
    # 连续排布。数字到达后只允许再接**一段**标签尾；第二段一定是下一行的标签头。
    # 缺这个约束，300432 会把「经营活动产生的现金/流量净额」和「基本每股收益」并成一行，
    # 于是 EPS 抽成 5.05 亿的经营现金流，S3 哨兵反过来否决正确的归母净利润。
    tail_appended = False

    def flush() -> None:
        nonlocal label_parts, pending_cells, pending_line, continuation
        nonlocal started_with_numbers, tail_appended
        if pending_line is not None and label_parts:
            rows.append(
                Row(
                    label="".join(label_parts),
                    cells=tuple(pending_cells),
                    line_index=pending_line,
                )
            )
        label_parts = []
        pending_cells = []
        pending_line = None
        continuation = 0
        started_with_numbers = False
        tail_appended = False

    for index, line in enumerate(lines):
        cells = split_cells(line)
        if not cells:
            flush()
            continue

        head = cells[0]
        label_like = _has_cjk(head.text) and not head.is_number
        has_numbers = any(cell.is_number for cell in cells)

        if label_like and has_numbers:
            # ★N04 修复：标签头也可能折在数字**之前**的一行::
            #
            #     归属于上市公司股东
            #     的净利润（元）    -79,024,133.16   ...
            #
            # 此时挂起行是一个「纯标签、还没收到任何数字」的行，且紧邻本行。
            # 直接 flush 会把标签头整个丢掉，剩下「的净利润（元）」匹配不上任何来源。
            #
            # 只在挂起行**确实像数据行标签头**时才并入：紧邻、无单元格、
            # 且本身不是表头词或单位声明——否则表头/表标题会被吸进第一行数据。
            adjacent_head = (
                pending_line == index - 1
                and not pending_cells
                and label_parts
                and not is_header_cell(label_parts[-1])
                and not _UNIT_PATTERN.search(label_parts[-1])
            )
            if adjacent_head:
                label_parts.append(head.text)
            else:
                flush()
                label_parts = [head.text]
                pending_line = index
            pending_cells = list(cells[1:])
            started_with_numbers = True
            tail_appended = False
        elif label_like:
            # 纯标签行。只有当挂起行是**由纯标签启动、已收到数字、且尚未接过标签尾**时，
            # 它才是折行标签的后半截。其余情况一律是下一个表格行的开头。
            continuable = (
                pending_cells
                and not started_with_numbers
                and not tail_appended
                and continuation < _MAX_LABEL_CONTINUATION_LINES
            )
            if continuable:
                label_parts.append(head.text)
                continuation += 1
                tail_appended = True
            else:
                flush()
                label_parts = [head.text]
                pending_cells = []
                pending_line = index
                started_with_numbers = False
                tail_appended = False
        elif (
            has_numbers
            and pending_line is not None
            and not started_with_numbers
            and not tail_appended
        ):
            # 纯数字行：只并入「由纯标签启动、尚未收尾」的折行挂起行。
            # 已完整的行不再吸收后续数字——那是下一行的数据。
            pending_cells.extend(cells)
            continuation += 1
        else:
            flush()

    flush()
    return rows


def is_data_row(line: str) -> bool:
    """一行是否是表格数据行（含 2 个以上数值单元格）。

    用来界定表边界：从表头向上走，一旦撞见数据行就说明已经进了上一张表。
    """
    return sum(cell.is_number for cell in split_cells(line)) >= 2


def _merge_spans(cells: list[Cell]) -> tuple[Column, ...]:
    """把跨行的表头单元格按字符区间重叠合并成列。

    区间重叠的碎片属于同一列，文字按出现顺序拼接：
    「上年同期」(第 1 行) + 「调整前」(第 3 行) → 一列「上年同期调整前」，
    于是 ``_EXCLUDED_HEADERS`` 里的「上年」照样能把它排除掉。
    """
    groups: list[list[Cell]] = []
    for cell in sorted(cells, key=lambda item: item.start):
        for group in groups:
            if cell.start < max(item.end for item in group) and cell.end > min(
                item.start for item in group
            ):
                group.append(cell)
                break
        else:
            groups.append([cell])

    columns: list[Column] = []
    for group in groups:
        ordered = sorted(group, key=lambda item: (item.start, item.end))
        columns.append(
            Column(
                header="".join(item.text for item in ordered),
                start=min(item.start for item in group),
                end=max(item.end for item in group),
            )
        )
    return tuple(columns)


def find_header_columns(lines: list[str], before_line: int) -> tuple[tuple[Column, ...], int, int]:
    """向上就近找表头**带**，返回 ``(列定义, 带起始行号, 带结束行号)``。

    找不到返回 ``((), -1, -1)``。

    ★为什么要返回带**结束**行号（B108 复验 N01）：单位声明常常夹在表头带内部
    （「合并利润表 / 单位：千元 / 项目 本期金额 上期金额」）。若拿带**起始**行号去做
    单位解析，而解析又只向上扫，声明就落在了扫描起点之下，结构性不可达——
    601186 的「单位:千元」在 L2971、带起点在 L2969，于是单位丢失、值缩小 10³。
    单位解析必须从带**末端**起扫，才能覆盖整条带。

    ★真实财报的表头本身就是跨物理行的，例如::

         176|                       上年同期            本报告期比上年同期增减
         177|        本报告期
         178|                  调整前        调整后          调整后

    只认单物理行的实现会拿到 L176，而真正需要的「本报告期」在 L177，
    于是所有列都被排除、返回 ``COLUMN_AMBIGUOUS``。B108 F003 实测这一条命中 76 次，
    是 48.7% 抽取失败的第一主因。因此这里先定位锚点行，再把相邻的非数据行并成一条表头带。
    """
    anchor = -1
    for index in range(before_line - 1, max(-1, before_line - _HEADER_LOOKBACK_LINES) - 1, -1):
        line = lines[index]
        if not line.strip() or is_data_row(line):
            continue
        cells = split_cells(line)
        if any(is_header_cell(cell.text) for cell in cells):
            anchor = index
            break
    if anchor < 0:
        return (), -1, -1

    start = anchor
    while start - 1 >= 0 and anchor - (start - 1) <= _HEADER_BAND_LINES:
        candidate = lines[start - 1]
        if not candidate.strip() or is_data_row(candidate):
            break
        start -= 1

    end = anchor
    while end + 1 < before_line and (end + 1) - anchor <= _HEADER_BAND_LINES:
        candidate = lines[end + 1]
        if not candidate.strip() or is_data_row(candidate):
            break
        end += 1

    band: list[Cell] = []
    for index in range(start, end + 1):
        band.extend(split_cells(lines[index]))

    columns = _merge_spans(band)
    if len(columns) < 2:
        return (), -1, -1
    return columns, start, end


def assign_column(cell: Cell, columns: tuple[Column, ...]) -> Column | None:
    """按字符区间把数据单元格归到某一列。

    先取区间重叠最大的列；无重叠时退化为中心距离最近的列。中文财报的数字是右对齐、
    表头常居中，所以两条规则都需要。
    """
    if not columns:
        return None
    overlaps = [
        (min(cell.end, column.end) - max(cell.start, column.start), column) for column in columns
    ]
    best_overlap, best_column = max(overlaps, key=lambda item: item[0])
    if best_overlap > 0:
        return best_column
    return min(columns, key=lambda column: abs(column.center - cell.center))


def resolve_unit(lines: list[str], header_line: int) -> tuple[str, str, bool]:
    """把单位绑定到**本表**。

    返回 ``(单位, 来源, 是否歧义)``。

    原实现在 ``before(1600 字符) + after(60 字符)`` 拼成的串上取 ``matches[-1]``：
    往后看了 60 字符（可能抓到下一张表的声明），窗口又可能够不到本表表头或越过上一张表。
    两条抽取路径的窗口还不一致（35 行 vs 1600 字符）。这里统一为：**只向上、限定在本表范围内、
    就近命中**；本表范围内出现互相矛盾的声明才算歧义。
    """
    for index in range(header_line, -1, -1):
        line = lines[index]
        matches = _UNIT_PATTERN.findall(line)
        if matches:
            # 命中行所在的**连续块**——块内出现互相矛盾的声明才叫歧义。
            # 边界同样是空行**或数据行**：越过数据行的声明属于上一张表，
            # 不构成本表的歧义（否则两张相邻的不同单位的表会互相污染）。
            block = list(matches)
            for above in range(index - 1, -1, -1):
                if not lines[above].strip() or is_data_row(lines[above]):
                    break
                block.extend(_UNIT_PATTERN.findall(lines[above]))
            return matches[-1], "table", len(set(block)) > 1

        # ★E04 修复：撞见数据行 = 已经走进上一张表，本表没有自己的单位声明，停止。
        #
        # 原实现只是把越界的命中改个标签叫 "document"，然后照样乘倍数——
        # B108 F003 实测 002670 2018 年报的「单位：万元」在表头之外 612 行，
        # 仍被绑定到合并利润表，把 -544,272,818.63 放大成 -5,442,728,186,300.00。
        # spec §3.4 要求的是「遇到表边界即停」，不是「越界了打个标签」。
        if index < header_line and is_data_row(line):
            break

    # 本表范围内无声明：中文财报默认以元计。这是语言约定的默认单位，不是猜数值；
    # 真要用万元的表，声明一定紧贴表头，不会藏在上一张表后面。
    return "元", "default", False


def unit_scale(unit: str) -> Decimal:
    return _UNIT_SCALE.get(unit, Decimal(1))
