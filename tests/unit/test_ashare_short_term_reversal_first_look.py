from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd

from scripts.test import ashare_short_term_reversal_first_look as sut
from scripts.test.ashare_multiscale_pv_trend_first_look import UniverseSchedule


def _schedule(tickers: list[str]) -> UniverseSchedule:
    return UniverseSchedule(
        dates=pd.DatetimeIndex(["2018-12-31"]),
        members=(frozenset(tickers),),
    )


def test_reversal_signal_uses_exactly_20_prior_market_sessions() -> None:
    dates = pd.bdate_range("2019-01-01", "2019-03-29")
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    base = np.arange(1, len(dates) + 1, dtype=float)
    close = pd.DataFrame(
        {ticker: base * (1.0 + number / 1_000.0) for number, ticker in enumerate(tickers)},
        index=dates,
    )

    signals, diagnostics = sut.build_reversal_signals(close, _schedule(tickers))

    first_date = pd.Timestamp(signals["signal_date"].min())
    position = int(close.index.get_indexer([first_date])[0])
    row = signals.loc[
        signals["signal_date"].eq(first_date) & signals["ticker"].eq(tickers[0])
    ].iloc[0]
    expected = close.loc[first_date, tickers[0]] / close.iloc[position - 20][tickers[0]] - 1.0
    assert row["past_return_20"] == expected
    assert row["reversal_20"] == -expected
    assert diagnostics["coverage"]["min"] == 1.0


def test_old_reversal_signal_does_not_change_when_future_prices_change() -> None:
    dates = pd.bdate_range("2019-01-01", "2019-04-30")
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    close = pd.DataFrame(
        np.arange(len(dates), dtype=float)[:, None] + np.arange(120)[None, :] + 100.0,
        index=dates,
        columns=tickers,
    )
    original, _ = sut.build_reversal_signals(close, _schedule(tickers))
    changed = close.copy()
    changed.loc[changed.index > pd.Timestamp("2019-02-28")] *= 10.0
    rerun, _ = sut.build_reversal_signals(changed, _schedule(tickers))

    left = original.loc[original["signal_date"].le("2019-02-28")].reset_index(drop=True)
    right = rerun.loc[rerun["signal_date"].le("2019-02-28")].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_reversal_signal_uses_latest_visible_pit_members() -> None:
    dates = pd.bdate_range("2019-01-01", "2019-05-31")
    first = [f"{number:06d}.SZ" for number in range(120)]
    second = [f"{number:06d}.SZ" for number in range(120, 240)]
    all_tickers = first + second
    close = pd.DataFrame(100.0, index=dates, columns=all_tickers)
    schedule = UniverseSchedule(
        dates=pd.DatetimeIndex(["2018-12-31", "2019-03-31"]),
        members=(frozenset(first), frozenset(second)),
    )

    signals, _ = sut.build_reversal_signals(close, schedule)
    by_month = signals.groupby("signal_date")["ticker"].agg(set)

    assert by_month.loc[pd.Timestamp("2019-02-28")] == set(first)
    assert by_month.loc[pd.Timestamp("2019-03-29")] == set(first)
    assert by_month.loc[pd.Timestamp("2019-04-30")] == set(second)


def test_four_folds_are_contiguous_and_exhaustive() -> None:
    records = [
        {"month": month, "ic": float(index)}
        for index, month in enumerate(pd.date_range("2019-01-31", periods=10, freq="ME"))
    ]
    folds = sut._four_folds(records)

    assert [fold["months"] for fold in folds] == [3, 3, 2, 2]
    assert sum(fold["months"] for fold in folds) == 10
    assert folds[0]["end"] < folds[1]["start"] < folds[2]["start"] < folds[3]["start"]


