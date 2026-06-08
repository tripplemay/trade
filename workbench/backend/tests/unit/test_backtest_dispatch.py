"""B050 F001 — per-strategy backtest dispatch + result adapters.

The production bug: the worker hard-ran the Master backtest regardless of the
selected ``strategy_id``, so every strategy produced the same result. These
tests pin the fix at the unit level:

1. ``run_backtest_job`` dispatches by ``strategy_id`` to the right engine runner.
2. A missing ``strategy_id`` defaults to master (the canonical stand-in).
3. Research-state regime strategies raise ``InactiveStrategyError`` →
   ``error_kind=inactive_strategy`` (not a silent master fallback).
4. An unwired strategy_id raises a clear error.
5. The momentum + risk_parity adapters map each engine's distinct result shape
   to the API fields.

The ★ "different strategy → different *real* result" counter-example is the L2
job (real VM, real engines) — here we pin routing + field mapping.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from workbench_api.backtests import worker as worker_mod
from workbench_api.backtests.adapters import adapt_momentum, adapt_risk_parity
from workbench_api.backtests.error_kinds import INACTIVE_STRATEGY, classify_error_kind

# --- dispatch routing ----------------------------------------------------------


def _patch_runner(monkeypatch: pytest.MonkeyPatch, strategy_id: str, tag: str) -> None:
    monkeypatch.setitem(
        worker_mod._DISPATCH,
        strategy_id,
        lambda _snapshot, _run: {"report_markdown": tag},
    )


@pytest.mark.parametrize(
    "strategy_id",
    ["master_portfolio", "B006-global-etf-momentum", "B016-risk-parity-hrp"],
)
def test_run_backtest_job_dispatches_by_strategy_id(
    monkeypatch: pytest.MonkeyPatch, strategy_id: str
) -> None:
    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", lambda: SimpleNamespace())
    for sid in ("master_portfolio", "B006-global-etf-momentum", "B016-risk-parity-hrp"):
        _patch_runner(monkeypatch, sid, f"ran:{sid}")
    run = SimpleNamespace(run_id="r1", strategy_id=strategy_id, params={})
    result = worker_mod.run_backtest_job(run)
    assert result["report_markdown"] == f"ran:{strategy_id}"


def test_run_backtest_job_defaults_missing_strategy_id_to_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical stand-in (or any run without a strategy_id) → master."""

    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", lambda: SimpleNamespace())
    _patch_runner(monkeypatch, "master_portfolio", "ran:master")
    run = SimpleNamespace(run_id="r1", params={})  # no strategy_id attribute
    assert worker_mod.run_backtest_job(run)["report_markdown"] == "ran:master"


@pytest.mark.parametrize(
    "strategy_id", ["B013-regime-quarterly", "B014-regime-stress", "B015-regime-active"]
)
def test_inactive_strategy_raises_and_classifies(
    monkeypatch: pytest.MonkeyPatch, strategy_id: str
) -> None:
    # Snapshot must NOT be loaded for an inactive strategy (fail fast, cheap).
    def _boom() -> None:  # pragma: no cover - asserted not called
        raise AssertionError("snapshot should not load for an inactive strategy")

    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", _boom)
    run = SimpleNamespace(run_id="r1", strategy_id=strategy_id, params={})
    with pytest.raises(worker_mod.InactiveStrategyError) as excinfo:
        worker_mod.run_backtest_job(run)
    assert classify_error_kind(excinfo.value) == INACTIVE_STRATEGY


def test_unwired_strategy_id_raises_worker_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_mod, "_load_backtest_snapshot", lambda: SimpleNamespace())
    run = SimpleNamespace(run_id="r1", strategy_id="does-not-exist", params={})
    with pytest.raises(worker_mod.BacktestWorkerError, match="no backtest engine wired"):
        worker_mod.run_backtest_job(run)


# --- strategy parameter wiring -------------------------------------------------


def test_strategy_parameters_empty_dict_is_none() -> None:
    run = SimpleNamespace(run_id="r1", strategy_id="x", params={"parameters": {}})
    assert worker_mod._strategy_parameters("x", run, dict) is None
    run2 = SimpleNamespace(run_id="r1", strategy_id="x", params={})
    assert worker_mod._strategy_parameters("x", run2, dict) is None


