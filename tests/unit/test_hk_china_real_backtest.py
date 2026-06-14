"""B063 F003 — standalone real-data HK-China quarterly backtest engine.

Pins that the engine (a) drives the real strategy's construction over a wide
USD universe and produces a non-degenerate result isomorphic to the proxy
engine (equity curve + fills + per-period signal weights + RealPortfolio
provenance), (b) goes fully defensive when nothing passes, and (c) applies the
defensive fallback when the USD records don't price a chosen name on the signal
date (so execution can't KeyError).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trade.backtest.hk_china_real import (
    _resolve_real_signal,
    run_real_hk_china_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_AS_OF = date(2024, 6, 28)
_RISERS = ("3690.HK", "1810.HK", "9618.HK", "0939.HK", "0883.HK")
_BELLWETHERS = ("0700.HK", "9988.HK", "600519.SH")
_DEFENSIVE = "SGOV"


def _usd_ramp(
    specs: dict[str, tuple[float, float]],
    *,
    as_of: date = _AS_OF,
    n_days: int = 460,
) -> pd.DataFrame:
    """USD long-format daily OHLCV: each ticker a linear ramp ending at ``as_of``
    (one bar per calendar day so the 200D MA + 12m momentum anchors resolve)."""

    start_day = as_of - timedelta(days=n_days - 1)
    rows: list[dict[str, object]] = []
    for ticker, (start, end) in specs.items():
        for i in range(n_days):
            d = start_day + timedelta(days=i)
            close = start + (end - start) * (i / (n_days - 1))
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "ticker": ticker,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def _rising_universe() -> dict[str, tuple[float, float]]:
    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})  # rising → not risk-off
    specs[_DEFENSIVE] = (100.0, 100.0)  # flat cash-like defensive asset
    return specs


def test_real_backtest_non_degenerate_and_isomorphic() -> None:
    frame = _usd_ramp(_rising_universe())
    signal_dates = (date(2024, 6, 10), date(2024, 6, 20))
    result = run_real_hk_china_quarterly_backtest(
        frame,
        signal_dates,
        HkChinaRealParameters(top_n=3),
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )
    assert result.starting_capital == 100_000.0
    assert result.ending_value > 0
    assert len(result.rebalance_results) == 2
    assert len(result.equity_curve) == 3
    first = result.rebalance_results[0]
    # Selected the 3 highest-momentum risers; provenance recorded.
    assert set(first.signal.target_weights) <= set(_RISERS) | {_DEFENSIVE}
    assert first.signal.is_defensive is False
    assert first.portfolio.scored >= 5
    assert {fill.execution_price_field for fill in first.fills} == {"open"}


def test_real_backtest_defensive_when_all_decline() -> None:
    specs = {t: (60.0, 30.0) for t in _RISERS + _BELLWETHERS}  # all decline
    specs[_DEFENSIVE] = (100.0, 100.0)
    frame = _usd_ramp(specs)
    result = run_real_hk_china_quarterly_backtest(
        frame, (date(2024, 6, 10),), HkChinaRealParameters()
    )
    signal = result.rebalance_results[0].signal
    assert signal.target_weights == {_DEFENSIVE: 1.0}
    assert signal.is_defensive is True


def test_resolve_real_signal_defensive_fallback_when_uncovered() -> None:
    # The construction selects 3690.HK (rising, passes trend), but the USD records
    # don't price it on the signal date (coverage set = {SGOV} only) → the engine
    # must fall back to the defensive asset so execution can't KeyError. This is
    # the defense-in-depth coverage branch (mirrors the proxy engine's fallback).
    frame = _usd_ramp({"3690.HK": (40.0, 90.0), _DEFENSIVE: (100.0, 100.0)})
    signal, portfolio = _resolve_real_signal(
        frame, HkChinaRealParameters(top_n=1), _AS_OF, frozenset({_DEFENSIVE})
    )
    assert portfolio.selected == ("3690.HK",)  # construction DID select it
    assert signal.target_weights == {_DEFENSIVE: 1.0}  # but coverage fallback fired
    assert signal.is_defensive is True
