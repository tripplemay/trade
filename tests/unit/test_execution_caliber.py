"""B111 F004 fix-round regression tests — unified execution/cost caliber.

Evaluator finding B111-F006-1: F004 round 1 shipped two divergent calibers
(backtest 1+2bps one-sided vs paper 5+5bps both-legs) and only quantified
the gap. These tests pin the unification: one shared caliber module, the
backtest defaults on it, the monthly engine on the both-legs turnover form,
and the pre/post-unification reconciliation numbers.
"""

from __future__ import annotations

from datetime import date

import pytest

from trade.backtest import execution_caliber as caliber
from trade.backtest.cost_reconciliation import (
    cost_caliber_comparison,
    post_unification_comparison,
    unified_rebalance_cost,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


def test_backtest_defaults_are_the_unified_caliber() -> None:
    """BacktestParameters defaults come from the single-source caliber module
    (mutation check: diverge either value and this goes red)."""

    params = BacktestParameters()
    assert params.cost_bps == caliber.UNIFIED_COST_BPS == 5.0
    assert params.slippage_bps == caliber.UNIFIED_SLIPPAGE_BPS == 5.0


def test_legacy_caliber_constants_pinned_for_provenance() -> None:
    """The pre-fix calibers stay pinned so historical artifacts keep their
    provenance labels (they must never silently track the unified values)."""

    assert caliber.LEGACY_BACKTEST_COST_BPS == 1.0
    assert caliber.LEGACY_BACKTEST_SLIPPAGE_BPS == 2.0
    assert caliber.LEGACY_BACKTEST_ONE_SIDED is True
    assert caliber.LEGACY_PAPER_COST_BPS == 5.0
    assert caliber.LEGACY_PAPER_SLIPPAGE_BPS == 5.0
    assert caliber.LEGACY_PAPER_FILL_TIMING == "signal_session_close"


def test_pre_unification_gap_is_the_documented_6_67x() -> None:
    """Provenance: the legacy gap stays reproducible (full swap, $100k)."""

    c = cost_caliber_comparison(100_000.0, 2.0)
    assert c.backtest_cost == pytest.approx(30.0)
    assert c.paper_cost == pytest.approx(200.0)
    assert c.ratio == pytest.approx(6.6667, rel=1e-3)


def test_post_unification_cost_difference_is_zero() -> None:
    """The fix-round deliverable: after unification both engines compute the
    SAME cost on every rebalance (ratio 1.0, difference 0)."""

    for turnover in (0.25, 0.47, 1.0, 2.0):
        c = post_unification_comparison(100_000.0, turnover)
        assert c.difference == pytest.approx(0.0)
        assert c.ratio == pytest.approx(1.0)
        assert c.backtest_cost == pytest.approx(
            unified_rebalance_cost(100_000.0, turnover)
        )


def test_unified_cost_matches_live_anchor() -> None:
    """Live anchor (production paper book): ~$47.76 avg per rebalance at
    ~0.47 turnover on ~$100k — the unified caliber reproduces ~$47."""

    assert unified_rebalance_cost(100_000.0, 0.47) == pytest.approx(47.0, abs=0.5)


def test_monthly_engine_charges_both_legs_on_a_full_swap() -> None:
    """Sidedness unification: a full swap (prior A → new B) costs 2 legs x
    10bps = $200 on $100k under the unified caliber; the legacy one-sided
    haircut charged $30 worth of friction on the same swap."""

    def _bars(symbol: str, closes: list[tuple[date, float]]) -> tuple[PriceBar, ...]:
        return tuple(
            PriceBar(day, symbol, close, close, close, 1) for day, close in closes
        )

    dates_and_closes = [(date(2024, m, 28), 100.0) for m in (1, 2, 3, 4, 5, 6)]
    params = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
        require_positive_trend_return=False,
    )
    from trade.backtest.monthly import run_monthly_backtest

    # Prior book is all SPY; force the new target to QQQ by giving QQQ the
    # only positive momentum (flat SPY/AGG, rising QQQ).
    qqq_closes = [
        (date(2024, 1, 28), 100.0),
        (date(2024, 2, 28), 101.0),
        (date(2024, 3, 28), 102.0),
        (date(2024, 4, 28), 103.0),
        (date(2024, 5, 28), 104.0),
        (date(2024, 6, 28), 105.0),
    ]
    records = (
        _bars("SPY", dates_and_closes)
        + _bars("QQQ", qqq_closes)
        + _bars("AGG", dates_and_closes)
    )
    result = run_monthly_backtest(
        records,
        params,
        signal_date=date(2024, 5, 28),
        prior_weights={"SPY": 1.0},
    )
    assert result.signal.target_weights == {"QQQ": 1.0}
    assert result.turnover == pytest.approx(2.0)  # sell SPY + buy QQQ
    assert result.cost_amount == pytest.approx(100_000.0 * 2.0 * 0.001)
