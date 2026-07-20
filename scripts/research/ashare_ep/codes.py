"""B108 F001 — 结构化失败码与结果类型。

对齐上游报告 §13：抽取器禁止只输出自由文本，每一次失败都必须落在一个可枚举的码上。

设计要点（spec §3.2）：**冲突时返回 ``None`` 而非猜测值。**
研究场景下「自信的错值」比「缺值」危害大一个量级——缺值会被覆盖率统计抓到，
错值会一路流进面板。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class FailureCode(StrEnum):
    """spec §3.3 冻结的 7 个失败码。"""

    LABEL_NOT_FOUND = "LABEL_NOT_FOUND"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    COLUMN_AMBIGUOUS = "COLUMN_AMBIGUOUS"
    UNIT_AMBIGUOUS = "UNIT_AMBIGUOUS"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    SINGLE_SOURCE_UNCONFIRMED = "SINGLE_SOURCE_UNCONFIRMED"
    MAGNITUDE_IMPLAUSIBLE = "MAGNITUDE_IMPLAUSIBLE"


class Status(StrEnum):
    """交叉验证的终态。只有 ``CONFIRMED`` 允许下游当作可用事实。"""

    CONFIRMED = "CONFIRMED"
    SINGLE_SOURCE_UNCONFIRMED = "SINGLE_SOURCE_UNCONFIRMED"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    MAGNITUDE_IMPLAUSIBLE = "MAGNITUDE_IMPLAUSIBLE"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


@dataclass(frozen=True)
class SourceValue:
    """单个来源抽出的一个候选值，带完整取值依据（供人工裁定与 lineage）。"""

    source: str
    """来源标识：``S1`` = 合并利润表，``S2`` = 主要会计数据表。"""

    value: Decimal
    """规范化到 CNY 元的值（= ``raw_value * unit_scale``）。"""

    raw_value: Decimal
    """未乘单位倍数的原始数字。"""

    unit: str
    """绑定到本表的单位字面量（元 / 千元 / 万元 / 百万元）。"""

    unit_source: str
    """单位来源：``table`` = 本表范围内声明，``document`` = 文档级声明，
    ``default`` = 全文无声明按元。"""

    label: str
    """匹配到的完整标签（已做跨行重连）。"""

    column_header: str
    """选中列的表头文字——列选择依据，不是硬编码列号。"""

    line_index: int
    """物理行号，供人工翻原文定位。"""


@dataclass(frozen=True)
class CrossCheckResult:
    """交叉验证结果。

    ``value`` 非 None 当且仅当 status 为 ``CONFIRMED`` 或 ``SINGLE_SOURCE_UNCONFIRMED``。
    """

    status: Status
    value: Decimal | None
    failure_code: FailureCode | None
    sources: tuple[SourceValue, ...]
    notes: tuple[str, ...] = ()

    @property
    def is_confirmed(self) -> bool:
        return self.status is Status.CONFIRMED

    @property
    def is_usable(self) -> bool:
        """下游可用性。只有交叉确认过的值算数——单源值必须显式选择降级使用。"""
        return self.status is Status.CONFIRMED
