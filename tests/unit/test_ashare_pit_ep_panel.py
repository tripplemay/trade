"""B110 F002 — E/P 面板与覆盖漏斗的单元测试（离线，不联网）。

被测性质：

1. **E/P 单位口径**：分子 `n_income_attr_p` 是**元**，分母 `total_mv_cny` 已由
   B109 `marketcap.WAN_TO_CNY` 一次性从万元转元 → 两边都是元，**不再乘任何系数**。
2. ★**负 E/P 必须保留**（spec §3.4 主口径不剔除）。实测 2021 年 15.50% 的证券
   TTM 为负 —— 一旦这里过滤，「双口径」设计在实现层被架空。
3. ★**漏斗闭合**：``usable + Σ drop_reasons == panel_rows``。这是 H4「禁静默 dropna」
   的机器判据：任何未归类的流失都会让等式破。
4. ★**drop_reason 单一归属**：分子 → 分母 → 收益的优先级，一行只归一个码。
5. ★**CSV 列稳定**：缺席的状态码补 0 而不是让列消失 —— 让列消失等于让流失消失。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_pit.codes import (
    FactStatus,
    FactVersion,
    MarketCapStatus,
    ResolvedFact,
)
from scripts.research.ashare_pit.ep_panel import (
    EpPanelRow,
    build_ep_funnel,
    csv_header,
    funnel_closes,
    funnel_to_csv_row,
)
from scripts.research.ashare_pit.marketcap import MarketCapPoint
from scripts.research.ashare_pit.returns import ForwardReturn, FwdReturnStatus
from scripts.research.ashare_pit.ttm import CumulativeFact, TTMResult, TTMStatus

# --- 构造辅助 ---


def _resolved(value: str = "1", f_ann: str = "20240420") -> ResolvedFact:
    version = FactVersion(
        ts_code="000001.SZ",
        end_date="20231231",
        f_ann_date=f_ann,
        ann_date=f_ann,
        update_flag="0",
        value=Decimal(value),
    )
    return ResolvedFact(
        status=FactStatus.RESOLVED,
        value=Decimal(value),
        selected=version,
        formation_date="20240630",
        candidates=(version,),
    )


def _ttm(
    value: str | None = "1000000000",
    *,
    status: TTMStatus = TTMStatus.RESOLVED,
    anchor: str = "20231231",
) -> TTMResult:
    return TTMResult(
        ts_code="000001.SZ",
        formation_date="20240630",
        status=status,
        value=Decimal(value) if value is not None else None,
        anchor_end_date=anchor,
        cumulatives=(CumulativeFact(anchor, "FY", _resolved()),),
    )


def _cap(
    total_mv_cny: str = "10000000000", *, status: MarketCapStatus = MarketCapStatus.RESOLVED
) -> MarketCapPoint:
    return MarketCapPoint(
        ts_code="000001.SZ",
        trade_date="20240628",
        close=Decimal("10"),
        total_share_wan=Decimal("100000"),
        total_mv_wan=Decimal(total_mv_cny) / Decimal(10000),
        total_mv_cny=Decimal(total_mv_cny),
        identity_error=Decimal("0"),
        status=status,
    )


def _fwd(
    value: str | None = "0.01",
    *,
    status: FwdReturnStatus = FwdReturnStatus.FWD_OK,
    ts_code: str = "000001.SZ",
) -> ForwardReturn:
    return ForwardReturn(
        ts_code=ts_code,
        formation_date="20240630",
        status=status,
        value=Decimal(value) if value is not None else None,
    )


_DEFAULT = object()


def _row(
    ts_code: str = "000001.SZ",
    *,
    ttm: TTMResult | None = None,
    cap: object = _DEFAULT,
    fwd: object = _DEFAULT,
    delisted_later: bool = False,
) -> EpPanelRow:
    """``cap=None`` / ``fwd=None`` 是**有意传空**（分母/收益缺失），与不传区分开。"""
    return EpPanelRow(
        ts_code=ts_code,
        formation_date="20240630",
        ttm=ttm if ttm is not None else _ttm(),
        market_cap=_cap() if cap is _DEFAULT else cap,  # type: ignore[arg-type]
        forward=_fwd() if fwd is _DEFAULT else fwd,  # type: ignore[arg-type]
        delisted_later=delisted_later,
    )


# --- E/P 口径 ---


def test_ep_is_a_plain_ratio_of_two_yuan_quantities() -> None:
    """10 亿利润 / 100 亿市值 = 0.1。★两边都是元，不再乘任何系数。"""
    row = _row()
    assert row.ep == Decimal("0.1")


def test_a_negative_ttm_produces_a_negative_ep_and_is_kept() -> None:
    """★spec §3.4 主口径**不剔除**负 TTM。实测 2021 年 15.50% 的证券 TTM 为负。"""
    row = _row(ttm=_ttm("-2000000000"))
    assert row.ep == Decimal("-0.2")
    assert row.has_ep is True
    assert row.is_usable is True
    assert row.drop_reason is None


def test_ep_is_none_when_the_numerator_failed() -> None:
    row = _row(ttm=_ttm(None, status=TTMStatus.COMPONENT_MISSING))
    assert row.ep is None
    assert row.drop_reason == "COMPONENT_MISSING"


def test_ep_is_none_when_the_denominator_is_missing() -> None:
    row = _row(cap=None)
    assert row.ep is None
    assert row.drop_reason == "TOTAL_MARKET_CAP_MISSING"


# --- drop_reason 优先级与漏斗闭合 ---


def test_drop_reason_follows_numerator_then_denominator_then_return() -> None:
    """同时坏掉时归给**最上游**那一层——否则同一行会被数进两个桶。"""
    row = _row(
        ttm=_ttm(None, status=TTMStatus.ANCHOR_AMBIGUOUS),
        cap=None,
        fwd=_fwd(None, status=FwdReturnStatus.FWD_NO_FORMATION_PRICE),
    )
    assert row.drop_reason == "ANCHOR_AMBIGUOUS"


def test_a_row_with_ep_but_no_forward_price_drops_at_the_return_stage() -> None:
    row = _row(fwd=_fwd(None, status=FwdReturnStatus.FWD_NO_FORMATION_PRICE))
    assert row.has_ep is True
    assert row.is_usable is False
    assert row.drop_reason == "FWD_NO_FORMATION_PRICE"


def test_the_funnel_closes_exactly() -> None:
    """★``usable + Σ drop_reasons == panel_rows``。这是 H4 的机器判据。"""
    rows = [
        _row("A"),
        _row("B", ttm=_ttm(None, status=TTMStatus.NO_VISIBLE_REPORT)),
        _row("C", cap=None),
        _row("D", fwd=_fwd(None, status=FwdReturnStatus.FWD_TERMINAL_DELIST)),
        _row("E", ttm=_ttm("-500000000")),
    ]
    funnel = build_ep_funnel(rows, universe_size=7)
    assert funnel_closes(funnel)
    assert funnel["panel_rows"] == 5
    assert funnel["no_record_at_all"] == 2
    assert funnel["usable"] == 2  # A 与 E（负 E/P 照样进）


def test_negative_ttm_is_counted_not_dropped() -> None:
    rows = [_row("A"), _row("E", ttm=_ttm("-500000000"))]
    funnel = build_ep_funnel(rows, universe_size=2)
    assert funnel["n_neg_ttm"] == 1
    assert funnel["n_with_ep"] == 2
    assert funnel["neg_ttm_fraction"] == 0.5


# --- ★幸存者偏差与流失偏向探针 ---


def test_the_delisted_later_probe_is_carried_into_the_funnel() -> None:
    """★禁令 #11 自查：某月为 0 而形成日久远 → 宇宙已退化为 list_status=L。"""
    rows = [_row("A"), _row("B", delisted_later=True), _row("C", delisted_later=True)]
    funnel = build_ep_funnel(rows, universe_size=3)
    assert funnel["in_universe_delisted_later"] == 2
    assert funnel["delisted_later_with_ep"] == 2