def test_strategy_parameters_builds_override() -> None:
    from trade.strategies.risk_parity import RiskParityParameters  # type: ignore[import-untyped]

    run = SimpleNamespace(
        run_id="r1",
        strategy_id="B016-risk-parity-hrp",
        params={"parameters": {"target_volatility": 0.12}},
    )
    built = worker_mod._strategy_parameters("B016-risk-parity-hrp", run, RiskParityParameters)
    assert built is not None and built.target_volatility == 0.12


def test_strategy_parameters_bad_keys_raise_worker_error() -> None:
    run = SimpleNamespace(
        run_id="r1", strategy_id="x", params={"parameters": {"nope": 1}}
    )

    class _P:
        def __init__(self) -> None:  # accepts no kwargs
            pass

    with pytest.raises(worker_mod.BacktestWorkerError, match="invalid parameters"):
        worker_mod._strategy_parameters("x", run, _P)


# --- adapters (per-engine result shape) ----------------------------------------


def _fill(symbol: str, weight: float, price: float) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        target_weight=weight,
        execution_price=price,
        execution_date=date(2024, 2, 1),
    )


def _equity_point(d: date, v: float) -> SimpleNamespace:
    return SimpleNamespace(date=d, value=v)


def test_adapt_momentum_maps_nested_rebalances() -> None:
    sub = SimpleNamespace(
        signal=SimpleNamespace(
            signal_date=date(2024, 1, 31), target_weights={"SPY": 0.6, "AGG": 0.4}
        ),
        fills=(_fill("SPY", 0.6, 100.0), _fill("AGG", 0.4, 50.0)),
        starting_capital=10_000.0,
    )
    result = SimpleNamespace(
        equity_curve=(
            _equity_point(date(2024, 1, 1), 10_000.0),
            _equity_point(date(2024, 2, 1), 10_500.0),
        ),
        rebalance_results=(sub,),
    )
    mapped = adapt_momentum(result)
    assert mapped["equity"] == [
        {"date": "2024-01-01", "nav": 10_000.0},
        {"date": "2024-02-01", "nav": 10_500.0},
    ]
    assert mapped["allocations"] == [
        {"date": "2024-01-31", "weights": {"SPY": 0.6, "AGG": 0.4}}
    ]
    # notional = target_weight × starting_capital; quantity = notional / price.
    spy = next(t for t in mapped["trades"] if t["symbol"] == "SPY")
    assert spy["notional"] == round(0.6 * 10_000.0, 2)
    assert spy["quantity"] == round(6_000.0 / 100.0, 6)
    assert spy["side"] == "buy"


def test_adapt_risk_parity_uses_signal_weights_and_ending_value() -> None:
    period = SimpleNamespace(
        signal=SimpleNamespace(
            signal_date=date(2024, 1, 31), target_weights={"SPY": 0.5, "SGOV": 0.5}
        ),
        fills=(_fill("SPY", 0.5, 100.0),),
        ending_value=20_000.0,
    )
    result = SimpleNamespace(
        equity_curve=(_equity_point(date(2024, 1, 1), 20_000.0),),
        rebalance_results=(period,),
    )
    mapped = adapt_risk_parity(result)
    assert mapped["allocations"] == [
        {"date": "2024-01-31", "weights": {"SPY": 0.5, "SGOV": 0.5}}
    ]
    spy = mapped["trades"][0]
    assert spy["notional"] == round(0.5 * 20_000.0, 2)  # ending_value as base


def test_adapt_skips_fills_without_executable_price() -> None:
    sub = SimpleNamespace(
        signal=SimpleNamespace(signal_date=date(2024, 1, 31), target_weights={"SPY": 1.0}),
        fills=(_fill("SPY", 1.0, 0.0),),  # missing T+1 open → price 0 → skipped
        starting_capital=10_000.0,
    )
    result = SimpleNamespace(equity_curve=(), rebalance_results=(sub,))
    assert adapt_momentum(result)["trades"] == []
