"""B067 F001 — CN attack live advisory target tests (synthetic A-share data).

Drives :func:`compute_cn_attack_live_target` (and the engine's new
``final_holdings``) with injected synthetic prices + a one-block universe history
so no VM data is needed. Covers the two things the advisory producer depends on:

- the published target ALWAYS sums to 1.0 (invested names + the explicit cash row),
  so the ``save_batch`` weight-sum guard never rejects it (the head trap);
- the band decision is faithful: on a stable top-N the last day holds the
  band-managed book (winners run), and ``rebalanced`` / ``profit_take`` are wired.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.engine import (
    CnAttackBacktestConfig,
    run_cn_attack_backtest,
)
from trade.backtest.cn_attack_momentum_quality.live import (
    compute_cn_attack_live_target,
)
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    CnAttackParameters,
)

# Distinct daily growth → stable momentum ordering (top-4 = first 4 names).
_GROWTH = {
    "600519.SH": 0.0024,
    "000858.SZ": 0.0022,
    "600036.SH": 0.0020,
    "300750.SZ": 0.0018,
    "002594.SZ": 0.0016,
    "000333.SZ": 0.0014,
}
_START = date(2025, 8, 1)
_END = date(2025, 12, 31)


def _synth_prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for index, (ticker, growth) in enumerate(_GROWTH.items()):
        # A small per-name intraday gain (open→close) so the equal-notional book
        # drifts to market-value weights ≠ equal weight. The factor is constant per
        # name, so it cancels in the 12-1 momentum ratio (ordering unchanged) but
        # makes the held book genuinely value-weighted — the realistic case the live
        # producer must handle (held ≠ a fresh equal-weight signal).
        intraday = 1.0 + 0.03 * index
        for i, day in enumerate(days):
            open_price = 100.0 * (1.0 + growth) ** i
            close_price = open_price * intraday
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": open_price,
                    "high": close_price * 1.005,
                    "low": open_price * 0.995,
                    "close": close_price,
                    "adj_close": close_price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2024, 1, 1): tuple(_GROWTH)}


def _params() -> CnAttackParameters:
    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=4, max_position_weight=0.4
    )


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _synth_prices()


def test_final_holdings_decomposes_equity_to_one(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    held = result.final_holdings
    # invested market-value weights + cash fraction == 1.0 (a value decomposition).
    total = sum(w for _, w in held.weights) + held.cash_weight
    assert abs(total - 1.0) < 1e-6
    assert held.cash_weight >= 0.0
    # A fully-invested attack book holds the top-4 names (steady uptrend).
    assert len(held.weights) == 4


def test_live_target_sums_to_one_with_cash_row(prices: pd.DataFrame) -> None:
    live = compute_cn_attack_live_target(
        _params(),
        prices=prices,
        universe_history=_universe_history(),
    )
    # The persisted snapshot = invested rows + the explicit cash row; it MUST sum
    # to 1.0 (±1e-3) or save_batch refuses it (spec §3 head trap).
    total = sum(live.target_weights.values()) + live.cash_weight
    assert abs(total - 1.0) < 1e-3
    assert all(w > 0 for w in live.target_weights.values())
    assert live.cash_weight >= 0.0
    # as_of is the last trading day; the variant is carried for the surface.
    assert live.as_of_date == date(2025, 12, 31)
    assert live.factor_variant == FACTOR_VARIANT_PURE_MOMENTUM


def test_stable_top_n_holds_the_band_managed_book(prices: pd.DataFrame) -> None:
    # On a stable top-N with the default band, the last day holds the current book
    # (winners run) rather than churning — and nothing is sold (no profit-take).
    live = compute_cn_attack_live_target(
        _params(),
        CnAttackBacktestConfig(no_trade_band=0.20),
        prices=prices,
        universe_history=_universe_history(),
    )
    assert live.rebalanced is False
    assert live.profit_take == ()
    # Holding the band-managed book → the published names are the 4 held names.
    assert len(live.target_weights) == 4


def test_zero_band_rebalances_to_equal_weight_signal(prices: pd.DataFrame) -> None:
    # With a zero band even the market-value drift of a held book exceeds the band,
    # so the last day rebalances to today's (equal-weight) signal — still summing to
    # 1.0 with the cash row, and the rebalance flag is honestly set.
    live = compute_cn_attack_live_target(
        _params(),
        CnAttackBacktestConfig(no_trade_band=0.0),
        prices=prices,
        universe_history=_universe_history(),
    )
    assert live.rebalanced is True
    total = sum(live.target_weights.values()) + live.cash_weight
    assert abs(total - 1.0) < 1e-3
    # Same stable names → an equal-weight signal target (no name dropped).
    assert len(live.target_weights) == 4
    assert all(abs(w - 0.25) < 1e-6 for w in live.target_weights.values())
    # profit_take only lists names actually rotated out (none here — same top-4).
    assert live.profit_take == ()
