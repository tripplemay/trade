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
from datetime import date
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
    """TTM 的结构化状态。★每一种「算不出来」都必须能和别的区分开。

    ★为什么 ``COMPONENT_*`` 拆成三个而不是一个 ``COMPONENT_UNRESOLVED``：合并会把
    「数据缺陷」读成「经济事实」，也会把「我们窗口开小了」读成「数据缺失」。实测
    FY2021 有 5 只公司从无年报（全部是强制退市名）——那是数据缺陷，与「新股还没
    四个季度」性质完全不同，与「当时确实还没披露」更是相反。
    """

    RESOLVED = "RESOLVED"
    #: 形成日看不到该证券的任何定期报告（IPO 前 / 早于数据起点）。
    NO_VISIBLE_REPORT = "NO_VISIBLE_REPORT"
    #: 最新可见期同一 f_ann_date 下有多个不同值（B109 FACT_VERSION_AMBIGUOUS）。
    #: ★不得退到更早的期次假装成功——静默降级正是错值来源。
    ANCHOR_AMBIGUOUS = "ANCHOR_AMBIGUOUS"
    #: 有记录但 f_ann_date > 形成日：**当时市场真的不知道**。这是合法的 PIT 不可得。
    COMPONENT_NOT_YET_PUBLISHED = "COMPONENT_NOT_YET_PUBLISHED"
    #: 该证券上市后的某个必需期**根本没有行** = 数据缺陷（或公司未按期披露）。
    COMPONENT_MISSING = "COMPONENT_MISSING"
    #: 分量自身版本歧义（同 f_ann_date 多值）。fail-closed 的代价，不是「缺数据」。
    COMPONENT_AMBIGUOUS = "COMPONENT_AMBIGUOUS"
    #: 必需期早于该证券上市日 = 上市历史不足四个连续单季。**禁止**季度年化填补。
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    #: ★必需期次不在本次抓取范围内 —— 这是**我们的覆盖缺陷**，不是数据特征。
    #: 与 COMPONENT_MISSING 混为一谈会把抓取 bug 伪装成「数据源的固有覆盖限制」，
    #: 且只打早年（早年迟报多、锚点更常向后滑）→ 直接放大覆盖污染项。
    PERIOD_NOT_FETCHED = "PERIOD_NOT_FETCHED"
    #: 必需期不连续（元数据层判据，不看数值）。
    PERIOD_NOT_CONTIGUOUS = "PERIOD_NOT_CONTIGUOUS"
    #: R2：累计差分出的单季与 ``report_type=2`` 单季直报不符 = **已知错值**。
    CUMULATIVE_BASIS_BREAK = "CUMULATIVE_BASIS_BREAK"
    #: 两式不一致。见模块 docstring：精确算术下这只可能来自实现 bug。
    EQUIVALENCE_MISMATCH = "EQUIVALENCE_MISMATCH"
    #: 非公历财年 → 累计期不可比（handoff §6：财年变更返回 null + 原因码）。
    #: 实测 A 股不可达（《会计法》第十一条强制日历年度），保留作断言分支。
    FISCAL_CALENDAR_IRREGULAR = "FISCAL_CALENDAR_IRREGULAR"
    #: 非人民币计价（实测 5,867/5,867 全 CNY，保留作断言分支）。
    CURRENCY_NOT_CNY = "CURRENCY_NOT_CNY"


class CrosscheckStatus(StrEnum):
    """R2 单季直报对拍的结果。★``UNAVAILABLE`` 不是通过。"""

    MATCH = "MATCH"
    BREAK = "BREAK"
    UNAVAILABLE = "CROSSCHECK_UNAVAILABLE"


#: 失败码优先级：数字越小越先报。★工程缺陷排在数据事实前面，
#: 这样自己的 bug 不会被淹没在「数据源就是这样」里。
_FAILURE_PRIORITY: dict[TTMStatus, int] = {
    TTMStatus.PERIOD_NOT_FETCHED: 0,
    TTMStatus.PERIOD_NOT_CONTIGUOUS: 1,
    TTMStatus.COMPONENT_AMBIGUOUS: 2,
    TTMStatus.COMPONENT_MISSING: 3,
    TTMStatus.COMPONENT_NOT_YET_PUBLISHED: 4,
    TTMStatus.INSUFFICIENT_HISTORY: 5,
}

#: R2 对拍容差：相对 0.1% + 绝对 1000 元。分位差与四舍五入不该触发 BREAK。
SQ_CROSSCHECK_REL_TOL = Decimal("0.001")
SQ_CROSSCHECK_ABS_TOL = Decimal("1000")

