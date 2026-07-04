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

# B076 F001 — market cap inversely aligned with momentum: the smallest caps are the
# lowest-momentum names, so a strong size tilt displaces the blue-chip leaders.
_MARKET_CAPS = {
    "600519.SH": 2.0e12,
    "000858.SZ": 1.0e12,
    "600036.SH": 8.0e11,
    "300750.SZ": 5.0e9,
    "002594.SZ": 2.0e9,
    "000333.SZ": 1.0e9,
}


def _synth_marketcap() -> pd.DataFrame:
    # One observation per name well before the window → covers every rebalance day.
    rows = [
        {"data_date": pd.Timestamp("2024-01-01"), "ticker": ticker, "market_cap": cap}
        for ticker, cap in _MARKET_CAPS.items()
    ]
    return pd.DataFrame(rows)

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
    # This test verifies the AGGREGATE no-trade band's hold behavior, which B081
    # F001(3) Option A deliberately bypasses (partial rebalance uses the per-name
    # threshold instead), so it pins partial_rebalance=False (the full-band口径).
    result = run_cn_attack_backtest(
        _params(),
        CnAttackBacktestConfig(
            exit_variant=EXIT_MOMENTUM_DECAY, no_trade_band=0.20, partial_rebalance=False
        ),
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


# --------------------------------------------------------------------------- #
# B076 F001 — size-tilt selection through the backtest engine
# --------------------------------------------------------------------------- #


def test_size_tilt_active_without_marketcap_raises(prices: pd.DataFrame) -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
        top_n=4,
        max_position_weight=0.4,
        size_tilt_weight=0.3,
    )
    with pytest.raises(CnBacktestError, match="non-empty marketcap"):
        run_cn_attack_backtest(
            params, None, _START, _END, prices=prices, universe_history=_universe_history()
        )
    # An empty-but-non-None frame is equally fatal (would silently yield all-cash).
    empty = pd.DataFrame(columns=["data_date", "ticker", "market_cap"])
    with pytest.raises(CnBacktestError, match="non-empty marketcap"):
        run_cn_attack_backtest(
            params, None, _START, _END, prices=prices,
            marketcap=empty, universe_history=_universe_history(),
        )


def test_strong_size_tilt_changes_the_selected_basket(prices: pd.DataFrame) -> None:
    common = dict(start=_START, end=_END, prices=prices, universe_history=_universe_history())
    baseline = run_cn_attack_backtest(_params(), None, **common)
    tilted = run_cn_attack_backtest(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
            top_n=4,
            max_position_weight=0.4,
            size_tilt_weight=0.6,
        ),
        None,
        marketcap=_synth_marketcap(),
        **common,
    )

    def _selected(result: object) -> set[str]:
        names: set[str] = set()
        for record in result.daily_records:  # type: ignore[attr-defined]
            names.update(record.target_tickers)
        return names

    base_names = _selected(baseline)
    tilt_names = _selected(tilted)
    # Baseline = blue-chip momentum leaders; the smallest caps never enter.
    assert "600519.SH" in base_names
    assert "000333.SZ" not in base_names
    # Strong size tilt pulls the two smallest caps in and drops the biggest leader.
    assert {"000333.SZ", "002594.SZ"} <= tilt_names
    assert tilt_names != base_names


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


def test_lot_rounding_conserves_equity_and_skips_sublot() -> None:
    # B081 F001(2) — round-lot realism: buys floor to whole 100-share lots, the
    # rounding remainder returns to cash (余额守恒), and a name too small for one lot
    # is skipped (跳过留现金). White-box on _execute_open (the fill site).
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import _execute_open, _Pending

    open_row = pd.Series({"AAA": 30.0, "BBB": 70.0, "TINY": 1000.0})
    pending = _Pending(kind="rebalance", target={"AAA": 0.5, "BBB": 0.49, "TINY": 0.01})
    new_shares, new_cash, _turnover, cost = _execute_open(
        {}, 100_000.0, open_row, pending, CnCostModel(), {}, {}, lot_rounding=True
    )
    # Every held quantity is a whole 100-lot.
    assert new_shares and all(qty % 100.0 == 0.0 for qty in new_shares.values())
    # TINY's target (~1 share) can't afford one lot → skipped, its notional is cash.
    assert "TINY" not in new_shares and {"AAA", "BBB"} <= set(new_shares)
    # 余额守恒: invested + cash == investable (== equity_open - cost).
    invested = sum(qty * open_row[t] for t, qty in new_shares.items())
    assert invested + new_cash == pytest.approx(100_000.0 - cost, rel=1e-12)


