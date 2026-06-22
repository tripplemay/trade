"""B075 F002 — permanent acceptance guard: cn_attack selects top-25 from a WIDE pool.

The batch widens the cn_attack input universe from ~43 seed blue chips to the full
liquid market (top ~1500). The strategy LOGIC is unchanged (spec §0: 不改策略逻辑)
— it still equal-weights its top-N (default 25). This guard pins the product claim
that matters: given a wide point-in-time universe, the live advisory target is the
top-25 *by the strategy's own ranking* drawn from that wide pool — not a fixed
short list, and never more than top_n names.

Pure synthetic injection (no VM / no network): a 60-name universe with strictly
decreasing momentum, so the deterministic top-25 are the 25 strongest names. With a
zero no-trade band the last day rebalances to the fresh equal-weight signal, so the
selection is unambiguous.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.engine import CnAttackBacktestConfig
from trade.backtest.cn_attack_momentum_quality.live import (
    compute_cn_attack_live_target,
)
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    CnAttackParameters,
)

_WIDE_N = 60
_TOP_N = 25
# Strictly decreasing daily growth → a stable, unambiguous momentum ranking
# (name 0 strongest … name 59 weakest). Top-25 = the first 25 names.
_TICKERS: tuple[str, ...] = tuple(f"{600000 + i}.SH" for i in range(_WIDE_N))
_GROWTH: dict[str, float] = {
    ticker: 0.0030 - 0.00004 * i for i, ticker in enumerate(_TICKERS)
}


def _wide_prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for ticker, growth in _GROWTH.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.005,
                    "low": price * 0.995,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _wide_universe_history() -> dict[date, tuple[str, ...]]:
    # One point-in-time block carrying the full wide pool (all 60 names eligible).
    return {date(2024, 1, 1): _TICKERS}


def _params() -> CnAttackParameters:
    return CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=_TOP_N)


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _wide_prices()


def test_cn_attack_selects_exactly_top_n_from_wide_pool(prices: pd.DataFrame) -> None:
    live = compute_cn_attack_live_target(
        _params(),
        CnAttackBacktestConfig(no_trade_band=0.0),  # force rebalance to today's signal
        prices=prices,
        universe_history=_wide_universe_history(),
    )
    # Exactly top_n names selected out of the wide 60-name pool (not the whole pool).
    assert live.rebalanced is True
    assert len(live.target_weights) == _TOP_N
    # The selected names are the 25 strongest-momentum names (the true top-25).
    expected_top = set(_TICKERS[:_TOP_N])
    assert set(live.target_weights) == expected_top
    # …and the weaker tail is excluded — proving it ranked the WIDE pool, not a
    # fixed short list.
    assert set(live.target_weights).isdisjoint(set(_TICKERS[_TOP_N:]))
    # Equal-weight signal + cash row sums to 1.0 (the head-trap invariant holds at
    # wide scale too).
    total = sum(live.target_weights.values()) + live.cash_weight
    assert abs(total - 1.0) < 1e-3


def test_wide_pool_target_is_well_formed(prices: pd.DataFrame) -> None:
    live = compute_cn_attack_live_target(
        _params(),
        CnAttackBacktestConfig(no_trade_band=0.0),
        prices=prices,
        universe_history=_wide_universe_history(),
    )
    # No single name breaches the position cap, and all weights are positive.
    cap = _params().max_position_weight + 1e-9
    assert all(0.0 < w <= cap for w in live.target_weights.values())
    assert live.cash_weight >= 0.0
    assert live.as_of_date == date(2025, 12, 31)
