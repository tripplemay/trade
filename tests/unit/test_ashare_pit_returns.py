"""B110 F002 — 月度前向收益的单元测试（离线，不联网）。

被测性质：

1. **复权**：``ret = (close_t1 × adjf_t1) / (close_t0 × adjf_t0) − 1``。
   ★不复权会把送转当暴跌、把分红白丢——实测 2024-06 单月 51% 的股票除权除息。
2. ★**缺行不是缺失值**：停牌股在 ``daily_basic`` 里完全没有行。四个状态码把
   「形成日无价」「停牌冻结」「退市终局」「未归类」彻底分开（H4 禁静默 dropna）。
3. ★**停牌期的亏损必须落到某个组合上**。若记 r=0 且随后各月因无价而进不了组合，
   崩塌就永远不会落地 —— 方向明确偏乐观，正是推向 GO 那一侧。
4. ★**退市 ≠ 归零**：终值取最后成交价（崩塌已在数据里），stub 三档全跑。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_pit.returns import (
    DELIST_STUBS,
    ForwardReturn,
    FwdReturnStatus,
    PricePoint,
    build_price_point,
    forward_return,
    summarize_returns,
)

# --- 构造辅助 ---


def _px(date: str, close: str, factor: str = "1.0", ts_code: str = "000001.SZ") -> PricePoint:
    return PricePoint(
        ts_code=ts_code, trade_date=date, close=Decimal(close), adj_factor=Decimal(factor)
    )


def _snapshot(**by_date: dict[str, PricePoint]) -> dict[str, dict[str, PricePoint]]:
    return dict(by_date)


# --- 复权 ---


def test_forward_return_uses_adjusted_prices() -> None:
    """10 送 10 后裸价腰斩而复权因子翻倍 → 真实收益为 0，不是 −50%。"""
    prices = {
        "d0": {"000001.SZ": _px("d0", "20.0", "1.0")},
        "d1": {"000001.SZ": _px("d1", "10.0", "2.0")},
    }
    result = forward_return(
        ts_code="000001.SZ",
        formation_date="d0",
        grid_ahead=["d1"],
        prices_by_date=prices,
    )
    assert result.status is FwdReturnStatus.FWD_OK
    assert result.value == Decimal(0)


def test_a_real_price_move_survives_the_adjustment() -> None:
    prices = {
        "d0": {"000001.SZ": _px("d0", "10.0", "1.5")},
        "d1": {"000001.SZ": _px("d1", "11.0", "1.5")},
    }
    result = forward_return(
        ts_code="000001.SZ", formation_date="d0", grid_ahead=["d1"], prices_by_date=prices
    )
    assert result.value == Decimal("0.1")


def test_build_price_point_returns_none_on_unparseable_input() -> None:
    assert build_price_point({"ts_code": "X", "close": None}, adj_factor="1.0") is None
    assert build_price_point({"ts_code": "X", "close": "1.0"}, adj_factor=None) is None
    point = build_price_point(
        {"ts_code": "X", "trade_date": "d0", "close": "1.5"}, adj_factor="2.0"
    )
    assert point is not None and point.adjusted == Decimal("3.0")


# --- ★四码分流：缺行不是缺失值 ---


def test_no_price_at_formation_date_never_enters_a_portfolio() -> None:
    """★实测 2015-07 有 18.13% 的宇宙在形成日无价。这些名不入任何分位。"""
    prices = {"d1": {"000001.SZ": _px("d1", "10.0")}}
    result = forward_return(
        ts_code="000001.SZ", formation_date="d0", grid_ahead=["d1"], prices_by_date=prices
    )
    assert result.status is FwdReturnStatus.FWD_NO_FORMATION_PRICE
    assert result.value is None
    assert result.is_usable is False


def test_a_suspended_month_books_the_loss_when_the_stock_resumes() -> None:
    """★停牌两个月后复牌跌 40% —— 这 40% 必须落在选中它的那个月上。

    若按「停牌月记 0」处理，该股在随后各月因无价而进不了任何组合，这笔亏损
    就永远不会落到任何组合上 —— 系统性抹掉崩塌，方向偏乐观。
    """
    prices = {
        "d0": {"000001.SZ": _px("d0", "10.0")},
        # d1 / d2 停牌：完全没有行
        "d3": {"000001.SZ": _px("d3", "6.0")},
    }
    result = forward_return(
        ts_code="000001.SZ",
        formation_date="d0",
        grid_ahead=["d1", "d2", "d3"],
        prices_by_date=prices,
    )
    assert result.status is FwdReturnStatus.FWD_FROZEN_SUSPENDED
    assert result.value == Decimal("-0.4")
    assert result.horizon_months == 3
    assert result.exit_date == "d3"


def test_an_unclassified_gap_falls_to_the_backstop_code_not_to_silence() -> None:
    """网格上再无行情且没有终值 → 兜底码，**不是**静默 dropna。"""
    prices = {"d0": {"000001.SZ": _px("d0", "10.0")}}
    result = forward_return(
        ts_code="000001.SZ",
        formation_date="d0",
        grid_ahead=["d1", "d2"],
        prices_by_date=prices,
    )
    assert result.status is FwdReturnStatus.FWD_MISSING
    assert result.value is None


# --- ★退市终局与 stub 敏感带 ---


def test_terminal_delisting_uses_the_last_traded_price_and_all_three_stubs() -> None:
    """★崩塌已经在最后成交价里（实测最后 20 交易日中位 −63.7%），别丢掉它。"""
    prices = {"d0": {"000001.SZ": _px("d0", "10.0")}}
    result = forward_return(
        ts_code="000001.SZ",
        formation_date="d0",
        grid_ahead=["d1", "d2"],
        prices_by_date=prices,
        terminal=_px("d_last", "4.0"),
    )
    assert result.status is FwdReturnStatus.FWD_TERMINAL_DELIST
    # 主披露 = stub 0.00 档
    assert result.value == Decimal("-0.6")
    assert result.by_stub["0.00"] == Decimal("-0.6")
    # (1 - 0.6) × (1 - 0.30) - 1 = -0.72
    assert result.by_stub["-0.30"] == Decimal("-0.72")
    # 残值全损 → -100%，但注意这是**叠加在最后成交价之上**的假设
    assert result.by_stub["-1.00"] == Decimal("-1.00")


def test_all_three_stubs_are_always_present_so_no_band_can_be_cherry_picked() -> None:
    """★附录 D6：三档全跑并排披露。任一档缺失 = 挑档。"""
    prices = {
        "d0": {"000001.SZ": _px("d0", "10.0")},
        "d1": {"000001.SZ": _px("d1", "11.0")},
    }
    result = forward_return(
        ts_code="000001.SZ", formation_date="d0", grid_ahead=["d1"], prices_by_date=prices
    )
    assert set(result.by_stub) == {str(stub) for stub in DELIST_STUBS}
    # 非退市观测三档相同 —— stub 只作用于退市终值之后
    assert len(set(result.by_stub.values())) == 1


def test_an_acquisition_style_delisting_can_be_positive() -> None:
    """★退市 ≠ 归零。实测吸收合并型退市为正收益（600832 +144%）。"""
    prices = {"d0": {"600832.SH": _px("d0", "10.0", ts_code="600832.SH")}}
    result = forward_return(
        ts_code="600832.SH",
        formation_date="d0",
        grid_ahead=["d1"],
        prices_by_date=prices,
        terminal=_px("d_last", "24.4", ts_code="600832.SH"),
    )
    assert result.value == Decimal("1.44")


# --- 披露 ---


def test_summary_separates_the_survivorship_relevant_buckets() -> None:
    items = [
        ForwardReturn(
            ts_code="A",
            formation_date="d0",
            status=FwdReturnStatus.FWD_OK,
            value=Decimal("0.01"),
        ),
        ForwardReturn(
            ts_code="B",
            formation_date="d0",
            status=FwdReturnStatus.FWD_TERMINAL_DELIST,
            value=Decimal("-0.6"),
        ),
        ForwardReturn(
            ts_code="C",
            formation_date="d0",
            status=FwdReturnStatus.FWD_FROZEN_SUSPENDED,
            value=Decimal("-0.4"),
            horizon_months=3,
        ),
        ForwardReturn(
            ts_code="D", formation_date="d0", status=FwdReturnStatus.FWD_NO_FORMATION_PRICE
        ),
    ]
    summary = summarize_returns(items, delisted_later=frozenset({"B"}))
    assert summary["n"] == 4
    assert summary["usable"] == 3
    assert summary["terminal_delist"] == 1
    assert summary["terminal_delist_in_delisted_later"] == 1
    assert summary["frozen_horizon_months"] == {"3": 1}
    assert summary["status_counts"]["FWD_NO_FORMATION_PRICE"] == 1


def test_summary_of_an_empty_month_does_not_fabricate_a_pass_rate() -> None:
    summary = summarize_returns([])
    assert summary["n"] == 0
    assert summary["usable_fraction"] == 0.0
