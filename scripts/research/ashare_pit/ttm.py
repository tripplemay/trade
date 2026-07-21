"""B110 F001 — PIT TTM 归母净利润（handoff §6 的**唯一算法**，纯逻辑，不联网）。

```text
SQ1 = C_Q1
SQ2 = C_H1 - C_Q1
SQ3 = C_Q3 - C_H1
SQ4 = C_FY - C_Q3
TTM = 最近连续四个 SQ 之和
```

本模块只做「分子」。分母走 :mod:`~scripts.research.ashare_pit.marketcap`（禁流通市值），
成分走 :mod:`~scripts.research.ashare_pit.universe`（全状态 L/D/P）。

## 三条不可协商的纪律

1. ★**四个分量各自独立 as-of**：每个累计期在**同一个** ``formation_date`` 上重新
   调用 B109 的 :func:`~scripts.research.ashare_pit.resolver.resolve_as_of`。混用不同
   知识截止日是最隐蔽的前视形态——TTM 里会混进当时还看不到的季度。
2. **fail-closed**：任一必需分量不可解析 → ``value is None`` + 结构化原因码。
   **禁止**用最新年报、线性插值、季度年化填补（handoff §6 明令）。
3. ★**负单季是有效经济事实**。累计值回落 = 单季亏损，不是数据错误。spec §3.4 要求
   负 TTM 主口径**不剔除**；一旦这里静默置空，「双口径」设计在实现层就被架空了。

## ★关于「等价式交叉验证」的诚实结论（必须随结果一同转述）

spec §3.1 要求同时算两条路径并比对：

- 路径 A：四个单季差分之和
- 路径 B（等价式）：``FY(y-1) + YTD(y) - YTD(y-1)``

**在 Decimal 精确算术下，当两条路径取自同一批 as-of 事实时，二者恒等**——路径 A 的
中间累计值全部望远镜相消，展开后逐项等于路径 B。:func:`sum_single_quarters` 与
:func:`equivalence_ttm` 的比对因此**不是对数据的独立验证**，它能抓到的是：

- TTM 窗口错位（锚点与四个单季不对齐）——最危险的一类实现 bug
- 路径 A 严格需要**更多**事实（Q1 锚点下 5 期 vs 等价式 3 期），少一期就 fail-closed，
  这正是「两式不一致 → 不得取其一」的操作含义
- 单位/币种混用、as-of 解析取到不同 vintage 等实现层错误

★**不得**把这项检查转述为「数据已交叉验证」。B109 审计器「可裁定样本仅 16.7% 而
一致率 100%」就是同型的自欺陷阱：分母被自己缩掉之后，一致率不再有信息量。
对数据的独立校验需要**外部真值锚**（巨潮原文 / 另一数据源），本批次不做。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from scripts.research.ashare_pit.codes import FactStatus, FactVersion, ResolvedFact
from scripts.research.ashare_pit.pipeline import REVISION_RATE_BY_REPORT_TYPE
from scripts.research.ashare_pit.resolver import resolve_as_of

#: 公式版本号——lineage 必须带上它，换算法后旧行才不会被误读为同口径（handoff §6）。
FORMULA_VERSION = "handoff-6.0/B110-F001"

#: A 股法定会计年度为公历年度，故报告期末只有这四个。
STANDARD_QUARTER_ENDS: tuple[str, ...] = ("0331", "0630", "0930", "1231")
CALENDAR_FISCAL_YEAR_END = "1231"

#: 报告期末 → B109 实测修订率所用的报表类型标签。
PERIOD_LABELS: dict[str, str] = {"0331": "Q1", "0630": "H1", "0930": "Q3", "1231": "FY"}


class TTMStatus(StrEnum):
    """TTM 的结构化状态。★每一种「算不出来」都必须能和别的区分开。"""

    RESOLVED = "RESOLVED"
    #: 形成日看不到该证券的任何定期报告（IPO 前 / 早于数据起点）。
    NO_VISIBLE_REPORT = "NO_VISIBLE_REPORT"
    #: 最新可见期同一 f_ann_date 下有多个不同值（B109 FACT_VERSION_AMBIGUOUS）。
    #: ★不得退到更早的期次假装成功——静默降级正是错值来源。
    ANCHOR_AMBIGUOUS = "ANCHOR_AMBIGUOUS"
    #: 必需的累计期存在记录但在形成日不可用（尚未披露 / 版本歧义）。
    COMPONENT_UNRESOLVED = "COMPONENT_UNRESOLVED"
    #: 必需的更早期次**根本没有记录** = 上市历史不足四个连续单季。
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    #: ★必需期次不在本次抓取范围内 —— 这是**我们的覆盖缺陷**，不是数据特征。
    #: 与 INSUFFICIENT_HISTORY 混为一谈会把抓取 bug 伪装成「新股历史不足」。
    PERIOD_NOT_FETCHED = "PERIOD_NOT_FETCHED"
    #: 两式不一致。见模块 docstring：精确算术下这只可能来自实现 bug。
    EQUIVALENCE_MISMATCH = "EQUIVALENCE_MISMATCH"
    #: 非公历财年 → 累计期不可比（handoff §6：财年变更返回 null + 原因码）。
    FISCAL_CALENDAR_IRREGULAR = "FISCAL_CALENDAR_IRREGULAR"


# --- 报告期算术 ---


def quarter_index(end_date: str) -> int | None:
    """``YYYYMMDD`` → 1..4；非标准期末返回 ``None``。"""
    try:
        return STANDARD_QUARTER_ENDS.index(end_date[4:]) + 1
    except (ValueError, IndexError):
        return None


def period_of(year: int, index: int) -> str:
    return f"{year:04d}{STANDARD_QUARTER_ENDS[index - 1]}"


def label_of(end_date: str) -> str:
    return PERIOD_LABELS.get(end_date[4:], "?")


def quarter_window(anchor_end_date: str) -> tuple[tuple[int, int], ...]:
    """以 ``anchor_end_date`` 收尾的**最近连续四个单季**，由近及远。

    返回 ``((fiscal_year, quarter_index), ...)``，跨年时自动回卷到上一财年。
    """
    index = quarter_index(anchor_end_date)
    if index is None:
        return ()
    year = int(anchor_end_date[:4])
    window: list[tuple[int, int]] = []
    for step in range(4):
        current, current_year = index - step, year
        while current <= 0:
            current += 4
            current_year -= 1
        window.append((current_year, current))
    return tuple(window)


def periods_required_for(anchor_end_date: str) -> tuple[str, ...]:
    """算出该锚点的 TTM 所**必需**的全部累计期（升序）。

    ★路径 A 需要的期次严格多于等价式：Q1 锚点下 A 需 5 期而等价式只需 3 期。
    少一期就 fail-closed，不得退化成等价式单独出数——这就是「不得取其一」。
    """
    index = quarter_index(anchor_end_date)
    if index is None:
        return ()
    year = int(anchor_end_date[:4])
    needed: set[str] = set()
    for fiscal_year, quarter in quarter_window(anchor_end_date):
        needed.add(period_of(fiscal_year, quarter))
        if quarter > 1:
            needed.add(period_of(fiscal_year, quarter - 1))
    # 等价式所需（是路径 A 的子集；显式并入，防止将来任一侧漂移后悄悄少拉数据）
    needed.add(anchor_end_date)
    if index != 4:
        needed.add(period_of(year - 1, 4))
        needed.add(period_of(year - 1, index))
    return tuple(sorted(needed))


# --- lineage 数据结构 ---


@dataclass(frozen=True)
class CumulativeFact:
    """一个累计期（C_Q1 / C_H1 / C_Q3 / C_FY）的 as-of 解析结果。"""

    end_date: str
    period_label: str
    resolved: ResolvedFact

    @property
    def value(self) -> Decimal | None:
        return self.resolved.value

    @property
    def is_usable(self) -> bool:
        return self.resolved.is_usable

    @property
    def revision_rate(self) -> float:
        """B109 实测的该报表类型修订率。FY 0.747% 是 Q1 0.073% 的 10.2 倍。"""
        return REVISION_RATE_BY_REPORT_TYPE.get(self.period_label, 0.0)


@dataclass(frozen=True)
class QuarterComponent:
    """四个单季分量之一。由 1-2 个累计事实差分而来，各自保留来源。"""

    role: str
    fiscal_year: int
    end_date: str
    value: Decimal | None
    minuend: CumulativeFact
    subtrahend: CumulativeFact | None

    @property
    def sources(self) -> tuple[CumulativeFact, ...]:
        if self.subtrahend is None:
            return (self.minuend,)
        return (self.minuend, self.subtrahend)

    @property
    def revision_rate_exposure(self) -> float:
        """★该分量吃到的**最高**修订率，不是平均。

        SQ4 = C_FY - C_Q3 直接吃 FY 的 0.747%；SQ1 只吃 Q1 的 0.073%。
        用混合平均披露会把「风险集中在一个分量上」这个最重要的结论抹平。
        """
        return max(item.revision_rate for item in self.sources)

    @property
    def superseded_later(self) -> bool:
        return any(item.resolved.superseded_later for item in self.sources)


@dataclass(frozen=True)
class TTMResult:
    ts_code: str
    formation_date: str
    status: TTMStatus
    value: Decimal | None
    anchor_end_date: str
    components: tuple[QuarterComponent, ...] = ()
    cumulatives: tuple[CumulativeFact, ...] = ()
    equivalence_value: Decimal | None = None
    failures: tuple[str, ...] = ()
    superseded_later: bool = False
    formula_version: str = FORMULA_VERSION
    #: 分量级别的修订率暴露，按 role。★不得聚合成单一数字。
    exposure_by_role: dict[str, float] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.status is TTMStatus.RESOLVED

    @property
    def report_lag_source(self) -> str:
        """用于新鲜度统计的期末——TTM 的右端点。"""
        return self.anchor_end_date


# --- 两条路径 ---


def sum_single_quarters(components: Iterable[QuarterComponent]) -> Decimal | None:
    """路径 A：四个单季之和。任一分量为 ``None`` 即整体为 ``None``。"""
    total = Decimal(0)
    count = 0
    for item in components:
        if item.value is None:
            return None
        total += item.value
        count += 1
    return total if count == 4 else None


def equivalence_ttm(
    anchor_end_date: str, cumulatives: Mapping[str, CumulativeFact]
) -> Decimal | None:
    """路径 B：``FY(y-1) + YTD(y) - YTD(y-1)``；年报锚点直接取 ``FY(y)``。"""
    index = quarter_index(anchor_end_date)
    if index is None:
        return None
    year = int(anchor_end_date[:4])
    if index == 4:
        anchor = cumulatives.get(anchor_end_date)
        return anchor.value if anchor is not None else None
    keys = (period_of(year - 1, 4), anchor_end_date, period_of(year - 1, index))
    values = [cumulatives[key].value if key in cumulatives else None for key in keys]
    if any(value is None for value in values):
        return None
    prior_fy, ytd, prior_ytd = values
    assert prior_fy is not None and ytd is not None and prior_ytd is not None
    return prior_fy + ytd - prior_ytd


# --- 主入口 ---


def compute_ttm(
    *,
    ts_code: str,
    formation_date: str,
    versions_by_period: Mapping[str, Iterable[FactVersion]],
    lookback_periods: Sequence[str],
    fiscal_year_end: str = CALENDAR_FISCAL_YEAR_END,
) -> TTMResult:
    """在 ``formation_date`` 这个知识截止日上算该证券的 PIT TTM 归母净利润。

    ``lookback_periods`` 是**本次抓取实际覆盖的报告期集合**（该语义很重要：
    必需期次落在集合外 → :attr:`TTMStatus.PERIOD_NOT_FETCHED`，是覆盖缺陷；
    落在集合内但无记录 → :attr:`TTMStatus.INSUFFICIENT_HISTORY`，是数据事实）。

    ``versions_by_period`` 只含**这一只证券**的版本，按报告期分组。
    """

    def failed(
        status: TTMStatus,
        failures: Sequence[str],
        *,
        anchor: str = "",
        cumulatives: tuple[CumulativeFact, ...] = (),
        equivalence: Decimal | None = None,
        components: tuple[QuarterComponent, ...] = (),
        superseded: bool = False,
    ) -> TTMResult:
        return TTMResult(
            ts_code=ts_code,
            formation_date=formation_date,
            status=status,
            value=None,
            anchor_end_date=anchor,
            components=components,
            cumulatives=cumulatives,
            equivalence_value=equivalence,
            failures=tuple(failures),
            superseded_later=superseded,
        )

    if fiscal_year_end != CALENDAR_FISCAL_YEAR_END:
        return failed(
            TTMStatus.FISCAL_CALENDAR_IRREGULAR,
            [f"FISCAL_YEAR_END:{fiscal_year_end}"],
        )

    fetched = {period for period in lookback_periods if quarter_index(period) is not None}
    if not fetched:
        return failed(TTMStatus.PERIOD_NOT_FETCHED, ["NO_STANDARD_PERIOD_IN_LOOKBACK"])

    # ★锚点搜索本身也是逐期独立 as-of。取**最新可见**期，而不是最新有记录的期。
    anchor: str | None = None
    anchor_fact: ResolvedFact | None = None
    for period in sorted(fetched, reverse=True):
        resolved = resolve_as_of(versions_by_period.get(period, ()), formation_date)
        if resolved.status in (FactStatus.RESOLVED, FactStatus.FACT_VERSION_AMBIGUOUS):
            anchor, anchor_fact = period, resolved
            break

    if anchor is None or anchor_fact is None:
        return failed(TTMStatus.NO_VISIBLE_REPORT, ["NO_VISIBLE_PERIOD"])
    if anchor_fact.status is FactStatus.FACT_VERSION_AMBIGUOUS:
        return failed(
            TTMStatus.ANCHOR_AMBIGUOUS,
            [f"{FactStatus.FACT_VERSION_AMBIGUOUS}:{anchor}"],
            anchor=anchor,
            cumulatives=(CumulativeFact(anchor, label_of(anchor), anchor_fact),),
            superseded=anchor_fact.superseded_later,
        )

    required = periods_required_for(anchor)
    not_fetched = [period for period in required if period not in fetched]
    if not_fetched:
        return failed(
            TTMStatus.PERIOD_NOT_FETCHED,
            [f"PERIOD_NOT_FETCHED:{period}" for period in not_fetched],
            anchor=anchor,
        )

    # ★每个必需累计期在同一 formation_date 上**各自独立**重新解析。
    cumulatives: dict[str, CumulativeFact] = {}
    failures: list[str] = []
    for period in required:
        resolved = resolve_as_of(versions_by_period.get(period, ()), formation_date)
        cumulatives[period] = CumulativeFact(period, label_of(period), resolved)
        if not resolved.is_usable:
            failures.append(f"{resolved.status}:{period}")

    ordered = tuple(cumulatives[period] for period in required)
    superseded = any(item.resolved.superseded_later for item in ordered)

    if failures:
        missing = [item for item in ordered if item.resolved.status is FactStatus.FACT_MISSING]
        # 全部失败都是「压根没这条记录」→ 上市历史不足；只要有一条是「有记录但当时看不到 /
        # 版本歧义」，就是 PIT 不可用，两者的下游含义完全不同。
        status = (
            TTMStatus.INSUFFICIENT_HISTORY
            if len(missing) == len(failures)
            else TTMStatus.COMPONENT_UNRESOLVED
        )
        return failed(status, failures, anchor=anchor, cumulatives=ordered, superseded=superseded)

    components = tuple(
        _build_component(fiscal_year, quarter, cumulatives)
        for fiscal_year, quarter in quarter_window(anchor)
    )
    path_a = sum_single_quarters(components)
    path_b = equivalence_ttm(anchor, cumulatives)

    if path_a is None or path_b is None:
        return failed(
            TTMStatus.COMPONENT_UNRESOLVED,
            ["PATH_A_NULL" if path_a is None else "PATH_B_NULL"],
            anchor=anchor,
            cumulatives=ordered,
            components=components,
            equivalence=path_b,
            superseded=superseded,
        )
    if path_a != path_b:
        # ★不得取其一。见模块 docstring：精确算术下这只可能是实现 bug，必须炸出来。
        return failed(
            TTMStatus.EQUIVALENCE_MISMATCH,
            [f"EQUIVALENCE_MISMATCH:{path_a}!={path_b}"],
            anchor=anchor,
            cumulatives=ordered,
            components=components,
            equivalence=path_b,
            superseded=superseded,
        )

    return TTMResult(
        ts_code=ts_code,
        formation_date=formation_date,
        status=TTMStatus.RESOLVED,
        value=path_a,
        anchor_end_date=anchor,
        components=components,
        cumulatives=ordered,
        equivalence_value=path_b,
        failures=(),
        superseded_later=superseded,
        exposure_by_role={item.role: item.revision_rate_exposure for item in components},
    )


def _build_component(
    fiscal_year: int, quarter: int, cumulatives: Mapping[str, CumulativeFact]
) -> QuarterComponent:
    end_date = period_of(fiscal_year, quarter)
    minuend = cumulatives[end_date]
    subtrahend = cumulatives[period_of(fiscal_year, quarter - 1)] if quarter > 1 else None
    if minuend.value is None or (subtrahend is not None and subtrahend.value is None):
        value = None
    elif subtrahend is None:
        value = minuend.value
    else:
        assert subtrahend.value is not None
        value = minuend.value - subtrahend.value
    return QuarterComponent(
        role=f"SQ{quarter}",
        fiscal_year=fiscal_year,
        end_date=end_date,
        value=value,
        minuend=minuend,
        subtrahend=subtrahend,
    )


def component_lineage(result: TTMResult) -> list[dict[str, object]]:
    """``ep_feature_component``：逐条记录四个分量各自的事实版本与风险。

    handoff §7 要求「另建 ep_feature_component，逐条记录四个单季事实版本」；
    spec §3.1 追加要求它必须能**区分四分量各自风险**（B109 实测 FY 是 Q1 的 10.2 倍）。
    """
    if result.status is not TTMStatus.RESOLVED:
        return []
    rows: list[dict[str, object]] = []
    for component in result.components:
        selected = [
            item.resolved.selected
            for item in component.sources
            if item.resolved.selected is not None
        ]
        rows.append(
            {
                "feature_id": f"{result.ts_code}|{result.formation_date}",
                "ts_code": result.ts_code,
                "formation_date": result.formation_date,
                "component_role": component.role,
                "fiscal_year": component.fiscal_year,
                "component_end_date": component.end_date,
                "value": component.value,
                "source_end_dates": tuple(item.end_date for item in component.sources),
                "source_period_labels": tuple(item.period_label for item in component.sources),
                "source_f_ann_dates": tuple(item.f_ann_date for item in selected),
                "source_ann_dates": tuple(item.ann_date for item in selected),
                "source_update_flags": tuple(item.update_flag for item in selected),
                "source_candidate_counts": tuple(
                    len(item.resolved.candidates) for item in component.sources
                ),
                "revision_rate_exposure": component.revision_rate_exposure,
                "superseded_later": component.superseded_later,
                "anchor_end_date": result.anchor_end_date,
                "formula_version": result.formula_version,
            }
        )
    return rows
