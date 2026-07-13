from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.test import ashare_low_max_first_look as sut
from scripts.test.ashare_multiscale_pv_trend_first_look import UniverseSchedule


def _write_size(path: Path, tickers: list[str]) -> None:
    pd.DataFrame(
        {
            "data_date": pd.Timestamp("2018-12-31"),
            "ticker": tickers,
            "market_cap": np.linspace(1e9, 2e9, len(tickers)),
        }
    ).to_csv(path, index=False)


def _schedule(tickers: list[str]) -> UniverseSchedule:
    return UniverseSchedule(
        dates=pd.DatetimeIndex(["2018-12-31"]),
        members=(frozenset(tickers),),
    )


def _price_frame(tickers: list[str]) -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-01", "2019-05-31")
    rng = np.random.default_rng(20260712)
    daily = rng.normal(0.0005, 0.01, size=(len(dates), len(tickers)))
    daily[30, :] = np.linspace(0.01, 0.08, len(tickers))
    close = 100.0 * np.cumprod(1.0 + daily, axis=0)
    return pd.DataFrame(close, index=dates, columns=tickers)


def _status_frame(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(1, index=close.index, columns=close.columns)


def test_lowmax_uses_maximum_of_exact_trailing_20_market_returns(tmp_path: Path) -> None:
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    close = _price_frame(tickers)
    size_path = tmp_path / "size.csv"
    _write_size(size_path, tickers)

    signals, diagnostics = sut.build_lowmax_signals(
        close, _status_frame(close), _schedule(tickers), size_path=size_path
    )

    first_date = pd.Timestamp(signals["signal_date"].min())
    position = int(close.index.get_indexer([first_date])[0])
    window = close.iloc[position - 20 : position + 1]
    expected = window[tickers[-1]].pct_change(fill_method=None).iloc[1:].max()
    row = signals.loc[
        signals["signal_date"].eq(first_date) & signals["ticker"].eq(tickers[-1])
    ].iloc[0]
    assert np.isclose(row["max20"], expected)
    assert np.isclose(row["raw_lowmax"], -expected)
    assert diagnostics["coverage"]["min"] == 1.0


def test_future_prices_do_not_change_old_lowmax_signal(tmp_path: Path) -> None:
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    close = _price_frame(tickers)
    size_path = tmp_path / "size.csv"
    _write_size(size_path, tickers)
    status = _status_frame(close)
    original, _ = sut.build_lowmax_signals(
        close, status, _schedule(tickers), size_path=size_path
    )
    changed = close.copy()
    changed.loc[changed.index > pd.Timestamp("2019-03-31")] *= 3.0
    rerun, _ = sut.build_lowmax_signals(
        changed, status, _schedule(tickers), size_path=size_path
    )

    columns = ["signal_date", "ticker", "max20", "raw_lowmax", "residual_lowmax"]
    left = original.loc[original["signal_date"].le("2019-03-31"), columns].reset_index(
        drop=True
    )
    right = rerun.loc[rerun["signal_date"].le("2019-03-31"), columns].reset_index(
        drop=True
    )
    pd.testing.assert_frame_equal(left, right)


def test_carried_suspension_price_is_zero_return_and_missing_close_fails_window(
    tmp_path: Path,
) -> None:
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    close = _price_frame(tickers)
    size_path = tmp_path / "size.csv"
    _write_size(size_path, tickers)
    status = _status_frame(close)
    feb_end = pd.Timestamp("2019-02-28")
    position = int(close.index.get_indexer([feb_end])[0])
    status.iloc[position - 5, 0] = 0
    close.iloc[position - 5, 0] *= 1.50
    close.iloc[position - 3, 1] = np.nan

    signals, diagnostics = sut.build_lowmax_signals(
        close, status, _schedule(tickers), size_path=size_path
    )

    first_month = signals[signals["signal_date"].eq(feb_end)]
    assert tickers[0] in set(first_month["ticker"])
    assert tickers[1] not in set(first_month["ticker"])
    row = first_month.loc[first_month["ticker"].eq(tickers[0])].iloc[0]
    window = close.iloc[position - 20 : position + 1, 0]
    expected_returns = window.pct_change(fill_method=None).iloc[1:]
    expected_returns = expected_returns.mask(
        status.loc[expected_returns.index, tickers[0]].eq(0), 0.0
    )
    assert np.isclose(row["max20"], expected_returns.max())
    assert np.isclose(row["past_return_20"], (1.0 + expected_returns).prod() - 1.0)
    february = next(
        row
        for row in diagnostics["coverage_by_month"]
        if row["signal_date"] == feb_end
    )
    assert february["signal_n"] == 119


def test_residual_signal_is_orthogonal_to_frozen_rank_controls(tmp_path: Path) -> None:
    tickers = [f"{number:06d}.SZ" for number in range(120)]
    close = _price_frame(tickers)
    size_path = tmp_path / "size.csv"
    _write_size(size_path, tickers)
    signals, diagnostics = sut.build_lowmax_signals(
        close,
        _status_frame(close),
        _schedule(tickers),
        size_path=size_path,
    )

    for _, cohort in signals.groupby("signal_date"):
        for control in ("rvol20_rank", "log_mcap_rank", "past_return_20_rank"):
            assert abs(cohort["residual_lowmax"].corr(cohort[control])) < 1e-10
    assert diagnostics["residual_max_abs_control_correlation"] < 1e-10


def test_pit_schedule_switches_only_after_new_snapshot_is_visible(tmp_path: Path) -> None:
    first = [f"{number:06d}.SZ" for number in range(120)]
    second = [f"{number:06d}.SZ" for number in range(120, 240)]
    all_tickers = first + second
    close = _price_frame(all_tickers)
    size_path = tmp_path / "size.csv"
    _write_size(size_path, all_tickers)
    schedule = UniverseSchedule(
        dates=pd.DatetimeIndex(["2018-12-31", "2019-03-31"]),
        members=(frozenset(first), frozenset(second)),
    )

    signals, _ = sut.build_lowmax_signals(
        close, _status_frame(close), schedule, size_path=size_path
    )
    by_month = signals.groupby("signal_date")["ticker"].agg(set)

    assert by_month.loc[pd.Timestamp("2019-03-29")] == set(first)
    assert by_month.loc[pd.Timestamp("2019-04-30")] == set(second)


def test_no_later_entry_is_retained_as_cash() -> None:
    signals = pd.DataFrame(
        {
            "signal_date": pd.Timestamp("2020-01-31"),
            "ticker": ["000001.SZ", "000002.SZ"],
            "raw_lowmax": [0.1, 0.2],
            "residual_lowmax": [0.1, 0.2],
            "past_return_20": [-0.1, -0.2],
            "pit_market_cap_signal": [1e9, 2e9],
        }
    )
    events = signals.iloc[[0]].copy()
    events["entry_date"] = pd.Timestamp("2020-02-03")
    events["limit_up"] = False

    combined = sut.retain_no_entry_as_cash(signals, events)
    cash = combined.loc[combined["ticker"].eq("000002.SZ")].iloc[0]

    assert cash["no_tradeable_entry"]
    assert cash["limit_up"]
    assert cash["ret_20"] == 0.0


def _analysis(*, long_excess: float = 0.005) -> dict:
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
                        "1": -0.01,
                        "2": -0.002,
                        "3": 0.003,
                        "4": 0.01,
                        "5": 0.02,
                    },
                    "q5_minus_q1": 0.03,
                    "q5_minus_all": long_excess,
                    "monotonic_rank_corr": 1.0,
                    "q5_excess_hac": {"mean": long_excess, "t": 2.5},
                    "q5_excess_bootstrap": {"ci_low": 0.001, "ci_high": 0.009},
                },
            }
        }
    }


