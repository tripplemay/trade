"""B066 F002 — unit tests for the directional A-share cost model."""

from __future__ import annotations

import pytest

from trade.backtest.cn_attack_momentum_quality.costs import CnCostError, CnCostModel


def test_sell_rate_includes_stamp_duty_buy_does_not() -> None:
    model = CnCostModel(stamp_duty_bps=10.0, commission_bps=2.5, slippage_bps=5.0)
    # buy = commission + slippage = 7.5 bps; sell adds 10 bps stamp duty = 17.5 bps.
    assert model.buy_rate() == pytest.approx(7.5 / 10_000.0)
    assert model.sell_rate() == pytest.approx(17.5 / 10_000.0)
    # The asymmetry IS the stamp duty.
    assert model.sell_rate() - model.buy_rate() == pytest.approx(10.0 / 10_000.0)


def test_trade_cost_costs_each_side_at_its_own_rate() -> None:
    model = CnCostModel(stamp_duty_bps=10.0, commission_bps=2.5, slippage_bps=5.0)
    # 100k buy + 100k sell: buy 100k*7.5bps=75, sell 100k*17.5bps=175 → 250.
    cost = model.trade_cost(buy_notional=100_000.0, sell_notional=100_000.0)
    assert cost == pytest.approx(75.0 + 175.0)


def test_pure_sell_pays_stamp_duty_pure_buy_does_not() -> None:
    model = CnCostModel()
    sell_only = model.trade_cost(buy_notional=0.0, sell_notional=50_000.0)
    buy_only = model.trade_cost(buy_notional=50_000.0, sell_notional=0.0)
    # Same notional, but the sell side is strictly more expensive (stamp duty).
    assert sell_only > buy_only


def test_defaults_match_spec_cost_row() -> None:
    model = CnCostModel()
    # B081 F001 — 印花税 default is now 5bp (0.05%, halved 2023-08-28); the old 10bp
    # 口径 is reproduced by an explicit CnCostModel(stamp_duty_bps=10.0) for F004's A/B.
    assert model.stamp_duty_bps == 5.0  # 0.05% sell-only (post-2023-08-28)
    assert model.commission_bps == 2.5
    assert model.slippage_bps == 5.0


def test_negative_rate_rejected() -> None:
    with pytest.raises(CnCostError, match="must be >= 0"):
        CnCostModel(stamp_duty_bps=-1.0)


def test_negative_notional_rejected() -> None:
    with pytest.raises(CnCostError, match="must be >= 0"):
        CnCostModel().trade_cost(buy_notional=-1.0, sell_notional=0.0)
