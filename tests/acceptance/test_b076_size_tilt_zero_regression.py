"""B076 F002 — permanent acceptance guard: ``size_tilt_weight=0`` is zero-regression.

The B076 verdict is **NO-GO** (the de-biased backtest found the size tilt degrades
full-sample risk-adjusted return — docs/test-reports/B076-size-tilt-comparison.md), so
production keeps ``size_tilt_weight`` at its default ``0``. This guard pins the invariant
that makes that safe: with the default, the cn_attack live selection is IDENTICAL to the
pre-B076 behaviour AND never reads market cap — turning the knob on is the ONLY thing that
changes selection, and production never turns it on (verdict-gated, B069 NO-SWITCH).

Pure synthetic injection (no VM / no network): a 12-name universe with strictly decreasing
momentum (name 0 strongest) and INVERSE market caps (name 0 biggest), so a size tilt would
visibly swap the blue-chip leaders for the small-cap tail — and the default must NOT.
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
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    SIZE_FACTOR_KEY,
    CnAttackParameters,
)

_N = 12
_TOP_N = 6
_MPW = 0.20  # top_n * max_position_weight = 1.2 >= 1.0 (cap reachable)
_TICKERS: tuple[str, ...] = tuple(f"{600000 + i}.SH" for i in range(_N))
# Strictly decreasing momentum: name 0 strongest … name 11 weakest → top-6 = names 0-5.
_GROWTH: dict[str, float] = {t: 0.0030 - 0.00018 * i for i, t in enumerate(_TICKERS)}
# INVERSE market cap: name 0 biggest … name 11 smallest, so a size tilt pulls the tail in.
_CAPS: dict[str, float] = {t: 2.0e12 / (1.0 + i) for i, t in enumerate(_TICKERS)}
# force rebalance to today's signal; lot_rounding=False keeps the OLD口径 so this
# SELECTION zero-regression test is unaffected by B081 F001(2) round-lot skipping
# (the small synthetic capital would otherwise floor every sub-lot name to zero).
_NO_BAND = CnAttackBacktestConfig(no_trade_band=0.0, lot_rounding=False)


def _prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-01-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for ticker, growth in _GROWTH.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i
            rows.append(
                {
                    "date": day, "ticker": ticker,
                    "open": price, "high": price * 1.005, "low": price * 0.995,
                    "close": price, "adj_close": price, "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _marketcap() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"data_date": pd.Timestamp("2024-01-01"), "ticker": t, "market_cap": cap}
            for t, cap in _CAPS.items()
        ]
    )


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2024, 1, 1): _TICKERS}


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _prices()


def _final_basket(params: CnAttackParameters, marketcap: pd.DataFrame | None) -> set[str]:
    result = run_cn_attack_backtest(
        params, _NO_BAND, prices=_prices(), marketcap=marketcap,
        universe_history=_universe_history(),
    )
    return {ticker for ticker, _ in result.final_holdings.weights}


def test_default_params_have_no_size_factor() -> None:
    # Both production variants default to size off → the composite carries no size key,
    # so the production scorer never even loads market cap.
    for variant in (FACTOR_VARIANT_PURE_MOMENTUM, FACTOR_VARIANT_QUALITY_MOMENTUM):
        params = CnAttackParameters(factor_variant=variant)
        assert params.size_tilt_weight == 0.0
        assert SIZE_FACTOR_KEY not in params.factor_weight_mapping()


def test_production_live_target_selects_blue_chip_momentum_without_marketcap(
    prices: pd.DataFrame,
) -> None:
    # The production live path (compute_cn_attack_live_target) takes NO marketcap arg and
    # must still produce the top-N momentum basket — proving the default needs no size data.
    live = compute_cn_attack_live_target(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=_TOP_N, max_position_weight=_MPW
        ),
        _NO_BAND, prices=prices, universe_history=_universe_history(),
    )
    assert set(live.target_weights) == set(_TICKERS[:_TOP_N])  # the 6 strongest momentum


def test_size_zero_selection_is_identical_with_or_without_marketcap() -> None:
    # ★ Zero-regression core: size_tilt_weight=0 ignores market cap entirely, so injecting
    # an (inverse) cap frame changes NOTHING — the selection equals the pre-B076 basket.
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=_TOP_N, max_position_weight=_MPW
    )
    without = _final_basket(params, None)
    with_caps = _final_basket(params, _marketcap())
    assert without == with_caps == set(_TICKERS[:_TOP_N])


def test_size_tilt_on_would_change_selection_so_off_is_a_real_choice() -> None:
    # The knob is a REAL lever: turning it on swaps blue chips for the small-cap tail. The
    # default keeps it OFF (NO-GO), so this difference is exactly what production avoids.
    off = _final_basket(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=_TOP_N, max_position_weight=_MPW
        ),
        None,
    )
    on = _final_basket(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=_TOP_N,
            max_position_weight=_MPW, size_tilt_weight=0.5,
        ),
        _marketcap(),
    )
    assert on != off  # the tilt changes selection…
    assert on & set(_TICKERS[_TOP_N:])  # …pulling small-cap-tail names in (off never does)
    assert off == set(_TICKERS[:_TOP_N])
