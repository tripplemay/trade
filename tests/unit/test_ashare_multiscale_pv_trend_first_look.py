from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "test"
    / "ashare_multiscale_pv_trend_first_look.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "ashare_multiscale_pv_trend_first_look", _SCRIPT
)
assert _SPEC is not None and _SPEC.loader is not None
research = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = research
_SPEC.loader.exec_module(research)


def test_universe_schedule_uses_latest_visible_snapshot_not_union() -> None:
    schedule = research.UniverseSchedule(
        dates=pd.DatetimeIndex(["2020-03-31", "2020-06-30"]),
        members=(frozenset({"A", "B"}), frozenset({"B", "C"})),
    )

    assert schedule.members_on(pd.Timestamp("2020-03-01")) == frozenset()
    assert schedule.members_on(pd.Timestamp("2020-05-15")) == frozenset({"A", "B"})
    assert schedule.members_on(pd.Timestamp("2020-07-01")) == frozenset({"B", "C"})


def test_complete_month_ends_excludes_partial_terminal_month() -> None:
    dates = pd.DatetimeIndex(
        ["2020-01-30", "2020-01-31", "2020-02-27", "2020-02-28", "2020-03-10"]
    )

    result = research._complete_month_end_dates(dates)

    assert result.tolist() == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28")]


def test_raw_momentum_is_exact_month_end_12_1() -> None:
    dates = pd.date_range("2020-01-31", periods=15, freq="ME")
    close = pd.DataFrame({"A": np.arange(100.0, 115.0)}, index=dates)

    signal = research.raw_momentum_12_1(close)

    assert np.isnan(signal.loc[dates[12], "A"])
    assert signal.loc[dates[13], "A"] == close.loc[dates[12], "A"] / close.loc[dates[0], "A"] - 1


def test_feature_frames_match_ma_ratios_and_carry_suspended_volume() -> None:
    dates = pd.bdate_range("2020-01-20", periods=15)
    close = pd.DataFrame({"A": np.arange(10.0, 25.0)}, index=dates)
    volume = pd.DataFrame({"A": np.arange(100.0, 115.0)}, index=dates)
    status = pd.DataFrame({"A": np.ones(len(dates))}, index=dates)
    month_ends = pd.DatetimeIndex(
        [dates[dates.to_period("M") == pd.Period("2020-01")][-1], dates[-1]]
    )

    features, _ = research.build_feature_frames(
        close, volume, status, month_ends, volume_mode="share_volume", lags=(3,)
    )
    january = month_ends[0]
    expected_price = close.loc[:january, "A"].iloc[-3:].mean() / close.loc[january, "A"]
    expected_volume = volume.loc[:january, "A"].iloc[-3:].mean() / volume.loc[january, "A"]
    assert features["p003"].loc[january, "A"] == expected_price
    assert features["v003"].loc[january, "A"] == expected_volume

    suspended = status.copy()
    suspended.loc[suspended.index.to_period("M") == pd.Period("2020-02"), "A"] = 0
    carried, _ = research.build_feature_frames(
        close, volume, suspended, month_ends, volume_mode="share_volume", lags=(3,)
    )
    assert carried["v003"].loc[month_ends[1], "A"] == carried["v003"].loc[january, "A"]


def test_feature_at_month_end_does_not_depend_on_future_bars() -> None:
    dates = pd.bdate_range("2020-01-01", periods=50)
    close = pd.DataFrame({"A": np.linspace(10.0, 20.0, len(dates))}, index=dates)
    volume = pd.DataFrame({"A": np.linspace(100.0, 150.0, len(dates))}, index=dates)
    status = pd.DataFrame({"A": np.ones(len(dates))}, index=dates)
    signal_date = dates[25]

    original, _ = research.build_feature_frames(
        close, volume, status, pd.DatetimeIndex([signal_date]), lags=(5,)
    )
    changed_close = close.copy()
    changed_volume = volume.copy()
    changed_close.loc[dates[30]:, "A"] *= 10
    changed_volume.loc[dates[30]:, "A"] *= 10
    changed, _ = research.build_feature_frames(
        changed_close,
        changed_volume,
        status,
        pd.DatetimeIndex([signal_date]),
        lags=(5,),
    )

    assert original["p005"].equals(changed["p005"])
    assert original["v005"].equals(changed["v005"])


