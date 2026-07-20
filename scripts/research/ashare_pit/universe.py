"""B109 F002 — PIT 证券宇宙（`stock_basic` 全状态 + `namechange`）。

**上游禁令 #11：禁止只拉 ``list_status=L``。** 只取当前在市的证券，等于让历史面板
的每个截面都只包含「活到今天」的公司——幸存者偏差直接烧进数据层，任何下游回测都
无法补救。三问探针实测退市名 **338 只**（263 只在 2013 年后），这不是可忽略的尾巴。

两条 as-of 语义：

1. **成分 as-of**：``list_date <= 形成日`` 且（未退市 或 ``delist_date > 形成日``）。
2. **名称 as-of**：从 `namechange` 取当时生效的那条。★``stock_basic.name`` 是
   **当前**名称，用它做历史 ST/*ST 判定是前视泄漏——一家 2015 年正常、2020 年被
   ST 的公司，会让 2015 年的截面凭空「预知」它日后会出事。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

# `stock_basic.list_status`。三者都要拉——D/P 缺席即幸存者偏差（禁令 #11）。
LISTED = "L"
DELISTED = "D"
PAUSED = "P"
ALL_LIST_STATUS: tuple[str, ...] = (LISTED, DELISTED, PAUSED)


class UniverseStatus(StrEnum):
    """一个证券在某个形成日的成分状态。"""

    IN_UNIVERSE = "IN_UNIVERSE"
    NOT_YET_LISTED = "NOT_YET_LISTED"
    ALREADY_DELISTED = "ALREADY_DELISTED"
    LIST_DATE_MISSING = "LIST_DATE_MISSING"
    """无上市日期——**不得默认纳入**。没有上市日就无法判断当时是否可交易。"""


@dataclass(frozen=True)
class Security:
    """一条证券主数据。``name`` 是**当前**名称，历史名称须走 :func:`name_as_of`。"""

    ts_code: str
    symbol: str
    name: str
    list_status: str
    list_date: str
    delist_date: str

    @property
    def is_delisted(self) -> bool:
        return self.list_status == DELISTED or bool(self.delist_date)


@dataclass(frozen=True)
class NameRecord:
    """一条 `namechange` 记录。``end_date`` 为空表示「至今仍生效」。"""

    ts_code: str
    name: str
    start_date: str
    end_date: str


def build_securities(rows: Iterable[dict[str, object]]) -> list[Security]:
    """规范化 `stock_basic` 行。缺 ``ts_code`` 的行丢弃，由调用方计数披露（H4）。"""
    securities: list[Security] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "").strip()
        if not ts_code:
            continue
        securities.append(
            Security(
                ts_code=ts_code,
                symbol=str(row.get("symbol") or "").strip(),
                name=str(row.get("name") or "").strip(),
                list_status=str(row.get("list_status") or "").strip(),
                list_date=str(row.get("list_date") or "").strip(),
                delist_date=str(row.get("delist_date") or "").strip(),
            )
        )
    return securities


def build_name_records(rows: Iterable[dict[str, object]]) -> list[NameRecord]:
    """规范化 `namechange` 行。缺 ``start_date`` 的行无法定位生效区间，丢弃。"""
    records: list[NameRecord] = []
    for row in rows:
        ts_code = str(row.get("ts_code") or "").strip()
        start_date = str(row.get("start_date") or "").strip()
        if not ts_code or not start_date:
            continue
        records.append(
            NameRecord(
                ts_code=ts_code,
                name=str(row.get("name") or "").strip(),
                start_date=start_date,
                end_date=str(row.get("end_date") or "").strip(),
            )
        )
    return records


def universe_status(security: Security, formation_date: str) -> UniverseStatus:
    """判定一个证券在 ``formation_date`` 的成分状态。

    ★退市判定用 ``delist_date > formation_date`` 而非 ``list_status``——
    ``list_status`` 是**当前**状态，一家 2021 年退市的公司今天标 ``D``，
    但它在 2015 年的截面里必须存在。
    """
    if not security.list_date:
        return UniverseStatus.LIST_DATE_MISSING
    if security.list_date > formation_date:
        return UniverseStatus.NOT_YET_LISTED
    if security.delist_date and security.delist_date <= formation_date:
        return UniverseStatus.ALREADY_DELISTED
    return UniverseStatus.IN_UNIVERSE


def universe_as_of(securities: Iterable[Security], formation_date: str) -> list[Security]:
    """``formation_date`` 当天真实可投的证券集合，**含日后退市者**。"""
    return sorted(
        (
            item
            for item in securities
            if universe_status(item, formation_date) is UniverseStatus.IN_UNIVERSE
        ),
        key=lambda item: item.ts_code,
    )


def name_as_of(
    records: Iterable[NameRecord],
    ts_code: str,
    formation_date: str,
) -> str | None:
    """``formation_date`` 当天该证券的**历史**名称；无覆盖记录返回 ``None``。

    返回 ``None`` 时调用方**不得回退到** ``stock_basic.name``——那是当前名称，
    回退即前视泄漏（见模块 docstring）。缺名称就按缺失处理并计入覆盖漏斗。
    """
    covering = [
        item
        for item in records
        if item.ts_code == ts_code
        and item.start_date <= formation_date
        and (not item.end_date or item.end_date >= formation_date)
    ]
    if not covering:
        return None
    # 区间重叠时取最晚生效的一条——同 as-of 语义（最近一次可知变更胜出）
    return max(covering, key=lambda item: item.start_date).name


def summarize_universe(
    securities: Iterable[Security],
    formation_date: str,
) -> dict[str, object]:
    """成分构成披露。**退市数必须单独可见**——它是幸存者偏差是否已消除的直接证据。"""
    items = list(securities)
    counts = {status: 0 for status in UniverseStatus}
    for item in items:
        counts[universe_status(item, formation_date)] += 1

    in_universe = [
        item
        for item in items
        if universe_status(item, formation_date) is UniverseStatus.IN_UNIVERSE
    ]
    return {
        "formation_date": formation_date,
        "total_securities": len(items),
        "in_universe": len(in_universe),
        # ★当时在市、但**此后**退市的数量。若为 0 而形成日又足够久远，
        # 几乎可以断定宇宙只拉了 list_status=L（禁令 #11 的自查探针）。
        "in_universe_delisted_later": sum(1 for item in in_universe if item.delist_date),
        **{f"count_{status.value.lower()}": counts[status] for status in UniverseStatus},
    }
