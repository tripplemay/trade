"""B110 F002 — 月度前向收益（纯逻辑，不联网）。

E/P 是排序变量，**前向收益是被解释变量**。分组收益、基准、IC 全部建立在这一层上，
所以这里错了整批作废。

## 复权（★第一号静默错误的防线）

``daily_basic.close`` 是**不复权**收盘价，跨月直接相除会把送转、分红当成暴跌。
复权价 = ``close × adj_factor``：

```text
ret(t → t+1) = (close_{t+1} × adjf_{t+1}) / (close_t × adjf_t) - 1
```

已对拍 Tushare 官方 ``pro_bar(adj='hfq')``：`603288.SH` 2024-05-31→06-28 本式
−0.019239 vs 官方 −0.019243（残差 ~1e-5 来自因子四位小数舍入）。这是**含分红
再投资的全收益口径**。实测 2024-06 单月有 51% 的股票除权除息。

★**两条价格路径必须物理隔离**：市值分母用**裸价**（禁令 #8；复权价会破坏
``close × total_share ≈ total_mv`` 恒等式），收益用**复权价**。本模块只碰后者，
:class:`PricePoint` 因此同时保留两者并把 :attr:`PricePoint.adjusted` 单独命名。

## ★停牌与退市：缺行不是缺失值

实测停牌股在 ``daily_basic`` / ``daily`` 里**完全没有行**（不是 vol=0）。
``suspend_d`` 不是判据（含盘中停牌）；``adj_factor`` 有行也不代表可交易
（`600213.SH` 退市 20241017，因子一直派发到 20250814）。**唯一权威信号是
``daily_basic`` 里有没有这一行。**

## ★★偏离设计备忘的一处判断：停牌期的收益记在哪个月

备忘建议「停牌月记 r=0，恢复当月一次性入账」。本模块**不这么做**，改为
**把收益一路算到下一个有价的网格日**，并记录实际跨越的月数 ``horizon_months``。

理由是偏差方向：截面框架里，停牌股在随后各月**没有价格因而进不了任何组合**，
「r=0」那笔亏损于是**永远不会落到任何组合上**——系统性地把崩塌从结果里抹掉，
方向明确偏乐观，正是推向 GO 那一侧。把它记在**选中它的那个月**，既能让亏损真的
落地，又把它归因给做出选择的那个 E/P 信号。代价是该笔观测不是严格的 1 个月收益，
故 ``horizon_months`` 必须逐条留痕并在漏斗里披露分布。

## ★退市终值（附录 D6，用户 2026-07-21 冻结）

终值 = **最后一个实际成交日的复权价**（崩塌已经在数据里：实测退市名最后 20 个
交易日收益中位 −63.7%，最后 250 日 −85.8%）。其上叠加残值 stub 敏感带
``{0.00, −0.30, −1.00}``，**三档全跑并排披露**。

★**退市 ≠ 归零**：实测吸收合并型退市为正收益（`600832` +144%）。单用 −100% 一定是错的。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from scripts.research.ashare_pit.resolver import to_decimal

#: 附录 D6 冻结的残值敏感带。★三档全跑并排披露，任一档跨越判据边界 → INCONCLUSIVE。
DELIST_STUBS: tuple[Decimal, ...] = (Decimal("0.00"), Decimal("-0.30"), Decimal("-1.00"))


class FwdReturnStatus(StrEnum):
    FWD_OK = "FWD_OK"
    #: 形成日有价、次月末无价、**日后仍有行情** → 算到下一个有价网格日（见模块 docstring）。
    FWD_FROZEN_SUSPENDED = "FWD_FROZEN_SUSPENDED"
    #: 形成日有价、此后网格上再无行情 → 用退市终值 + stub 敏感带。
    FWD_TERMINAL_DELIST = "FWD_TERMINAL_DELIST"
    #: ★形成日本身无价（停牌 / 缺行）→ 不入任何分位。实测 2015-07 缺行率高达 18.13%。
    FWD_NO_FORMATION_PRICE = "FWD_NO_FORMATION_PRICE"
    #: 兜底码，**应恒为 0**。非 0 即有未归类流失（H4）。
    FWD_MISSING = "FWD_MISSING"


@dataclass(frozen=True)
class PricePoint:
    ts_code: str
    trade_date: str
    #: ★裸价。市值分母用它，收益**不得**用它。
    close: Decimal
    adj_factor: Decimal

    @property
    def adjusted(self) -> Decimal:
        return self.close * self.adj_factor

    @property
    def is_positive(self) -> bool:
        return self.close > 0 and self.adj_factor > 0


@dataclass(frozen=True)
class ForwardReturn:
    ts_code: str
    formation_date: str
    status: FwdReturnStatus
    #: 主披露值 = stub 0.00 档。三档全部在 :attr:`by_stub`。
    value: Decimal | None = None
    #: ``str(stub) -> 收益``。非退市观测三档相同（stub 只作用于退市终值之后）。
    by_stub: dict[str, Decimal | None] = field(default_factory=dict)
    exit_date: str = ""
    #: 实际跨越的网格月数。★>1 表示停牌冻结，必须披露分布。
    horizon_months: int = 1
    entry: PricePoint | None = None
    exit_point: PricePoint | None = None

    @property
    def is_usable(self) -> bool:
        return self.status is not FwdReturnStatus.FWD_NO_FORMATION_PRICE and self.value is not None


def build_price_point(row: Mapping[str, object], *, adj_factor: object) -> PricePoint | None:
    """从一行 ``daily_basic`` + 对应复权因子造价格点。

    任一字段不可解析返回 ``None``——返回 ``None`` 的行**必须被调用方计数**（H4）。
    """
    close = to_decimal(row.get("close"))
    factor = to_decimal(adj_factor)
    if close is None or factor is None:
        return None
    return PricePoint(
        ts_code=str(row.get("ts_code", "")).strip(),
        trade_date=str(row.get("trade_date", "")).strip(),
        close=close,
        adj_factor=factor,
    )


def _ratio(entry: PricePoint, exit_point: PricePoint) -> Decimal | None:
    if not entry.is_positive or not exit_point.is_positive:
        return None
    return exit_point.adjusted / entry.adjusted - Decimal(1)


def forward_return(
    *,
    ts_code: str,
    formation_date: str,
    grid_ahead: Sequence[str],
    prices_by_date: Mapping[str, Mapping[str, PricePoint]],
    terminal: PricePoint | None = None,
) -> ForwardReturn:
    """形成日 → 下一个有价网格日的复权收益，缺任一端都不猜。

    ``grid_ahead`` 是形成日**之后**的网格交易日（由近及远），
    ``prices_by_date[date][ts_code]`` 是该网格日的价格快照。
    """
    entry = prices_by_date.get(formation_date, {}).get(ts_code)
    if entry is None:
        return ForwardReturn(
            ts_code=ts_code,
            formation_date=formation_date,
            status=FwdReturnStatus.FWD_NO_FORMATION_PRICE,
            by_stub={str(stub): None for stub in DELIST_STUBS},
        )

    for offset, exit_date in enumerate(grid_ahead, start=1):
        exit_point = prices_by_date.get(exit_date, {}).get(ts_code)
        if exit_point is None:
            continue
        value = _ratio(entry, exit_point)
        status = (
            FwdReturnStatus.FWD_OK if offset == 1 else FwdReturnStatus.FWD_FROZEN_SUSPENDED
        )
        return ForwardReturn(
            ts_code=ts_code,
            formation_date=formation_date,
            status=status if value is not None else FwdReturnStatus.FWD_MISSING,
            value=value,
            by_stub={str(stub): value for stub in DELIST_STUBS},
            exit_date=exit_date,
            horizon_months=offset,
            entry=entry,
            exit_point=exit_point,
        )

    # 网格上再无行情 → 退市终局。★崩塌已经在最后成交价里，别丢掉它。
    if terminal is None:
        return ForwardReturn(
            ts_code=ts_code,
            formation_date=formation_date,
            status=FwdReturnStatus.FWD_MISSING,
            by_stub={str(stub): None for stub in DELIST_STUBS},
            entry=entry,
        )
    base = _ratio(entry, terminal)
    if base is None:
        return ForwardReturn(
            ts_code=ts_code,
            formation_date=formation_date,
            status=FwdReturnStatus.FWD_MISSING,
            by_stub={str(stub): None for stub in DELIST_STUBS},
            entry=entry,
            exit_point=terminal,
        )
    by_stub = {
        str(stub): (Decimal(1) + base) * (Decimal(1) + stub) - Decimal(1)
        for stub in DELIST_STUBS
    }
    return ForwardReturn(
        ts_code=ts_code,
        formation_date=formation_date,
        status=FwdReturnStatus.FWD_TERMINAL_DELIST,
        value=by_stub[str(DELIST_STUBS[0])],
        by_stub=by_stub,
        exit_date=terminal.trade_date,
        horizon_months=len(grid_ahead),
        entry=entry,
        exit_point=terminal,
    )


def summarize_returns(
    items: Iterable[ForwardReturn], *, delisted_later: frozenset[str] = frozenset()
) -> dict[str, object]:
    """收益层的结构化披露（H4：禁静默 dropna，每一条流失都要落在某个码上）。

    ★``terminal_delist`` 与 ``no_formation_price`` 两项是幸存者偏差的直接度量：
    B109 花钱在宇宙层含进的退市名，如果在收益层被 dropna 掉，净效果等价于
    只拉 ``list_status=L``，且 ``in_universe_delisted_later`` 这类探针再也照不出来。
    """
    rows = list(items)
    counts: dict[str, int] = {}
    for item in rows:
        key = str(item.status)
        counts[key] = counts.get(key, 0) + 1

    frozen = [item for item in rows if item.status is FwdReturnStatus.FWD_FROZEN_SUSPENDED]
    terminal = [item for item in rows if item.status is FwdReturnStatus.FWD_TERMINAL_DELIST]
    usable = [item for item in rows if item.is_usable]
    horizons: dict[str, int] = {}
    for item in frozen:
        horizons[str(item.horizon_months)] = horizons.get(str(item.horizon_months), 0) + 1
    return {
        "n": len(rows),
        "usable": len(usable),
        "usable_fraction": len(usable) / len(rows) if rows else 0.0,
        "status_counts": dict(sorted(counts.items())),
        # ★停牌冻结的跨度分布。全为 1 说明该月无冻结；长尾说明该月的「月度收益」
        # 里混进了多月观测，解读分年结果时必须知道。
        "frozen_horizon_months": dict(sorted(horizons.items())),
        "terminal_delist": len(terminal),
        "terminal_delist_in_delisted_later": sum(
            1 for item in terminal if item.ts_code in delisted_later
        ),
        "survivorship_note": (
            "退市观测以最后成交日复权价入账并叠加 {0, -0.30, -1.00} 三档 stub，未做"
            "公司行动处置（spec §5）。若某月 terminal_delist 计数为 0 而当月宇宙含"
            "日后退市名，须核查是否在上游被静默剔除——那等价于把幸存者偏差挪到下游。"
        ),
    }
