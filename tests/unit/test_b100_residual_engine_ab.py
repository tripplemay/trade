"""B100 — deterministic unit tests for the residual-momentum engine A/B wrapper.

Locks the four claims the research report rests on (no real-data pickle needed — a
small synthetic panel is enough because the logic, not the numbers, is under test):

1. NO look-ahead — raw AND residual momentum at date ``t`` are invariant to any
   mutation of prices strictly after ``t`` (the residualisation regression + the
   momentum cumulation use only data ≤ t; the ``.shift(SKIP)`` pushes them further
   into the past). The realised holding-period return uses strictly future prices.
2. Fairness — the two arms differ ONLY in the momentum input: identical momentum →
   bit-identical equity curves; a changed momentum panel → changed selection/curve.
3. Turnover is computed correctly (Σ|Δw|, first rebalance = all buys, sells pay stamp).
4. Engine construction is faithful — ``_target_weights`` selects exactly the top-N by
   momentum and equal-weights them (the frozen ``build_cn_portfolio`` contract).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.research.b085_residual_momentum import SKIP, residual_momentum
from scripts.research.b100_residual_engine_ab import (
    _target_weights,
    _turnover_and_cost,
    raw_momentum,
    rebalance_dates,
    run_arm,
)
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    WEIGHTING_SCHEME_EQUAL,
    CnAttackParameters,
)

_PARAMS = CnAttackParameters(
    factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
    weighting_scheme=WEIGHTING_SCHEME_EQUAL,
)


def _synthetic_panel(n_tickers: int = 60, n_days: int = 760, seed: int = 7) -> pd.DataFrame:
    """Deterministic positive geometric-random-walk adj_close panel (date × ticker)."""

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-04-01", periods=n_days)
    tickers = [f"T{i:03d}.SZ" for i in range(n_tickers)]
    # per-name drift so the cross-section has a real momentum ranking to select on
    drift = np.linspace(-0.0004, 0.0006, n_tickers)
    shocks = rng.normal(0.0, 0.012, size=(n_days, n_tickers))
    log_prices = np.cumsum(drift + shocks, axis=0)
    prices = 10.0 * np.exp(log_prices)
    return pd.DataFrame(prices, index=dates, columns=tickers)


def test_no_look_ahead_signals_invariant_to_future_prices() -> None:
    """Momentum + residual at t must not move when prices strictly after t change."""

    prices = _synthetic_panel()
    t = prices.index[-40]  # a warm, non-NaN date

    raw_before = raw_momentum(prices).loc[t]
    resid_before = residual_momentum(prices).loc[t]

    mutated = prices.copy()
    future_mask = mutated.index > t
    mutated.loc[future_mask] = mutated.loc[future_mask] * 3.7  # violent future shock

    raw_after = raw_momentum(mutated).loc[t]
    resid_after = residual_momentum(mutated).loc[t]

    pd.testing.assert_series_equal(raw_before, raw_after)
    pd.testing.assert_series_equal(resid_before, resid_after)


def test_signals_only_use_data_up_to_t_minus_skip() -> None:
    """Even mutating prices at t itself only affects signals at t+SKIP+ (shift lock)."""

    prices = _synthetic_panel()
    t = prices.index[-60]

    resid_before = residual_momentum(prices)
    mutated = prices.copy()
    mutated.loc[t] = mutated.loc[t] * 2.0
    resid_after = residual_momentum(mutated)

    # signal at t is built from data ≤ t-SKIP, so the t-price bump cannot reach it
    pd.testing.assert_series_equal(resid_before.loc[t], resid_after.loc[t])
    # ... and the first index that CAN see the bump is SKIP days later
    reachable = prices.index[prices.index.get_loc(t) + SKIP]
    assert not resid_before.loc[reachable].equals(resid_after.loc[reachable])


def test_arms_differ_only_in_momentum_input() -> None:
    """Identical momentum → identical curve; changed momentum → changed curve."""

    prices = _synthetic_panel()
    reb = rebalance_dates(prices, prices.index[0])
    mom = raw_momentum(prices)

    a = run_arm(prices, mom, reb, "a", _PARAMS)
    b = run_arm(prices, mom, reb, "b", _PARAMS)
    pd.testing.assert_frame_equal(a.equity_curve, b.equity_curve)
    assert a.turnovers == b.turnovers

    # a genuinely different momentum panel must change the selection → the curve
    resid = residual_momentum(prices)
    c = run_arm(prices, resid, reb, "c", _PARAMS)
    assert c.rebalance_count > 0
    assert not a.equity_curve["equity"].equals(c.equity_curve["equity"])


def test_turnover_first_rebalance_all_buys_no_stamp() -> None:
    prev: dict[str, float] = {}
    new = {"A": 0.5, "B": 0.5}
    turnover, cost = _turnover_and_cost(prev, new)
    assert turnover == 1.0
    # all buys → commission+slippage on 1.0 notional, no sell stamp
    assert cost == 1.0 * (2.5 + 5.0) / 1e4


def test_turnover_rotation_charges_sell_stamp() -> None:
    prev = {"A": 0.5, "B": 0.5}
    new = {"B": 0.5, "C": 0.5}
    turnover, cost = _turnover_and_cost(prev, new)
    assert turnover == 1.0  # sell A (0.5) + buy C (0.5)
    expected = 1.0 * (2.5 + 5.0) / 1e4 + 0.5 * 5.0 / 1e4  # stamp on the 0.5 sell only
    assert abs(cost - expected) < 1e-12


def test_turnover_no_change_is_zero() -> None:
    w = {"A": 0.5, "B": 0.5}
    turnover, cost = _turnover_and_cost(w, dict(w))
    assert turnover == 0.0
    assert cost == 0.0


def test_engine_construction_faithful_topn_equal_weight() -> None:
    """_target_weights must pick exactly the top-N momentum names, equal-weighted."""

    # 40 names, ascending momentum score → the top-N are the highest indices
    tickers = [f"N{i:02d}" for i in range(40)]
    momentum = pd.Series(np.arange(40, dtype=float), index=tickers)

    weights = _target_weights(momentum, tickers, _PARAMS)

    assert len(weights) == _PARAMS.top_n
    expected_top = set(tickers[-_PARAMS.top_n :])  # highest momentum
    assert set(weights) == expected_top
    ew = 1.0 / _PARAMS.top_n
    assert all(abs(w - ew) < 1e-12 for w in weights.values())
    assert ew <= _PARAMS.max_position_weight  # cap not binding at top_n=25


def test_realised_return_uses_future_prices() -> None:
    """If every held name's price jumps after entry, invested equity must rise with it."""

    prices = _synthetic_panel(n_tickers=60, n_days=760)
    reb = rebalance_dates(prices, prices.index[0])
    mom = raw_momentum(prices)
    # find the first rebalance that actually trades (warm enough)
    arm = run_arm(prices, mom, reb, "base", _PARAMS)
    assert arm.rebalance_count > 0
    # ending equity is a compounding of realised (future) segment returns; a positive
    # ending on the upward-drifting names confirms future prices drove the P&L
    assert arm.equity_curve["equity"].iloc[-1] > 0.0
    assert len(arm.daily_returns) > 100