def _synthetic_online_inputs() -> tuple[
    dict[str, pd.DataFrame], pd.DataFrame, object, pd.DatetimeIndex
]:
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    tickers = [f"T{index:03d}" for index in range(30)]
    base = np.linspace(0.8, 1.2, len(tickers))
    price_feature = pd.DataFrame(
        [base + month * 0.001 for month in range(len(dates))],
        index=dates,
        columns=tickers,
    )
    volume_feature = pd.DataFrame(
        [base[::-1] + month * 0.002 for month in range(len(dates))],
        index=dates,
        columns=tickers,
    )
    monthly_returns = pd.DataFrame(
        [np.zeros(len(tickers))]
        + [0.03 - 0.02 * price_feature.iloc[month - 1].to_numpy() for month in range(1, 8)],
        index=dates,
        columns=tickers,
    )
    close = 100 * (1 + monthly_returns).cumprod()
    schedule = research.UniverseSchedule(
        dates=pd.DatetimeIndex([dates[0]]),
        members=(frozenset(tickers[:25]),),
    )
    return {"p003": price_feature, "v003": volume_feature}, close, schedule, dates


def test_online_estimator_is_pit_and_full_score_equals_components() -> None:
    features, close, schedule, _ = _synthetic_online_inputs()

    signals, diagnostics = research.estimate_online_trend(
        features, close, schedule, burn_in=2, min_cross_section=20
    )

    assert set(signals["ticker"]) == set(schedule.members[0])
    assert diagnostics["coefficient_months"] >= 2
    assert np.allclose(
        signals["trend_pv"],
        signals["trend_price_component"] + signals["trend_volume_component"],
    )


def test_online_estimator_old_signal_is_unchanged_by_future_return() -> None:
    features, close, schedule, dates = _synthetic_online_inputs()
    original, _ = research.estimate_online_trend(
        features, close, schedule, burn_in=2, min_cross_section=20
    )
    changed_close = close.copy()
    changed_close.loc[dates[-1]] *= np.linspace(0.5, 1.5, changed_close.shape[1])
    changed, _ = research.estimate_online_trend(
        features, changed_close, schedule, burn_in=2, min_cross_section=20
    )
    cutoff = dates[-2]
    columns = ["signal_date", "ticker", "trend_pv"]
    left = original.loc[original["signal_date"].le(cutoff), columns].reset_index(drop=True)
    right = changed.loc[changed["signal_date"].le(cutoff), columns].reset_index(drop=True)

    pd.testing.assert_frame_equal(left, right)


def test_forward_returns_wait_for_tradeable_open_and_exit(tmp_path: Path) -> None:
    dates = pd.bdate_range("2020-01-02", periods=80)
    signal_position = 20
    entry_position = signal_position + 3
    close = np.linspace(10.0, 18.0, len(dates))
    open_values = close.copy()
    open_values[entry_position] = 12.0
    close[entry_position] = 12.5
    status = np.ones(len(dates), dtype=int)
    status[signal_position + 1 : entry_position] = 0
    target = entry_position + 19
    status[target] = 0
    close[target + 1] = 15.0
    prices = pd.DataFrame(
        {
            "date": dates,
            "ticker": "000001.SZ",
            "open": open_values,
            "high": np.maximum(open_values, close),
            "low": np.minimum(open_values, close),
            "adj_close": close,
            "volume": 1_000_000.0,
            "tradestatus": status,
        }
    )
    signals = pd.DataFrame(
        {
            "signal_date": [dates[signal_position]],
            "ticker": ["000001.SZ"],
            "trend_pv": [1.0],
            "trend_price_component": [0.4],
            "trend_volume_component": [0.6],
            "raw_momentum_12_1": [0.2],
            "trend_pv_share_volume": [0.9],
        }
    )
    size_path = tmp_path / "size.csv"
    pd.DataFrame(
        {
            "data_date": [dates[signal_position - 1]],
            "ticker": ["000001.SZ"],
            "market_cap": [100.0],
        }
    ).to_csv(size_path, index=False)

    events = research.attach_forward_returns(signals, prices, size_path=size_path)

    assert events.loc[0, "entry_date"] == dates[entry_position]
    assert events.loc[0, "entry_delay_market_sessions"] == 2
    assert events.loc[0, "ret_1"] == close[entry_position + 1] / 12.0 - 1.0
    assert events.loc[0, "ret_20"] == close[target + 1] / 12.0 - 1.0
    assert events.loc[0, "exit_delay_20"] == 1
    assert events.loc[0, "pit_market_cap"] == 100.0


