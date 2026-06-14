"""B050 F003 — standalone HK-China quarterly backtest engine.

Pins that the new standalone engine (a) reuses the SAME signal generator the
Master uses (no divergent signal logic), (b) produces a non-degenerate result
isomorphic to risk_parity (equity curve + fills + per-period signal weights),
and (c) applies the Master's defensive fallback when records don't cover the
chosen tickers. The signal generator is monkeypatched so the engine is exercised
without the HK-China fixture data (the signal itself is covered by its own
strategy tests).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trade.backtest import hk_china as hk_china_engine
from trade.backtest.hk_china import run_hk_china_quarterly_backtest
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters


class _FakeSignal:
    def __init__(self, weights: dict[str, float], *, defensive: bool = False) -> None:
        self._weights = weights
        self._defensive = defensive
        self.parameters_hash = "fake-hash"

    def weights_dict(self) -> dict[str, float]:
        return self._weights

    def is_defensive(self) -> bool:
        return self._defensive


def _history(symbols: tuple[str, ...], observations: int) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for symbol_index, symbol in enumerate(symbols):
        price = 100.0 + symbol_index * 10.0
        for index in range(observations):
            if index:
                price *= 1.0 + (0.003 * (symbol_index + 1) if index % 2 else -0.002)
            records.append(
                PriceBar(
                    date=start + timedelta(days=index),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
    return tuple(records)


def test_hk_china_backtest_uses_shared_signal_and_is_isomorphic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _history(("MCHI", "FXI", "SGOV"), 90)
    calls: list[date] = []

    def _fake(
        params: HkChinaMomentumParameters, signal_date: date, *, prices: object = None
    ) -> _FakeSignal:
        calls.append(signal_date)
        return _FakeSignal({"MCHI": 0.5, "FXI": 0.5})

    monkeypatch.setattr(hk_china_engine, "generate_hk_china_signal", _fake)

    result = run_hk_china_quarterly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        HkChinaMomentumParameters(),
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    # Same-source: the shared signal generator was invoked per signal date.
    assert calls == [date(2024, 3, 10), date(2024, 3, 20)]
    # Non-degenerate + isomorphic to risk_parity.
    assert result.starting_capital == 100_000.0
    assert result.ending_value > 0
    assert len(result.rebalance_results) == 2
    assert len(result.equity_curve) == 3
    first = result.rebalance_results[0]
    assert first.signal.signal_date == date(2024, 3, 10)
    assert first.signal.target_weights == {"MCHI": 0.5, "FXI": 0.5}
    assert {fill.execution_price_field for fill in first.fills} == {"open"}


def test_signal_prices_is_threaded_to_the_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # B063 F003 — the optional signal_prices is forwarded to the signal generator
    # so the comparison harness can pin signal + execution to one frame. Default
    # (None) preserves the self-loading behaviour (Master / B050 unchanged).
    records = _history(("MCHI", "FXI", "SGOV"), 90)
    seen_prices: list[object] = []

    def _fake(params: HkChinaMomentumParameters, signal_date: date, *, prices=None):  # type: ignore[no-untyped-def]
        seen_prices.append(prices)
        return _FakeSignal({"MCHI": 1.0})

    monkeypatch.setattr(hk_china_engine, "generate_hk_china_signal", _fake)

    # Default: prices not pinned → None reaches the signal (unchanged behaviour).
    run_hk_china_quarterly_backtest(records, (date(2024, 3, 10),))
    assert seen_prices == [None]

    # Pinned: the exact frame is forwarded.
    seen_prices.clear()
    frame = object()
    run_hk_china_quarterly_backtest(
        records, (date(2024, 3, 10),), signal_prices=frame  # type: ignore[arg-type]
    )
    assert seen_prices == [frame]


def test_hk_china_backtest_defensive_fallback_when_tickers_uncovered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Records cover only SGOV — the signal picks KWEB (uncovered) → fall back to
    # 100% defensive (same behaviour as the Master sleeve).
    records = _history(("SGOV",), 90)
    monkeypatch.setattr(
        hk_china_engine,
        "generate_hk_china_signal",
        lambda params, d, prices=None: _FakeSignal({"KWEB": 1.0}),
    )

    result = run_hk_china_quarterly_backtest(records, (date(2024, 3, 10),))
    signal = result.rebalance_results[0].signal
    assert signal.target_weights == {"SGOV": 1.0}
    assert signal.is_defensive is True
