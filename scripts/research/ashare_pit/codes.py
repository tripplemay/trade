"""B109 F002 — Tushare PIT 数据层的结构化状态与失败码。

沿用 B108 的原则：**抽不准就说抽不准，不返回猜测值。** 上游报告 §13 要求
所有失败以可枚举的码呈现，禁止只输出自由文本。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class FactStatus(StrEnum):
    """一次 as-of 解析的终态。只有 ``RESOLVED`` 允许下游当作可用事实。"""

    RESOLVED = "RESOLVED"
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    FACT_VERSION_AMBIGUOUS = "FACT_VERSION_AMBIGUOUS"
    FACT_MISSING = "FACT_MISSING"


class MarketCapStatus(StrEnum):
    """分母状态。"""

    RESOLVED = "RESOLVED"
    TOTAL_MARKET_CAP_MISSING = "TOTAL_MARKET_CAP_MISSING"
    MARKET_CAP_IDENTITY_FAILED = "MARKET_CAP_IDENTITY_FAILED"
    NON_POSITIVE_MARKET_CAP = "NON_POSITIVE_MARKET_CAP"


@dataclass(frozen=True)
class FactVersion:
    """一条财务事实版本。对应 `income_vip` 的一行。

    ``f_ann_date``（实际公告日期）是**唯一**的可知时间来源。
    ★不得用 ``ann_date`` 代替：修正行的 ``ann_date`` 与首版相同，
    用它做 as-of 比较会把修正值错误地判为「首版当时就可见」。
    """

    ts_code: str
    end_date: str
    f_ann_date: str
    ann_date: str
    update_flag: str
    value: Decimal


@dataclass(frozen=True)
class ResolvedFact:
    """as-of 解析结果。``value`` 非 None 当且仅当 status 为 ``RESOLVED``。"""

    status: FactStatus
    value: Decimal | None
    selected: FactVersion | None
    formation_date: str
    candidates: tuple[FactVersion, ...]
    """形成日当时可见的全部版本（`f_ann_date <= formation_date`），供 lineage 追溯。"""

    superseded_later: bool = False
    """该事实在形成日**之后**是否还有更新版本。

    这不影响本次取值的正确性（as-of 就该返回当时那一版），但必须暴露出来——
    下游做「修订不变性」检查和覆盖披露时需要知道哪些点位后来被改过。
    """

    @property
    def is_usable(self) -> bool:
        return self.status is FactStatus.RESOLVED
