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
from datetime import date
from decimal import Decimal

from scripts.research.ashare_pit.codes import (
    FactStatus,
    MarketCapStatus,
    ResolvedFact,
)
from scripts.research.ashare_pit.marketcap import MarketCapPoint


def _to_date(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except (ValueError, IndexError):
        return None

# ★★2026-07-20 F001 分页重测（2013-2024 全 48 期）后的口径。原值 (0.0047, 0.0088)
# 来自被静默截断的单次调用，已作废。详见
# `docs/audits/B109-F001-vintage-probe-remeasured-2026-07-20.md`。
#
# ★区间**只取自可信窗口 2018-2021**：那四年 65%-91% 的证券存有多个版本，
# 修订检出接近完全，故观测率接近无偏。2013-2017 只有 7%-14% 的证券有多版本，
# 其近零修订率是**不可观测**而非**已证明为低**——不得并入区间。
REVISION_RATE_BOUNDS: tuple[float, float] = (0.00515, 0.01325)

# 年报（FY）逐期观测率。**只列实际分页测过的**，不外推、不补全。
# ★2013-2017 一并列出但标注不可信，是为了让下游看见「低值来自看不见」而非「低风险」。
REVISION_RATE_FY_BY_YEAR: dict[str, float] = {
    "2013": 0.00071, "2014": 0.00112, "2015": 0.00289,  # ← 多版本仅 7%-10%，不可信
    "2016": 0.00253, "2017": 0.00414,  # ← 多版本 13.5%，不可信
    "2018": 0.00515, "2019": 0.00626, "2020": 0.00947, "2021": 0.01325,  # ← 可信窗口
    "2022": 0.01721, "2023": 0.01032, "2024": 0.01022,
}

# 版本多重度 = 该期有 >=2 个存档版本的证券占比。**这是修订率可信度的前置条件**：
# 它低时，修订「测不出来」而不是「不存在」。实测三段式存储制度变迁。
VERSION_MULTIPLICITY_FY: dict[str, float] = {
    "2013": 0.073, "2015": 0.100, "2017": 0.135,
    "2018": 0.648, "2019": 0.888, "2020": 0.914, "2021": 0.912,
    "2022": 0.679, "2024": 0.074,
}
TRUSTED_MEASUREMENT_YEARS: tuple[str, ...] = ("2018", "2019", "2020", "2021")

# ★修订风险集中在年报分量（重测后更强）。48 期分页实测的逐报告类型率。
REVISION_RATE_BY_REPORT_TYPE: dict[str, float] = {
    "FY": 0.00747,
    "H1": 0.00181,
    "Q3": 0.00089,
    "Q1": 0.00073,
}


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
    def report_lag_days(self) -> int | None:
        """形成日与所用报告期期末之间的天数。

        ★这一项不能省：resolver 拿不到最新一期时会**回退到更早的报告期**
        （as-of 语义上完全正确），于是漏斗里一行「可用」的背后可能是一年前的报表。
        只报可用率会把「有数」与「数够新」混为一谈——2014 年实测正是如此：
        可用率 91% 看着健康，实际大量行由更旧的期次支撑。
        """
        if not self.end_date or len(self.end_date) != 8:
            return None
        formation = _to_date(self.formation_date)
        end = _to_date(self.end_date)
        if formation is None or end is None:
            return None
        return (formation - end).days

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
        **_staleness(usable),
    }


# 报告新鲜度分档。A 股季报法定披露上限约 1 个月、年报 4 个月，
# 故 >270 天基本等同「跳过了至少一期」，>450 天则连年报都换代了。
_STALENESS_BUCKETS: tuple[tuple[str, int], ...] = (
    ("lag_le_180d", 180),
    ("lag_le_270d", 270),
    ("lag_le_450d", 450),
)


def _staleness(usable: list[PanelRow]) -> dict[str, object]:
    """可用行的报告新鲜度分布。**只统计可用行**——不可用行的滞后无意义。"""
    lags = sorted(lag for item in usable if (lag := item.report_lag_days) is not None)
    if not lags:
        return {"report_lag": {"n": 0}}
    counts = {name: sum(1 for lag in lags if lag <= limit) for name, limit in _STALENESS_BUCKETS}
    return {
        "report_lag": {
            "n": len(lags),
            "median_days": lags[len(lags) // 2],
            "p90_days": lags[int(len(lags) * 0.9)],
            "max_days": lags[-1],
            **{name: count / len(lags) for name, count in counts.items()},
        }
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
        "revision_rate_bounds": list(REVISION_RATE_BOUNDS),
        "revision_rate_note": (
            "★区间 0.515%-1.325% **只取自可信窗口 2018-2021**（该窗口 65%-91% 的证券"
            "存有多版本，检出接近完全）。F001 原区间 0.47%-0.88% 已作废——"
            "探针走单次调用被静默截断。一律以区间引用，禁作点估计"
        ),
        "revision_rate_fy_by_year": dict(REVISION_RATE_FY_BY_YEAR),
        "revision_rate_by_report_type": dict(REVISION_RATE_BY_REPORT_TYPE),
        "fy_component_risk_note": (
            "★修订风险集中在 FY 分量，重测后更强：FY 0.747% vs Q1 0.073%（10.2 倍）。"
            "TTM 由四个单季拼成，其风险**非均匀**，不得用混合平均掩盖 FY 分量"
        ),
        # ★★这一条决定上面那些率能不能信：多版本占比低时，修订是「测不出」而非「不存在」
        "version_multiplicity_fy": dict(VERSION_MULTIPLICITY_FY),
        "trusted_measurement_years": list(TRUSTED_MEASUREMENT_YEARS),
        "version_multiplicity_note": (
            "★存储制度三段式变迁：2013-2017 仅 7%-14% 的证券存有多版本 → "
            "该窗口的近零修订率是**不可观测**，不是**已证明为低**，不得当作低风险引用；"
            "2018-2021 达 65%-91%（可信窗口，区间取自此）；2022+ 回落但检出机制转为"
            "『多条 flag=1 带不同 f_ann_date』，仍能工作"
        ),
        "measured_window": "2013-2024 全 48 期（report_type=1），分页重测；28/48 期需多页",
        "extrapolation_warning": (
            "2013-2017 的修订率不可信（多版本占比 7%-14%）；★但实测**已推翻**两个担忧："
            "2014 年面板既无覆盖洞（NOT_YET_PUBLISHED=0）也无陈旧问题"
            "（报告滞后中位 91 天，与 2023 的 92 天相同）。该窗口真正的约束在**分母**："
            "2014-06-30 有 8.7% 的证券缺 total_mv"
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
