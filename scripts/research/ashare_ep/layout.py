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

# 标签跨行最多向后并入几行（bug ④）。给一个小上限防止把相邻行误并。
_MAX_LABEL_CONTINUATION_LINES = 3

# 单位向上就近搜索时，视为「本表范围」的行数上限（bug ②）。
# 超出即认为跨到了上一张表，只能降级为文档级声明。
_TABLE_SCOPE_LOOKBACK_LINES = 12


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

    def flush() -> None:
        nonlocal label_parts, pending_cells, pending_line, continuation
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

    for index, line in enumerate(lines):
        cells = split_cells(line)
        if not cells:
            flush()
            continue

        head = cells[0]
        label_like = _has_cjk(head.text) and not head.is_number
        has_numbers = any(cell.is_number for cell in cells)

        if label_like and has_numbers:
            # 一个自带数值的新行——先结掉上一行
            flush()
            label_parts = [head.text]
            pending_cells = list(cells[1:])
            pending_line = index
        elif label_like:
            # 纯标签行。只有当挂起行**已经收到数字**时，它才可能是折行标签的后半截；
            # 否则前一个挂起行不过是个没有数值的标题行（「单位：元」「项目」「合并利润表」），
            # 应当丢弃重开——否则标题会被一路粘进标签里。
            if pending_cells and continuation < _MAX_LABEL_CONTINUATION_LINES:
                label_parts.append(head.text)
                continuation += 1
            else:
                flush()
                label_parts = [head.text]
                pending_cells = []
                pending_line = index
        elif has_numbers and pending_line is not None:
            # 纯数字行：并入当前挂起的标签
            pending_cells.extend(cells)
            continuation += 1
        else:
            flush()

    flush()
    return rows


def find_header_columns(lines: list[str], before_line: int) -> tuple[tuple[Column, ...], int]:
    """向上就近找表头行，返回 ``(列定义, 表头行号)``。找不到返回 ``((), -1)``。

    「就近」很重要：一份季报里有多张表，用错表头就会用错列语义。
    表头行号还要交给 :func:`resolve_unit` 界定「本表范围」——单位声明贴着表头走，
    不贴着数据行走，所以必须用表头行号而不是数据行号做锚点。
    """
    for index in range(before_line - 1, max(-1, before_line - 40) - 1, -1):
        cells = split_cells(lines[index])
        if len(cells) < 2:
            continue
        if sum(any(token in cell.text for token in _HEADER_TOKENS) for cell in cells) >= 2:
            return tuple(Column(cell.text, cell.start, cell.end) for cell in cells), index
    return (), -1


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
        matches = _UNIT_PATTERN.findall(lines[index])
        if not matches:
            continue

        # 命中行所在的**连续非空块**——块内出现互相矛盾的声明才叫歧义。
        # 隔着空行的上一张表的声明不参与：那是另一张表的事。
        block = list(matches)
        for above in range(index - 1, -1, -1):
            if not lines[above].strip():
                break
            block.extend(_UNIT_PATTERN.findall(lines[above]))

        unit = matches[-1]
        origin = "table" if header_line - index <= _TABLE_SCOPE_LOOKBACK_LINES else "document"
        return unit, origin, len(set(block)) > 1

    # 全文无声明：中文财报默认以元计。这不是猜数值，是语言约定的默认单位；
    # 若默认错了，S1/S2 分处不同表、单位声明各自独立，交叉验证会抓到。
    return "元", "default", False


def unit_scale(unit: str) -> Decimal:
    return _UNIT_SCALE.get(unit, Decimal(1))