def _primary(*, q5: float = 0.02, q1: float = -0.01, long_excess: float = 0.005) -> dict:
    monthly = [
        {"month": month, "ic": 0.04, "n": 800}
        for month in pd.date_range("2019-01-31", periods=64, freq="ME")
    ]
    return {
        "horizons": {
            "N20": {
                "valid_months": 64,
                "monthly": monthly,
                "hac": {"mean": 0.04, "t": 2.5},
                "block_bootstrap": {"ci_low": 0.01, "ci_high": 0.07},
                "quintiles": {
                    "means": {
                        "1": q1,
                        "2": -0.002,
                        "3": 0.003,
                        "4": 0.01,
                        "5": q5,
                    },
                    "q5_minus_q1": q5 - q1,
                    "q5_minus_all": long_excess,
                    "monotonic_rank_corr": 1.0,
                    "q5_excess_bootstrap": {"ci_low": 0.001, "ci_high": 0.009},
                },
            }
        }
    }


def _diagnostics() -> dict:
    return {
        "universe_snapshots": 29,
        "signal_coverage": {"min": 0.99},
        "noncurrent_members": 536,
    }


def test_long_only_attribution_separates_unbuyable_winner_short_leg() -> None:
    attribution = sut.long_only_attribution(_primary(q5=0.01, q1=-0.03, long_excess=0.001))

    assert np.isclose(attribution["investable_universe_mean"], 0.009)
    assert np.isclose(attribution["winner_short_leg_contribution"], 0.039)
    assert np.isclose(attribution["long_short_spread"], 0.04)
    assert np.isclose(attribution["winner_short_share_of_spread"], 0.975)


def test_gates_require_independently_profitable_long_leg() -> None:
    passing = sut.evaluate_gates(_primary(), _diagnostics())
    assert passing["signal_data_pass"] is True
    assert passing["signal_pass"] is True
    assert passing["verdict"] == "RESEARCH_GO_EXECUTION_DATA_REQUIRED"
    assert passing["cny_2_1m_portfolio_backtest_allowed"] is False

    short_driven = deepcopy(_primary(q5=-0.001, q1=-0.04, long_excess=0.001))
    short_driven["horizons"]["N20"]["quintiles"]["q5_excess_bootstrap"]["ci_low"] = -0.001
    failed = sut.evaluate_gates(short_driven, _diagnostics())
    assert failed["signal"]["past_loser_q5_absolute_return_positive"] is False
    assert failed["signal"]["long_only_q5_excess_ge_20bp_per_month"] is False
    assert failed["signal"]["long_only_q5_excess_bootstrap_ci_above_zero"] is False
    assert failed["signal_pass"] is False
    assert failed["verdict"] == "SIGNAL_NO_GO"


def test_data_gate_blocks_incomplete_pit_coverage() -> None:
    diagnostics = _diagnostics()
    diagnostics["signal_coverage"] = {"min": 0.94}
    result = sut.evaluate_gates(_primary(), diagnostics)

    assert result["signal_data_pass"] is False
    assert result["verdict"] == "DATA_NO_GO"


def test_exit_stress_forces_path_ended_and_long_delay_but_not_right_censor() -> None:
    market_dates = pd.bdate_range("2020-01-01", periods=100)
    events = pd.DataFrame(
        {
            "signal_date": pd.Timestamp("2020-03-31"),
            "reversal_20": np.arange(100, dtype=float),
            "ret_20": np.linspace(-0.05, 0.05, 100),
            "limit_up": False,
            "entry_date": pd.Timestamp("2020-04-01"),
            "exit_delay_20": 0.0,
        }
    )
    events.loc[0, ["ret_20", "exit_delay_20"]] = np.nan
    events.loc[1, ["ret_20", "exit_delay_20"]] = np.nan
    events.loc[1, "entry_date"] = market_dates[-1]
    events.loc[2, "exit_delay_20"] = 21.0

    result = sut.n20_exit_stress(events, market_dates)

    assert result["path_ended_forced_loss"] == 1
    assert result["long_delay_forced_loss"] == 1
    assert result["forced_loss_events"] == 2
