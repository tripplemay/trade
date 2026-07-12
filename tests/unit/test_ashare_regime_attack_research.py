from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from types import ModuleType

import pandas as pd


def _load_runner() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts/test/ashare_regime_attack_research.py"
    )
    spec = importlib.util.spec_from_file_location("ashare_regime_attack_research", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def test_monthly_regime_does_not_use_future_closes() -> None:
    dates = pd.bdate_range("2023-01-02", periods=320)
    frame = pd.DataFrame(
        {"date": dates, "close": [100.0 + index * 0.1 for index in range(len(dates))]}
    )
    as_of = dates[-15]
    schedule = RUNNER._build_regime_schedule(frame)
    original_source = schedule.source_date_on(as_of.date())
    original_state = schedule.state_on(as_of.date())

    changed = frame.copy()
    changed.loc[changed["date"] > as_of, "close"] = 1.0
    changed_schedule = RUNNER._build_regime_schedule(changed)

    assert original_source <= as_of.date()
    assert changed_schedule.source_date_on(as_of.date()) == original_source
    assert changed_schedule.state_on(as_of.date()) is original_state


def test_risk_off_empty_target_forces_retry_below_aggregate_band() -> None:
    from trade.backtest.cn_attack_momentum_quality import engine as engine_module

    class Parameters:
        factor_variant = "pure_momentum"

        def parameter_hash(self) -> str:
            return "hash"

    original_signal = engine_module.generate_cn_attack_signal
    original_turnover = engine_module._would_be_turnover
    schedule = RUNNER.RegimeSchedule(
        states=pd.Series(
            [False], index=pd.DatetimeIndex([pd.Timestamp("2020-01-31")])
        )
    )

    with RUNNER._regime_signal_gate(schedule) as counters:
        signal = engine_module.generate_cn_attack_signal(
            Parameters(),
            date(2020, 2, 3),
            prices=pd.DataFrame(),
            universe_members=("AAA",),
        )
        forced = engine_module._would_be_turnover({"AAA": 0.10}, {})
        assert signal.weights_dict() == {}
        assert forced > 0.20
        assert counters["risk_off_calls"] == 1
        assert counters["forced_cash_retry_calls"] == 1

    assert engine_module.generate_cn_attack_signal is original_signal
    assert engine_module._would_be_turnover is original_turnover


def test_corrected_halt_mask_uses_trade_status_not_carried_price() -> None:
    from trade.backtest.cn_attack_momentum_quality import engine as engine_module

    original = engine_module._real_bar_mask
    prices = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2025-01-02"),
                "ticker": "AAA",
                "adj_close": 10.0,
                "tradestatus": 1,
            },
            {
                "date": pd.Timestamp("2025-01-03"),
                "ticker": "AAA",
                "adj_close": 10.0,
                "tradestatus": 0,
            },
        ]
    )
    with RUNNER._trade_status_real_bar_mask():
        mask = engine_module._real_bar_mask(prices)
        assert bool(mask.loc[pd.Timestamp("2025-01-02"), "AAA"])
        assert not bool(mask.loc[pd.Timestamp("2025-01-03"), "AAA"])

    assert engine_module._real_bar_mask is original