def test_terminal_delist_rows_report_their_own_ep_median() -> None:
    """★把「剔除缺收益样本会高估结论」从断言变成实测。

    被退市终局吃掉的名，其 E/P 中位数若显著高于全体，说明顶层组正在系统性
    富集退市陷阱——这正是 A 股保壳公司用非经常性损益把 TTM 做正的那条通道。
    """
    rows = [
        _row("A", ttm=_ttm("1000000000")),  # E/P = 0.1
        _row(
            "B",
            ttm=_ttm("5000000000"),  # E/P = 0.5，典型的重组收益撑起来的壳
            fwd=_fwd("-0.6", status=FwdReturnStatus.FWD_TERMINAL_DELIST),
        ),
    ]
    funnel = build_ep_funnel(rows, universe_size=2)
    assert funnel["d_fwd_terminal_delist"] == 1
    assert funnel["d_fwd_terminal_delist__median_ep"] == Decimal("0.5")
    assert funnel["median_ep_all"] == Decimal("0.3")


def test_joint_coverage_is_measured_against_the_full_universe() -> None:
    """D7：``n_in_quintile / n_universe``，分母是**当时在市**的证券数。"""
    rows = [_row("A"), _row("B", cap=None)]
    funnel = build_ep_funnel(rows, universe_size=4)
    assert funnel["n_in_quintile"] == 1
    assert funnel["joint_coverage_c1"] == 0.25


# --- CSV 稳定性 ---


def test_every_status_code_gets_its_own_stable_column() -> None:
    """★缺席的码补 0 而不是让列消失——让列消失等于让流失消失。"""
    header = csv_header()
    assert "ttm_resolved" in header
    assert "ttm_cumulative_basis_break" in header
    assert "ttm_period_not_fetched" in header
    assert "fwd_terminal_delist" in header
    assert "fwd_no_formation_price" in header
    assert len(header) == len(set(header))


def test_csv_row_fills_absent_codes_with_zero() -> None:
    funnel = build_ep_funnel([_row("A")], universe_size=1)
    row = funnel_to_csv_row(funnel, seq=1)
    assert set(row) == set(csv_header())
    assert row["formation_seq"] == 1
    assert row["ttm_resolved"] == 1
    assert row["ttm_cumulative_basis_break"] == 0
    assert row["fwd_ok"] == 1
    assert row["fwd_terminal_delist"] == 0


def test_report_lag_columns_are_lifted_out_of_the_nested_dict() -> None:
    funnel = build_ep_funnel([_row("A")], universe_size=1)
    row = funnel_to_csv_row(funnel, seq=7)
    # 形成日 20240630 − 锚点 20231231 = 182 天
    assert row["report_lag_median_days"] == 182
