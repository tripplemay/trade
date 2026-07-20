"""B109 F002 — as-of resolver（纯逻辑，不联网）。

语义（B109 F001 探针实测裁定）::

    resolve(ts_code, end_date, formation_date)
      = 取 f_ann_date <= formation_date 的行中 f_ann_date 最大的一条

依据：410 个已知修订中 **98.8%** 可用该语义正确还原当时可见的版本；
修正相对首版的滞后 **100% 为正**（中位 244 天），不存在会破坏 as-of 查询的时间倒挂。

**上游 handoff 报告 §4.4/§5 的重装设计**（`filing_version` + `financial_fact_version`
+ 版本链 + UPSERT/RETRACT + 追加式 QA decision + 三时钟 resolver）**在本数据源上不必要**——
Tushare 的 `f_ann_date` 已经承载了「市场可知时间」这一轴，而修订率只有 0.47%–0.88%。

但「轻量」不等于「可以省掉失败码」：剩下的 1.2% 无法按 `f_ann_date` 分辨先后，
必须 fail closed（见 :func:`resolve_as_of`）。
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from scripts.research.ashare_pit.codes import (
    FactStatus,
    FactVersion,
    ResolvedFact,
)


def to_decimal(value: object) -> Decimal | None:
    """转 Decimal。上游报告 §6 要求全程 Decimal，最终导出前才转浮点。"""
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return None if result.is_nan() else result


def resolve_as_of(
    versions: Iterable[FactVersion],
    formation_date: str,
) -> ResolvedFact:
    """还原 ``formation_date`` 当天市场可见的那一版事实。

    三条硬规则：

    1. **只看 ``f_ann_date``**，不看 ``ann_date``（修正行的 ``ann_date`` 与首版相同）。
    2. **同一 ``f_ann_date`` 上出现互相矛盾的值 → fail closed**，返回
       ``FACT_VERSION_AMBIGUOUS``。★禁止按行序、抓取顺序或 ``update_flag``
       任选一条（上游禁令 #13）——那正是「静默错值」的来源。
    3. 形成日之后的版本**不参与取值**，但要在 ``superseded_later`` 里暴露出来。
    """
    ordered = sorted(versions, key=lambda item: (item.f_ann_date, item.ts_code))
    if not ordered:
        return ResolvedFact(
            status=FactStatus.FACT_MISSING,
            value=None,
            selected=None,
            formation_date=formation_date,
            candidates=(),
        )

    visible = tuple(item for item in ordered if item.f_ann_date <= formation_date)
    if not visible:
        # 形成日当时尚未披露——这是**经济事实**（市场当时确实不知道），
        # 不是数据缺失，覆盖漏斗里必须与 FACT_MISSING 分开计数。
        return ResolvedFact(
            status=FactStatus.NOT_YET_PUBLISHED,
            value=None,
            selected=None,
            formation_date=formation_date,
            candidates=(),
        )

    latest_known = visible[-1].f_ann_date
    winners = [item for item in visible if item.f_ann_date == latest_known]
    distinct = {item.value for item in winners}

    superseded_later = any(item.f_ann_date > formation_date for item in ordered)

    if len(distinct) > 1:
        return ResolvedFact(
            status=FactStatus.FACT_VERSION_AMBIGUOUS,
            value=None,
            selected=None,
            formation_date=formation_date,
            candidates=visible,
            superseded_later=superseded_later,
        )

    return ResolvedFact(
        status=FactStatus.RESOLVED,
        value=winners[0].value,
        selected=winners[0],
        formation_date=formation_date,
        candidates=visible,
        superseded_later=superseded_later,
    )


def build_versions(rows: Iterable[dict[str, object]]) -> list[FactVersion]:
    """把 `income_vip` 的原始行规范化为 :class:`FactVersion`。

    缺 ``f_ann_date`` 或缺值的行**直接丢弃**——没有可知时间的事实无法参与 as-of 查询。
    丢弃数量由调用方统计并披露（H4），本函数不静默吞掉。
    """
    versions: list[FactVersion] = []
    for row in rows:
        f_ann_date = str(row.get("f_ann_date") or "").strip()
        value = to_decimal(row.get("n_income_attr_p"))
        if not f_ann_date or value is None:
            continue
        versions.append(
            FactVersion(
                ts_code=str(row.get("ts_code") or ""),
                end_date=str(row.get("end_date") or ""),
                f_ann_date=f_ann_date,
                ann_date=str(row.get("ann_date") or ""),
                update_flag=str(row.get("update_flag") or ""),
                value=value,
            )
        )
    return versions


def dropped_row_count(rows: list[dict[str, object]], versions: list[FactVersion]) -> int:
    """被 :func:`build_versions` 丢弃的行数——供覆盖报告显式披露，不得静默。"""
    return len(rows) - len(versions)
