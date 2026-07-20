"""B109 F002 — 月末面板装配与覆盖漏斗（纯逻辑，不联网）。

把 resolver（分子）、marketcap（分母）、universe（成分）接成逐月截面，并产出
**覆盖漏斗**：从「当时在市的证券」一路衰减到「分子分母都可用」，每一级的流失
都必须有归因。H4：禁止静默 dropna——掉的每一条都要落在某个失败码上。

★F001 裁定的**四项不得省略**的披露，由 :func:`mandatory_disclosures` 强制随附
（见该函数 docstring）。它们不是注释，是 :func:`build_funnel` 输出的固定字段——
放在数据结构里而非报告文字里，才不会在下一次转述中丢失。
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from scripts.research.ashare_pit.codes import (
    FactStatus,
    MarketCapStatus,
    ResolvedFact,
)
from scripts.research.ashare_pit.marketcap import MarketCapPoint

# ★★2026-07-20 撤回原值 (0.0047, 0.0088)：F001 的探针走的是**单次调用**，
# 而单次调用会被服务端静默截断（见 `fetch` 模块 docstring）。分页重测后：
#
#   2021FY 修订率 0.525% → 1.325%（2.5 倍）  flag=0 保留率 69.4% → 93.1%
#   2022FY 修订率 1.534% → 1.721%            flag=0 保留率 60.1% → 70.2%
#   2023FY / 2022H1 未触顶，数字不变
#
# 即 F001 报告的修订率区间**系统性低估**，且「保留率剧烈波动」部分是截断伪影而非机制。
# 在 F001 用分页重测之前，这里**不提供任何区间**——给一个已知偏低的数比不给更糟，
# 下游会拿它当作已验证的事实。
REVISION_RATE_BOUNDS: tuple[float, float] | None = None

# 已分页重测的期次（观测下界）。**只列实际重测过的**，不外推、不补全。
REVISION_RATE_REMEASURED: dict[str, float] = {
    "20211231": 0.01325,
    "20221231": 0.01721,
    "20231231": 0.01032,
    "20220630": 0.00019,
}

# ★方向性结论**未被推翻**：修订风险仍集中在年报分量（重测后 FY 三期均 >1%，
# 而 2022H1 仅 0.019%），TTM 四分量风险非均匀这一点反而更强了。
REVISION_RATE_BY_REPORT_TYPE: dict[str, float] | None = None
"""F001 分页重测前不提供逐报告类型的率值——原值同样来自被截断的观测。"""


@dataclass(frozen=True)
class PanelRow:
    """一个证券-形成日的面板行。``is_usable`` 为真才允许进入下游计算。"""

    ts_code: str
    formation_date: str
    end_date: str
    fact: ResolvedFact
    market_cap: MarketCapPoint | None

    @property
    def is_usable(self) -> bool:
        return self.fact.is_usable and self.market_cap is not None and self.market_cap.is_usable

    @property
    def drop_reason(self) -> str | None:
        """流失归因。可用行返回 ``None``；其余一律落在一个结构化码上（H4）。"""
        if not self.fact.is_usable:
            return str(self.fact.status)
        if self.market_cap is None:
            return str(MarketCapStatus.TOTAL_MARKET_CAP_MISSING)
        if not self.market_cap.is_usable:
            return str(self.market_cap.status)
        return None


def month_end_dates(start: str, end: str) -> list[str]:
    """闭区间 ``[start, end]`` 内每个自然月的月末日（``YYYYMMDD``）。

    形成日用**自然月末**而非交易日：as-of 语义比较的是 ``f_ann_date <= 形成日``，
    与交易日历无关。分母侧再由 :func:`last_trade_date_on_or_before` 落到实际交易日。
    """
    start_year, start_month = int(start[:4]), int(start[4:6])
    end_year, end_month = int(end[:4]), int(end[4:6])
    dates: list[str] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        last_day = calendar.monthrange(year, month)[1]
        dates.append(f"{year:04d}{month:02d}{last_day:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return dates


def last_trade_date_on_or_before(trade_dates: Iterable[str], formation_date: str) -> str | None:
    """不晚于形成日的最后一个交易日；没有则返回 ``None``（不向后取，那是前视）。"""
    eligible = [item for item in trade_dates if item <= formation_date]
    return max(eligible) if eligible else None


def select_latest_resolved(
    resolved_by_period: dict[str, ResolvedFact],
) -> tuple[str | None, ResolvedFact | None]:
    """从多个报告期的解析结果里选出「形成日当时最新的一期」。

    ★歧义期不得跳过：若某一期是 ``FACT_VERSION_AMBIGUOUS`` 而它恰是最新一期，
    必须**返回该歧义结果**而不是退回到更早那期。退一期看似「还有数可用」，
    实则用旧数据冒充当期事实——这正是 fail-closed 要拦的静默降级。
    """
    usable = {
        end_date: fact
        for end_date, fact in resolved_by_period.items()
        if fact.status in (FactStatus.RESOLVED, FactStatus.FACT_VERSION_AMBIGUOUS)
    }
    if not usable:
        return None, None
    latest = max(usable)
    return latest, usable[latest]


def build_funnel(rows: Iterable[PanelRow], *, universe_size: int) -> dict[str, object]:
    """一个形成日截面的覆盖漏斗。

    ``universe_size`` 是**当时在市**的证券数（含日后退市者），不是面板行数——
    两者之差即「宇宙里有、但连一条待解析记录都没有」的部分，这一段最容易被漏掉。
    """
    items = list(rows)
    usable = [item for item in items if item.is_usable]

    reasons: dict[str, int] = {}
    for item in items:
        if (reason := item.drop_reason) is not None:
            reasons[reason] = reasons.get(reason, 0) + 1

    return {
        "universe_size": universe_size,
        "panel_rows": len(items),
        "no_record_at_all": max(universe_size - len(items), 0),
        "usable": len(usable),
        "usable_fraction": len(usable) / universe_size if universe_size else 0.0,
        "drop_reasons": dict(sorted(reasons.items())),
        # ★fail-closed 的代价必须单独可见：这些不是「缺数据」，是「有数据但分不清哪版」。
        # F001 实测 4/50450，其中 603607.SH 两版差 66% —— 静默挑一条就是那个错值。
        "fact_version_ambiguous": sum(
            1 for item in items if item.fact.status is FactStatus.FACT_VERSION_AMBIGUOUS
        ),
        "superseded_later": sum(1 for item in items if item.fact.superseded_later),
    }


def flag0_retention(rows: Iterable[dict[str, object]]) -> float:
    """一期内「至少有一条 ``update_flag=0``」的证券占比。

    ★这个数必须逐期披露：它衡量的是**修订检出能力**，不是修订本身。
    F001 实测保留率在 10.5%–95.4% 之间剧烈波动，且检出机制正在迁移
    （2019–2022 主靠 0/1 配对，2023/2024 已转为多条 flag=1 带不同 ``f_ann_date``）。
    不披露它，下游就会把「这一期没检出修订」读成「这一期没有修订」。
    """
    by_code: dict[str, bool] = {}
    for row in rows:
        ts_code = str(row.get("ts_code") or "")
        if not ts_code:
            continue
        has_flag0 = str(row.get("update_flag") or "") == "0"
        by_code[ts_code] = by_code.get(ts_code, False) or has_flag0
    return sum(by_code.values()) / len(by_code) if by_code else 0.0


def mandatory_disclosures(
    *,
    fact_version_ambiguous: int,
    flag0_retention_by_period: dict[str, float],
) -> dict[str, object]:
    """★F001 裁定的四项不得省略的披露。

    1. ``FACT_VERSION_AMBIGUOUS`` 计数（fail-closed 的代价，非「缺数据」）
    2. 逐期 ``flag=0`` 保留率（禁止把「没检出修订」读成「没有修订」）
    3. 修订率**标区间**，禁点估计
    4. FY 分量**单独**标风险（TTM 四分量风险非均匀）

    以结构化字段随每份覆盖报告输出。放进数据结构而不是文字，是因为文字会在转述中丢。
    """
    return {
        "fact_version_ambiguous_count": fact_version_ambiguous,
        "fact_version_ambiguous_note": (
            "fail-closed 拦下的『有数据但无法分辨版本先后』，不同于缺数据；"
            "禁止按 update_flag 或行序任选一条（上游禁令 #13）"
        ),
        "flag0_retention_by_period": dict(sorted(flag0_retention_by_period.items())),
        "flag0_retention_note": (
            "衡量的是修订**检出能力**而非修订本身；F001 实测 10.5%–95.4% 剧烈波动。"
            "『未检出修订』不等于『无修订』"
        ),
        "revision_rate_bounds": REVISION_RATE_BOUNDS,
        "revision_rate_note": (
            "★F001 原区间 0.47%-0.88% **已撤回**——探针走单次调用，被服务端静默截断。"
            "分页重测后 2021FY 修订率 0.525%→1.325%（2.5 倍）。重测完成前不提供区间"
        ),
        "revision_rate_remeasured_paged": dict(REVISION_RATE_REMEASURED),
        "revision_rate_by_report_type": REVISION_RATE_BY_REPORT_TYPE,
        "fy_component_risk_note": (
            "★修订风险集中在 FY 分量这一**方向性结论未被推翻**，重测后反而更强："
            "FY 三期均 >1%，而 2022H1 仅 0.019%。TTM 由四个单季拼成，"
            "其风险**非均匀**，不得用混合平均掩盖 FY 分量"
        ),
        # F001 的诚实限制随附，避免下游把 2021-2024 的结论外推到全样本
        "measured_window": "2021-2024（report_type=1）；其中仅 4 期做过分页重测",
        "extrapolation_warning": (
            "2013-2020 未测，且 2019/2020 的 flag=0 保留率模式与 2021+ 显著不同 → 不可外推"
        ),
        # ★这一条是数据层的元缺陷，比任何单个数字都重要
        "upstream_fetch_defect": (
            "Tushare 单次调用静默截断（income_vip 9000 行 / namechange 10000 行，无错误、"
            "无标志位）。截断**非均匀**：2022FY 漏掉的行里 update_flag=0 占 18.7%、"
            "flag=1 仅 5.2%，即被砍掉的恰恰富集 vintage 记录。"
            "所有走单次调用得出的 vintage 结论均须以分页重测复核"
        ),
    }


def summarize_panel(
    funnels: Iterable[dict[str, object]],
) -> dict[str, object]:
    """跨形成日汇总。逐月漏斗全部保留——只给一个平均数会掩盖单月塌陷。"""
    items = list(funnels)
    if not items:
        return {"n_formation_dates": 0, "by_formation_date": []}

    usable = sum(int(item["usable"]) for item in items)
    universe = sum(int(item["universe_size"]) for item in items)
    fractions = sorted(float(item["usable_fraction"]) for item in items)
    return {
        "n_formation_dates": len(items),
        "pooled_usable_fraction": usable / universe if universe else 0.0,
        "worst_month_usable_fraction": fractions[0],
        "median_month_usable_fraction": fractions[len(fractions) // 2],
        "total_fact_version_ambiguous": sum(
            int(item["fact_version_ambiguous"]) for item in items
        ),
        "by_formation_date": items,
    }


def to_jsonable(value: object) -> object:
    """Decimal → str 的递归转换。★不转 float：分子分母都是金额，精度不能在导出时丢。"""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