def _diagnostics() -> dict:
    return {
        "universe_snapshots": 29,
        "noncurrent_members": 510,
        "signal_coverage": {"min": 0.99},
        "residual_design_full_rank_months": 64,
        "signal_months": 64,
        "residual_max_abs_control_correlation": 1e-15,
    }


def _exposure() -> dict:
    return {
        "mean_rvol_rank_gap": 0.05,
        "mean_log_mcap_rank_gap": -0.05,
    }


def test_raw_and_residual_signals_must_both_pass() -> None:
    passing = sut.evaluate_gates(_analysis(), _analysis(), _diagnostics(), _exposure())
    assert passing["signal_pass"] is True
    assert passing["verdict"] == "RESEARCH_GO_EXECUTION_DATA_REQUIRED"
    assert passing["cny_2_1m_portfolio_backtest_allowed"] is False

    residual_failed = _analysis(long_excess=0.001)
    failed = sut.evaluate_gates(
        _analysis(), residual_failed, _diagnostics(), _exposure()
    )
    assert failed["raw_signal_pass"] is True
    assert failed["residual_signal_pass"] is False
    assert failed["verdict"] == "SIGNAL_NO_GO"


def test_residual_top_group_exposure_gate_blocks_disguised_lowvol() -> None:
    exposure = deepcopy(_exposure())
    exposure["mean_rvol_rank_gap"] = -0.25
    result = sut.evaluate_gates(_analysis(), _analysis(), _diagnostics(), exposure)

    assert result["attribution_pass"] is False
    assert result["signal_pass"] is False
    assert result["verdict"] == "SIGNAL_NO_GO"