def test_lot_rounding_off_is_fractional_old_kou_jing() -> None:
    # With the switch off (old口径), shares stay fractional — the pre-B081 behavior
    # the zero-regression tests pin for bit-level reproduction.
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import _execute_open, _Pending

    open_row = pd.Series({"AAA": 30.0, "BBB": 70.0})
    pending = _Pending(kind="rebalance", target={"AAA": 0.5, "BBB": 0.5})
    new_shares, _cash, _turnover, _cost = _execute_open(
        {}, 100_000.0, open_row, pending, CnCostModel(), {}, {}, lot_rounding=False
    )
    assert any(qty % 100.0 != 0.0 for qty in new_shares.values())


def test_partial_rebalance_preserves_kept_shares_trades_significant() -> None:
    # B081 F001(3) Option A — a partial rebalance keeps a small-drift name's EXACT
    # shares (no trade) and trades only entering/big-drift names. Per-rebalance this
    # trades fewer names than the full re-target (换手<全量 per rebalance).
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
    from trade.backtest.cn_attack_momentum_quality.engine import _partial_rebalance_open

    open_row = pd.Series({"AAA": 30.0, "BBB": 70.0, "NEW": 50.0})

    def price(t: str) -> float:
        return float(open_row[t])

    shares = {"AAA": 1000.0, "BBB": 500.0}  # AAA 30k, BBB 35k, cash 35k → equity 100k
    current_notional = {"AAA": 30_000.0, "BBB": 35_000.0}
    # AAA weight 0.30 unchanged (kept); BBB 0.35→0.50 (traded); NEW enters at 0.15.
    priced_target = {"AAA": 0.30, "BBB": 0.50, "NEW": 0.15}
    new_shares, new_cash, _buy, _sell, cost = _partial_rebalance_open(
        shares, current_notional, 100_000.0, priced_target, price,
        CnCostModel(), 0.005, False,
    )
    assert new_shares["AAA"] == 1000.0  # kept: exact shares preserved, no trade
    assert new_shares["BBB"] != 500.0  # traded (0.15 drift > threshold)
    assert "NEW" in new_shares  # entering → traded
    invested = sum(q * price(t) for t, q in new_shares.items())
    assert invested + new_cash == pytest.approx(100_000.0 - cost, rel=1e-12)


def test_delist_confirmation_detection() -> None:
    # B081 F002 — delist detection: a name whose bars STOP is confirmed delisted
    # exactly delist_confirm_days trading days after its FINAL real bar; a name trading
    # throughout never confirms. Uses the pre-ffill pivot to see real bars vs carries.
    import pandas as pd

    from trade.backtest.cn_attack_momentum_quality.engine import _delist_confirmations

    dates = [date(2025, 1, d) for d in range(1, 11)]  # 10 consecutive "trading" days
    rows: list[dict[str, object]] = []
    for i, d in enumerate(dates):
        rows.append({"date": pd.Timestamp(d), "ticker": "STAYS", "adj_close": 100.0})
        if i <= 2:  # DELIST has a real bar only through position 2, then stops
            rows.append({"date": pd.Timestamp(d), "ticker": "DELIST", "adj_close": 50.0})
    conf = _delist_confirmations(pd.DataFrame(rows), dates, confirm_days=3)
    # Last real bar at position 2 → confirmation at position 2 + 3 = 5 (date Jan 6).
    assert conf.get(date(2025, 1, 6)) == {"DELIST"}
    # STAYS trades throughout → never confirmed delisted.
    assert all("STAYS" not in names for names in conf.values())
    # A shorter/longer confirm window shifts the date deterministically.
    conf2 = _delist_confirmations(pd.DataFrame(rows), dates, confirm_days=5)
    assert conf2.get(date(2025, 1, 8)) == {"DELIST"}  # position 2 + 5 = 7 (Jan 8)


def test_partial_rebalance_threshold_controls_churn(prices: pd.DataFrame) -> None:
    # Option A: the per-name threshold is the sole churn filter — a wider threshold
    # trades fewer names → strictly lower cumulative turnover.
    def turnover(thr: float) -> float:
        return run_cn_attack_backtest(
            _params(),
            CnAttackBacktestConfig(partial_rebalance=True, per_name_rebalance_threshold=thr),
            _START, _END, prices=prices, universe_history=_universe_history(),
        ).total_turnover

    assert turnover(0.05) < turnover(0.005)


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
