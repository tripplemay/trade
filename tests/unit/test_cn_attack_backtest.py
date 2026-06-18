"""B066 F002 — CN attack daily-driver backtest engine tests (synthetic A-share data).

Synthetic prices give 6 names distinct steady uptrends (stable top-N → the
no-trade band holds most days) plus a ~28% mid-window V-dip (so trailing stops
fire). The engine is driven with injected prices + a one-block universe history,
so no VM data is needed. Covers: non-degenerate equity, band-holds-most-days,
the 3 exit variants (momentum_decay never forces an exit; trailing_stop fires on
the dip; hard_profit_target fires on gains) producing different results, and that
directional costs are actually charged.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
from trade.backtest.cn_attack_momentum_quality.engine import (
    EXIT_HARD_PROFIT_TARGET,
    EXIT_MOMENTUM_DECAY,
    EXIT_TRAILING_STOP,
    CnAttackBacktestConfig,
    CnBacktestError,
    run_cn_attack_backtest,
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
_DIP_CENTER = pd.Timestamp("2025-09-15")
_START = date(2025, 8, 1)
_END = date(2025, 12, 31)


def _envelope(day: pd.Timestamp) -> float:
    # V-shaped ~28% correction: trough 0.72 at the center, flat 1.0 elsewhere.
    delta = (day - _DIP_CENTER).days
    if -20 <= delta <= 0:
        return 1.0 - 0.28 * (delta + 20) / 20
    if 0 < delta <= 25:
        return 0.72 + 0.28 * delta / 25
    return 1.0


def _synth_prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for ticker, growth in _GROWTH.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i * _envelope(day)
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


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2024, 1, 1): tuple(_GROWTH)}


def _params() -> CnAttackParameters:
    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=4, max_position_weight=0.4
    )


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _synth_prices()


def test_runs_non_degenerate_equity(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(exit_variant=EXIT_MOMENTUM_DECAY),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    assert result.trading_days > 50
    assert len(result.equity_curve) == result.trading_days
    assert result.equity_curve["equity"].nunique() > 10  # not flat
    assert result.ending_value > 0
    assert result.total_turnover > 0  # at least the initial investment traded
    assert result.rebalance_count >= 1


def test_no_trade_band_holds_most_days(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(exit_variant=EXIT_MOMENTUM_DECAY, no_trade_band=0.20),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    traded_days = sum(
        1 for r in result.daily_records if r.rebalanced or r.forced_exits
    )
    # Most days hold: a stable top-N + band means rebalances are the exception.
    assert traded_days < result.trading_days * 0.3


def test_momentum_decay_never_forces_an_exit(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(exit_variant=EXIT_MOMENTUM_DECAY),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    assert result.exit_count == 0
    assert all(not r.forced_exits for r in result.daily_records)


def test_trailing_stop_fires_on_the_dip(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(
            exit_variant=EXIT_TRAILING_STOP, trailing_stop_pct=0.20
        ),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    # The ~28% V-dip pushes held names > 20% below their peak → forced exits.
    assert result.exit_count > 0


def test_hard_profit_target_fires_on_gains(prices: pd.DataFrame) -> None:
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(
            exit_variant=EXIT_HARD_PROFIT_TARGET, profit_target_pct=0.10
        ),
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    # Steady uptrends cross the +10% target → forced profit-taking exits.
    assert result.exit_count > 0


def test_three_exit_variants_produce_different_results(prices: pd.DataFrame) -> None:
    def run(variant: str, **kw: float):  # type: ignore[no-untyped-def]
        return run_cn_attack_backtest(
            _params(),
            CnAttackBacktestConfig(exit_variant=variant, **kw),  # type: ignore[arg-type]
            _START,
            _END,
            prices=prices,
            universe_history=_universe_history(),
        )

    decay = run(EXIT_MOMENTUM_DECAY)
    trailing = run(EXIT_TRAILING_STOP, trailing_stop_pct=0.20)
    profit = run(EXIT_HARD_PROFIT_TARGET, profit_target_pct=0.10)
    endings = {
        round(decay.ending_value, 2),
        round(trailing.ending_value, 2),
        round(profit.ending_value, 2),
    }
    # The exit overlays change the trajectory → not all three identical.
    assert len(endings) == 3


def test_directional_cost_is_charged(prices: pd.DataFrame) -> None:
    cost_model = CnCostModel(stamp_duty_bps=10.0, commission_bps=2.5, slippage_bps=5.0)
    config = CnAttackBacktestConfig(exit_variant=EXIT_MOMENTUM_DECAY, cost_model=cost_model)
    result = run_cn_attack_backtest(
        _params(),
        config,
        _START,
        _END,
        prices=prices,
        universe_history=_universe_history(),
    )
    assert result.total_cost > 0
    # The first executed trade is the all-cash → invest leg: pure BUYS, so its cost
    # must use buy_rate (no stamp duty), NOT sell_rate. At that point equity_open ==
    # starting_capital (all cash, no positions yet), so the cost is exactly
    # turnover * starting_capital * buy_rate — proving the directional asymmetry.
    first_exec = next(r for r in result.daily_records if r.executed_turnover > 0)
    buy_cost = first_exec.executed_turnover * config.starting_capital * cost_model.buy_rate()
    sell_cost = first_exec.executed_turnover * config.starting_capital * cost_model.sell_rate()
    assert first_exec.executed_cost == pytest.approx(buy_cost, rel=1e-9)
    assert first_exec.executed_cost < sell_cost  # stamp duty NOT charged on the buy


def test_halted_holding_carries_value_no_nan_no_leak() -> None:
    # A-share 停牌 (halt): a held top name has NO price rows for a mid-window window.
    # The pivot yields NaN there; the engine must forward-fill (carry last price) so
    # (a) the equity curve has NO NaN and (b) the name's value is NOT leaked (the
    # pre-fix rebalance branch dropped it → ~25% equity collapse on a 4-name book).
    full = _synth_prices()
    baseline = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(),
        _START,
        _END,
        prices=full,
        universe_history=_universe_history(),
    )
    halt_lo, halt_hi = pd.Timestamp("2025-10-06"), pd.Timestamp("2025-10-17")
    halted = full[
        ~(
            (full["ticker"] == "600519.SH")
            & (full["date"] >= halt_lo)
            & (full["date"] <= halt_hi)
        )
    ].reset_index(drop=True)
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(),
        _START,
        _END,
        prices=halted,
        universe_history=_universe_history(),
    )
    assert not result.equity_curve["equity"].isna().any()  # NaN-poison bug #2 guard
    # Value conserved through the halt: no ~25% collapse from a vanished holding.
    assert result.ending_value == pytest.approx(baseline.ending_value, rel=0.05)


def test_needs_two_trading_days() -> None:
    prices = _synth_prices()
    with pytest.raises(CnBacktestError, match=">= 2 trading days"):
        run_cn_attack_backtest(
            _params(),
            CnAttackBacktestConfig(),
            date(2025, 12, 31),
            date(2025, 12, 31),
            prices=prices,
            universe_history=_universe_history(),
        )


def test_invalid_exit_variant_rejected() -> None:
    with pytest.raises(CnBacktestError, match="exit_variant"):
        CnAttackBacktestConfig(exit_variant="sentiment_flip")