#: ``f_ann_date - ann_date`` 超过该天数即标记（**只标记，不 fail-closed**，见附录 D5）。
VINTAGE_GAP_MAX_DAYS = 90


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

    @property
    def vintage_gap_days(self) -> int | None:
        """``f_ann_date - ann_date``。>0 表示 Tushare 用重述版覆盖了原始 vintage。

        ★方向是「更晚才可见」= 保守，**不是前视泄漏**，故只披露不 fail-closed
        （见 `docs/specs/B110-frozen-conventions-addendum.md` D5）。
        """
        selected = self.resolved.selected
        if selected is None:
            return None
        left, right = _to_date(selected.f_ann_date), _to_date(selected.ann_date)
        if left is None or right is None:
            return None
        return (left - right).days


def _to_date(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except (ValueError, IndexError):
        return None


@dataclass(frozen=True)
class QuarterComponent:
    """四个单季分量之一。由 1-2 个累计事实差分而来，各自保留来源。"""

    role: str
    fiscal_year: int
    end_date: str
    value: Decimal | None
    minuend: CumulativeFact
    subtrahend: CumulativeFact | None
    #: R2：``report_type=2`` 单季直报（同样 as-of 解析，见 :func:`compute_ttm`）。
    direct: CumulativeFact | None = None

    @property
    def crosscheck_delta(self) -> Decimal | None:
        if self.value is None or self.direct is None or self.direct.value is None:
            return None
        return self.value - self.direct.value

    @property
    def crosscheck_status(self) -> CrosscheckStatus:
        delta = self.crosscheck_delta
        if delta is None or self.direct is None or self.direct.value is None:
            return CrosscheckStatus.UNAVAILABLE
        tolerance = abs(self.direct.value) * SQ_CROSSCHECK_REL_TOL + SQ_CROSSCHECK_ABS_TOL
        return CrosscheckStatus.MATCH if abs(delta) <= tolerance else CrosscheckStatus.BREAK

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
    list_date: str = "",
    currency: str = "CNY",
    direct_versions_by_period: Mapping[str, Iterable[FactVersion]] | None = None,
) -> TTMResult:
    """在 ``formation_date`` 这个知识截止日上算该证券的 PIT TTM 归母净利润。

    ``lookback_periods`` 是**本次抓取实际覆盖的报告期集合**（该语义很重要：
    必需期次落在集合外 → :attr:`TTMStatus.PERIOD_NOT_FETCHED`，是**我们的**覆盖缺陷；
    落在集合内但无记录 → :attr:`TTMStatus.COMPONENT_MISSING` 或
    :attr:`TTMStatus.INSUFFICIENT_HISTORY`，是数据事实）。

    ``versions_by_period`` 只含**这一只证券**的版本，按报告期分组。

    ``list_date`` 用于区分「上市前本就没有」（``INSUFFICIENT_HISTORY``）与
    「上市后该报的却没有」（``COMPONENT_MISSING``）。实测 FY2021 有 5 只**已上市**
    公司从无年报，全部是强制退市名——那是数据缺陷，不是新股历史不足。

    ``direct_versions_by_period`` 是 ``report_type=2`` 的单季直报版本（R2 对拍源）。
    ★它**同样走 as-of 解析**，不是拿最新值来判——否则「2015 年的一行是否被丢弃」
    会取决于 2023 年才发生的重述，那是把前视偷偷放进了**样本选择**里。
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

    # ★元数据门必须最先。这一层的判据全部是日期 / 报表类型 / 币种，
    # **没有任何一条看数值**（附录 §5 铁律：以数值为条件的置空一律禁止）。
    if fiscal_year_end != CALENDAR_FISCAL_YEAR_END:
        return failed(
            TTMStatus.FISCAL_CALENDAR_IRREGULAR,
            [f"FISCAL_YEAR_END:{fiscal_year_end}"],
        )
    if currency and currency != "CNY":
        return failed(TTMStatus.CURRENCY_NOT_CNY, [f"CURRENCY:{currency}"])

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
    if not _is_contiguous(required, anchor):
        return failed(
            TTMStatus.PERIOD_NOT_CONTIGUOUS,
            [f"PERIOD_NOT_CONTIGUOUS:{anchor}"],
            anchor=anchor,
        )
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
    codes: list[TTMStatus] = []
    for period in required:
        resolved = resolve_as_of(versions_by_period.get(period, ()), formation_date)
        cumulatives[period] = CumulativeFact(period, label_of(period), resolved)
        if not resolved.is_usable:
            code = _classify_component(resolved.status, period, list_date)
            codes.append(code)
            failures.append(f"{code}:{period}")

    ordered = tuple(cumulatives[period] for period in required)
    superseded = any(item.resolved.superseded_later for item in ordered)

    if codes:
        # ★优先级而非「先到先得」：工程缺陷与 fail-closed 代价排在数据事实之前，
        # 免得自己的 bug 被淹没在「数据源就是这样」里。
        status = min(codes, key=lambda item: _FAILURE_PRIORITY[item])
        return failed(status, failures, anchor=anchor, cumulatives=ordered, superseded=superseded)

    direct = _resolve_direct(direct_versions_by_period, required, formation_date)
    components = tuple(
        _build_component(fiscal_year, quarter, cumulatives, direct)
        for fiscal_year, quarter in quarter_window(anchor)
    )

    # R2：累计差分 vs report_type=2 单季直报。★这是分子唯一有鉴别力的交叉验证
    # （等价式是恒等式，见模块 docstring）。UNAVAILABLE 不算通过，单独计数。
    broken = [item for item in components if item.crosscheck_status is CrosscheckStatus.BREAK]
    if broken:
        return failed(
            TTMStatus.CUMULATIVE_BASIS_BREAK,
            [f"CUMULATIVE_BASIS_BREAK:{item.role}@{item.end_date}" for item in broken],
            anchor=anchor,
            cumulatives=ordered,
            components=components,
            superseded=superseded,
        )

    path_a = sum_single_quarters(components)
    path_b = equivalence_ttm(anchor, cumulatives)

    if path_a is None or path_b is None:
        return failed(
            TTMStatus.COMPONENT_MISSING,
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


def _is_contiguous(required: Sequence[str], anchor: str) -> bool:
    """必需期是否构成以锚点收尾的连续季度序列（纯元数据判据，不看数值）。"""
    expected = {period_of(year, quarter) for year, quarter in quarter_window(anchor)}
    expected |= {
        period_of(year, quarter - 1)
        for year, quarter in quarter_window(anchor)
        if quarter > 1
    }
    return set(required) == expected


def _classify_component(status: FactStatus, period: str, list_date: str) -> TTMStatus:
    """把 B109 的事实状态映射成 TTM 层的失败码。

    ★``FACT_MISSING`` 的两种含义必须分开：上市前本就没有（历史不足，良性）
    vs 上市后该报却没有（数据缺陷，实测 FY2021 有 5 只已上市公司从无年报）。
    """
    if status is FactStatus.NOT_YET_PUBLISHED:
        return TTMStatus.COMPONENT_NOT_YET_PUBLISHED
    if status is FactStatus.FACT_VERSION_AMBIGUOUS:
        return TTMStatus.COMPONENT_AMBIGUOUS
    if list_date and period < list_date:
        return TTMStatus.INSUFFICIENT_HISTORY
    return TTMStatus.COMPONENT_MISSING


def _resolve_direct(
    direct_versions_by_period: Mapping[str, Iterable[FactVersion]] | None,
    required: Sequence[str],
    formation_date: str,
) -> dict[str, CumulativeFact]:
    """R2 对拍源（``report_type=2`` 单季直报）的 as-of 解析。

    ★与主分量走**同一个** ``formation_date``。用最新值来判会让样本选择依赖未来。
    """
    if not direct_versions_by_period:
        return {}
    resolved: dict[str, CumulativeFact] = {}
    for period in required:
        versions = direct_versions_by_period.get(period)
        if not versions:
            continue
        fact = resolve_as_of(versions, formation_date)
        if fact.is_usable:
            resolved[period] = CumulativeFact(period, label_of(period), fact)
    return resolved


def _build_component(
    fiscal_year: int,
    quarter: int,
    cumulatives: Mapping[str, CumulativeFact],
    direct: Mapping[str, CumulativeFact],
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
        direct=direct.get(end_date),
    )


def step_without_filing(
    previous: TTMResult | None, current: TTMResult, *, previous_formation_date: str
) -> bool:
    """R1：TTM 变了，却没有任何一个分量在两个形成日之间**新可见**。

    ★这是本设计里**唯一直接检验 PIT 性**的检查（等价式是恒等式，见模块 docstring）。
    违反意味着：as-of 漏进了未来 vintage、锚点抖动、或缓存串期。
    """
    if previous is None or not previous.is_usable or not current.is_usable:
        return False
    if previous.value == current.value:
        return False
    for component in current.components:
        for source in component.sources:
            selected = source.resolved.selected
            if selected is None:
                continue
            if previous_formation_date < selected.f_ann_date <= current.formation_date:
                return False
    return True


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
                # D5：只披露不 fail-closed。>0 表示 Tushare 用重述版覆盖了原始 vintage，
                # 方向是「更晚才可见」= 保守。
                "source_vintage_gap_days": tuple(
                    item.vintage_gap_days for item in component.sources
                ),
                "vintage_gap_gt_max": any(
                    (gap := item.vintage_gap_days) is not None and gap > VINTAGE_GAP_MAX_DAYS
                    for item in component.sources
                ),
                # R2：分子唯一有鉴别力的交叉验证。UNAVAILABLE ≠ 通过。
                "sq_direct_rt2": component.direct.value if component.direct is not None else None,
                "crosscheck_delta": component.crosscheck_delta,
                "crosscheck_status": str(component.crosscheck_status),
                "revision_rate_exposure": component.revision_rate_exposure,
                "superseded_later": component.superseded_later,
                "anchor_end_date": result.anchor_end_date,
                "formula_version": result.formula_version,
            }
        )
    return rows