def test_limit_band_respects_chinext_reform_date() -> None:
    assert research._limit_band("300001.SZ", pd.Timestamp("2020-08-21")) == 0.10
    assert research._limit_band("300001.SZ", pd.Timestamp("2020-08-24")) == 0.20
    assert research._limit_band("688001.SH", pd.Timestamp("2019-07-22")) == 0.20


def test_block_bootstrap_is_deterministic() -> None:
    values = np.linspace(-0.1, 0.2, 60)

    assert research._block_bootstrap(values) == research._block_bootstrap(values)


def test_quintiles_freeze_rank_and_leave_limit_up_slot_in_cash() -> None:
    events = pd.DataFrame(
        {
            "signal_date": pd.Timestamp("2024-01-31"),
            "signal": np.arange(100.0),
            "ret_20": np.r_[np.full(99, 0.01), 1.0],
            "limit_up": np.r_[np.zeros(99, dtype=bool), True],
        }
    )

    result = research._quintiles(events, "signal", "ret_20")

    assert np.isclose(result["means"]["5"], 19 * 0.01 / 20)
    assert np.isclose(result["q5_minus_all"], 19 * 0.01 / 20 - 99 * 0.01 / 100)


def test_monthly_ic_skips_constant_signal_instead_of_counting_nan_month() -> None:
    events = pd.DataFrame(
        {
            "signal_date": pd.Timestamp("2024-01-31"),
            "signal": np.ones(100),
            "ret_20": np.arange(100.0),
        }
    )

    assert research._monthly_ic(events, "signal", "ret_20").empty


def test_jsonable_replaces_non_finite_values() -> None:
    result = research._jsonable({"nan": float("nan"), "inf": float("inf"), "x": 1.0})

    assert result == {"nan": None, "inf": None, "x": 1.0}


def test_exact_amount_data_gate_blocks_even_a_positive_proxy() -> None:
    positive_horizon = {
        "valid_months": 40,
        "hac": {"mean": 0.04, "t": 3.0},
        "block_bootstrap": {"ci_low": 0.01},
        "folds": [{"mean_ic": 0.04}, {"mean_ic": 0.03}, {"mean_ic": 0.02}],
        "quintiles": {
            "q5_minus_q1": 0.01,
            "monotonic_rank_corr": 0.9,
            "q5_excess_bootstrap": {"ci_low": 0.001},
        },
    }
    primary = {"horizons": {"N20": positive_horizon, "N60": positive_horizon}}
    comparison = {
        "hac": {"mean": 0.02},
        "block_bootstrap": {"ci_low": 0.005},
        "excluding_2024q4_mean": 0.01,
    }
    diagnostics = {
        "universe_snapshots": 29,
        "coefficient_months": 80,
        "pit_signal_coverage": {"p10": 0.99},
        "exact_rmb_traded_value_available": False,
    }

    gates = research.evaluate_gates(primary, comparison, primary, diagnostics)

    assert gates["signal_pass"]
    assert not gates["data_pass"]
    assert gates["verdict"] == "DATA_NO_GO"
    assert gates["proxy_signal_verdict"] == "PROXY_RESEARCH_GO"
    assert not gates["million_cny_portfolio_backtest_allowed"]
