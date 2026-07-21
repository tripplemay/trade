"""B110 F002 — 月末 E/P 面板装配与覆盖漏斗（纯逻辑，不联网）。

把 B110 F001 的分子（:mod:`~scripts.research.ashare_pit.ttm`）、B109 已验收的分母
（:mod:`~scripts.research.ashare_pit.marketcap`，G4 27,963 证券-日 100.0000%）、
B109 的全状态宇宙（:mod:`~scripts.research.ashare_pit.universe`）与前向收益
（:mod:`~scripts.research.ashare_pit.returns`）接成逐月截面。

## 漏斗的存在意义

H4 禁静默 dropna：从「当时在市的证券」一路衰减到「进入五分位」，**每一级流失都要
有归因**。B109 的 :func:`~scripts.research.ashare_pit.pipeline.build_funnel` 只覆盖
到「分子分母都可用」，B110 在其上追加 TTM 层与收益层。

★**不修改 B109 的 `PanelRow` / `build_funnel`**——改它们会让 B109 signoff 的证据失效。
本模块用组合（:class:`EpPanelRow` 持有 :class:`TTMResult` 等）而非继承。

## ★流失偏向探针：把断言变成实测

「剔除缺前向收益的样本会高估收益」这句话本身是个**假设**。本模块因此逐月输出
被剔者的 E/P 中位数、退市名占比等，让 Codex 能用数据判断方向，而不是接受断言。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from scripts.research.ashare_pit.codes import FactStatus, MarketCapStatus, ResolvedFact
from scripts.research.ashare_pit.marketcap import MarketCapPoint
from scripts.research.ashare_pit.pipeline import build_funnel
from scripts.research.ashare_pit.returns import DELIST_STUBS, ForwardReturn, FwdReturnStatus
from scripts.research.ashare_pit.ttm import TTMResult, TTMStatus

#: 分母缺失时的 drop_reason，与 B109 保持同名。
TOTAL_MV_MISSING = str(MarketCapStatus.TOTAL_MARKET_CAP_MISSING)

_EMPTY_FACT = ResolvedFact(
    status=FactStatus.FACT_MISSING,
    value=None,
    selected=None,
    formation_date="",
    candidates=(),
)


@dataclass(frozen=True)
class EpPanelRow:
    """一个（证券 × 形成日）截面点。"""

    ts_code: str
    formation_date: str
    ttm: TTMResult
    market_cap: MarketCapPoint | None
    forward: ForwardReturn | None
    #: 该证券在**本形成日之后**曾退市。★禁令 #11 的自查探针，不参与任何计算。
    delisted_later: bool = False

    @property
    def ep(self) -> Decimal | None:
        """E/P = TTM 归母净利润(元) / 总市值(元)。两边都已是元，不乘任何系数。

        ★**不做任何符号或量级过滤**。负 E/P 是有效经济事实（实测 2021 年 15.50%
        的证券 TTM 为负），spec §3.4 主口径明令不剔除。
        """
        if not self.ttm.is_usable or self.ttm.value is None:
            return None
        if self.market_cap is None or not self.market_cap.is_usable:
            return None
        if self.market_cap.total_mv_cny <= 0:
            return None
        return self.ttm.value / self.market_cap.total_mv_cny

    @property
    def has_ep(self) -> bool:
        return self.ep is not None

    @property
    def is_usable(self) -> bool:
        """能进入五分位：有 E/P **且**有可用前向收益。"""
        return self.has_ep and self.forward is not None and self.forward.is_usable

    @property
    def drop_reason(self) -> str | None:
        """★分层优先级：分子 → 分母 → 收益。同一行只归一个码，漏斗才闭合。"""
        if not self.ttm.is_usable:
            return str(self.ttm.status)
        if self.market_cap is None:
            return TOTAL_MV_MISSING
        if not self.market_cap.is_usable:
            return str(self.market_cap.status)
        if self.forward is None:
            return str(FwdReturnStatus.FWD_MISSING)
        if not self.forward.is_usable:
            return str(self.forward.status)
        return None

    @property
    def report_lag_days(self) -> int | None:
        """形成日 − TTM 锚点期末。B109 ``_staleness`` 用同一语义。"""
        anchor = self.ttm.anchor_end_date
        if len(anchor) != 8 or len(self.formation_date) != 8:
            return None
        from datetime import date

        try:
            left = date(
                int(self.formation_date[:4]),
                int(self.formation_date[4:6]),
                int(self.formation_date[6:8]),
            )
            right = date(int(anchor[:4]), int(anchor[4:6]), int(anchor[6:8]))
        except ValueError:
            return None
        return (left - right).days

    @property
    def fact(self) -> ResolvedFact:
        """锚点的 :class:`ResolvedFact`，供 B109 ``build_funnel`` 结构复用。

        ★这是**锚点级**而非 TTM 级的视角：TTM 全四分量的歧义计数另见
        :func:`build_ep_funnel` 的 ``d_component_ambiguous``。
        """
        anchor = self.ttm.anchor_end_date
        for item in self.ttm.cumulatives:
            if item.end_date == anchor:
                return item.resolved
        return _EMPTY_FACT


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def build_ep_funnel(
    rows: Iterable[EpPanelRow],
    *,
    universe_size: int,
    formation_date: str = "",
    malformed_security_rows: int = 0,
    price_trade_date: str = "",
    exit_trade_date: str = "",
) -> dict[str, object]:
    """一个形成日的完整覆盖漏斗（B109 骨架 + B110 的 TTM 层与收益层）。

    ``universe_size`` 是当时**在市**的证券数（含日后退市者），不是面板行数。
    """
    items = list(rows)
    base = build_funnel(items, universe_size=universe_size)

    status_counts: dict[str, int] = {}
    for item in items:
        key = str(item.ttm.status)
        status_counts[key] = status_counts.get(key, 0) + 1

    fwd_counts: dict[str, int] = {}
    for item in items:
        if item.forward is None:
            continue
        key = str(item.forward.status)
        fwd_counts[key] = fwd_counts.get(key, 0) + 1

    with_ep = [item for item in items if item.has_ep]
    in_quintile = [item for item in items if item.is_usable]
    negative = [item for item in with_ep if (value := item.ep) is not None and value < 0]
    terminal = [
        item
        for item in items
        if item.forward is not None
        and item.forward.status is FwdReturnStatus.FWD_TERMINAL_DELIST
    ]

    # ★流失偏向探针：被退市终局吃掉的那批名，它们的 E/P 长什么样？
    # 若显著高于全体中位数，说明顶层组正在系统性富集退市陷阱。
    terminal_eps = [value for item in terminal if (value := item.ep) is not None]
    all_eps = [value for item in with_ep if (value := item.ep) is not None]

    ambiguous_components = sum(
        1
        for item in items
        if any(
            cumulative.resolved.status is FactStatus.FACT_VERSION_AMBIGUOUS
            for cumulative in item.ttm.cumulatives
        )
    )
    vintage_gap = sum(
        1
        for item in items
        for component in item.ttm.components
        for source in component.sources
        if (gap := source.vintage_gap_days) is not None and gap > 90
    )

    return {
        **base,
        # ★B109 的 build_funnel 不带形成日（它由调用方按顺序持有）。B110 的 CSV 要让
        # Codex 逐行断言「144 个月无断档」，形成日必须落在行里而不是靠行序推断。
        "formation_date": formation_date or (items[0].formation_date if items else ""),
        "price_trade_date_t": price_trade_date,
        "price_trade_date_t1": exit_trade_date,
        "d_security_row_malformed": malformed_security_rows,
        "ttm_status_counts": dict(sorted(status_counts.items())),
        "fwd_status_counts": dict(sorted(fwd_counts.items())),
        "n_with_ep": len(with_ep),
        "n_in_quintile": len(in_quintile),
        # D7（附录 §2）：截面级联合覆盖率。门控判 min/median，不用池化。
        "joint_coverage_c1": len(in_quintile) / universe_size if universe_size else 0.0,
        # ★主口径不剔除负 TTM。某月为 0 = 被静默剔了（H4 违规）。
        "n_neg_ttm": len(negative),
        "neg_ttm_fraction": len(negative) / len(with_ep) if with_ep else 0.0,
        # ★禁令 #11 自查探针：任一月为 0 而形成日久远 → 宇宙退化为 list_status=L。
        "in_universe_delisted_later": sum(1 for item in items if item.delisted_later),
        "delisted_later_with_ep": sum(1 for item in with_ep if item.delisted_later),
        # ★把「剔除缺收益样本会高估」从断言变成实测
        "d_fwd_terminal_delist": len(terminal),
        "d_fwd_terminal_delist__median_ep": _median(terminal_eps),
        "median_ep_all": _median(all_eps),
        "d_component_ambiguous_rows": ambiguous_components,
        "n_vintage_gap_gt_90d": vintage_gap,
        "delist_stubs": [str(stub) for stub in DELIST_STUBS],
    }


def funnel_closes(funnel: dict[str, object]) -> bool:
    """漏斗闭合恒等式：``usable + Σ drop_reasons == panel_rows``（H4 的机器判据）。"""
    reasons = funnel.get("drop_reasons", {})
    assert isinstance(reasons, dict)
    dropped = sum(int(value) for value in reasons.values())
    return int(funnel["usable"]) + dropped == int(funnel["panel_rows"])  # type: ignore[arg-type]


#: 扁平 CSV 的列顺序。★Codex 要对 144 行逐列断言，列名必须稳定。
CSV_COLUMNS: tuple[str, ...] = (
    "formation_date",
    "formation_seq",
    "price_trade_date_t",
    "price_trade_date_t1",
    "universe_size",
    "d_security_row_malformed",
    "panel_rows",
    "no_record_at_all",
    "n_with_ep",
    "n_in_quintile",
    "joint_coverage_c1",
    "usable",
    "usable_fraction",
    "n_neg_ttm",
    "neg_ttm_fraction",
    "in_universe_delisted_later",
    "delisted_later_with_ep",
    "d_fwd_terminal_delist",
    "d_fwd_terminal_delist__median_ep",
    "median_ep_all",
    "fact_version_ambiguous",
    "d_component_ambiguous_rows",
    "n_vintage_gap_gt_90d",
    "superseded_later",
    "report_lag_median_days",
    "report_lag_p90_days",
    "report_lag_max_days",
    "api_calls_this_month",
    "api_rows_this_month",
    "elapsed_seconds",
)

#: TTM / 收益两族状态码在 CSV 中的固定列（缺席时补 0，不让列消失）。
_TTM_CSV_CODES: tuple[TTMStatus, ...] = tuple(TTMStatus)
_FWD_CSV_CODES: tuple[FwdReturnStatus, ...] = tuple(FwdReturnStatus)


def _ttm_column(code: TTMStatus) -> str:
    return f"ttm_{code.value.lower()}"


def _fwd_column(code: FwdReturnStatus) -> str:
    return f"fwd_{code.value.removeprefix('FWD_').lower()}"


def csv_header() -> list[str]:
    return [
        *CSV_COLUMNS,
        *(_ttm_column(code) for code in _TTM_CSV_CODES),
        *(_fwd_column(code) for code in _FWD_CSV_CODES),
    ]


def funnel_to_csv_row(funnel: dict[str, object], *, seq: int) -> dict[str, object]:
    """把一个月的漏斗压平成 CSV 行。缺席的码补 0——★让列消失等于让流失消失。"""
    lag = funnel.get("report_lag", {})
    assert isinstance(lag, dict)
    ttm_counts = funnel.get("ttm_status_counts", {})
    fwd_counts = funnel.get("fwd_status_counts", {})
    assert isinstance(ttm_counts, dict) and isinstance(fwd_counts, dict)
    row: dict[str, object] = {"formation_seq": seq}
    for column in CSV_COLUMNS:
        if column == "formation_seq":
            continue
        if column.startswith("report_lag_"):
            row[column] = lag.get(column.removeprefix("report_lag_"), "")
            continue
        row[column] = funnel.get(column, "")
    for code in _TTM_CSV_CODES:
        row[_ttm_column(code)] = ttm_counts.get(str(code), 0)
    for code in _FWD_CSV_CODES:
        row[_fwd_column(code)] = fwd_counts.get(str(code), 0)
    return row
