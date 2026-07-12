from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/test/ashare_etf_trend_strict_followup.py"
SPEC = importlib.util.spec_from_file_location("ashare_etf_trend_strict_followup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
research = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = research
SPEC.loader.exec_module(research)


def _frame(
    code: str,
    dates: pd.DatetimeIndex,
    closes: list[float],
    *,
    opens: list[float] | None = None,
    nominal_scale: float = 1.0,
) -> pd.DataFrame:
    opens = opens or closes
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "close": closes,
            "high": [max(a, b) * 1.01 for a, b in zip(opens, closes, strict=True)],
            "low": [min(a, b) * 0.99 for a, b in zip(opens, closes, strict=True)],
            "volume_lots": 1_000_000.0,
            "turnover_pct": 1.0,
            "amount_cny": 1_000_000_000.0,
            "ticker": code,
            "raw_close": np.asarray(closes) * nominal_scale,
            "adjustment_scale": nominal_scale,
            "nominal_open": np.asarray(opens) * nominal_scale,
            "nominal_high": np.asarray(
                [max(a, b) * 1.01 for a, b in zip(opens, closes, strict=True)]
            )
            * nominal_scale,
            "nominal_low": np.asarray(
                [min(a, b) * 0.99 for a, b in zip(opens, closes, strict=True)]
            )
            * nominal_scale,
        }
    )


def _monthly_daily_dates(periods: int = 18) -> pd.DatetimeIndex:
    month_ends = pd.date_range("2020-01-31", periods=periods, freq="ME")
    entries = month_ends + pd.offsets.BDay(1)
    return pd.DatetimeIndex(sorted(set(month_ends) | set(entries)))


def test_schedule_executes_after_signal_close_and_drops_terminal_partial_month() -> None:
    dates = _monthly_daily_dates()
    closes = [100.0 + index for index in range(len(dates))]
    frame = _frame("A", dates, closes)
    momentum, entries = research.build_signal_schedule({"A": frame}, ["A"])
    assert len(entries) > 0
    assert (entries["entry_date"] > entries.index).all()
    assert (entries["exit_date"] > entries["entry_date"]).all()
    assert entries.index.max().to_period("M") < dates.max().to_period("M")
    assert momentum.index.equals(entries.index)


def test_adjusted_prices_remove_raw_split_from_momentum() -> None:
    dates = pd.date_range("2020-01-31", periods=14, freq="ME")
    qfq = pd.DataFrame({"date": dates, "ticker": "A", "open": 1.0, "close": 1.0,
                        "high": 1.0, "low": 1.0, "volume_lots": 1.0,
                        "turnover_pct": 1.0, "amount_cny": 1_000_000.0})
    raw = pd.DataFrame({"date": dates, "ticker": "A", "close": [4.0] * 7 + [1.0] * 7})
    merged = research.attach_nominal_prices(qfq, raw)
    assert (merged["close"].pct_change().fillna(0.0) == 0.0).all()
    assert merged["raw_close"].pct_change().min() == -0.75
    assert merged["nominal_open"].iloc[0] == 4.0
    assert merged["nominal_open"].iloc[-1] == 1.0


def test_tencent_row_retains_exact_amount_field() -> None:
    rows = [["2026-07-10", "4.918", "4.829", "4.949", "4.827", "8242800", {},
             "4.80", "403950.72", ""]]
    frame = research._normalise_tx_rows(rows, "510300")
    assert np.isclose(frame.iloc[0]["amount_cny"], 4_039_507_200.0)
    assert frame.iloc[0]["volume_lots"] == 8_242_800.0


def test_cost_includes_minimum_commission_and_slippage() -> None:
    assert research._trade_cost(1_000.0) == 5.5
    assert research._trade_cost(1_000_000.0) == 750.0
    assert research._trade_cost(1_000_000.0, 2.0) == 1_500.0
    assert research._trade_cost(0.0) == 0.0


def test_target_notionals_round_to_100_share_lots_and_keep_cash_nonnegative() -> None:
    targets, cost, trades = research._target_notionals(
        2_100_000.0,
        {"A": 0.5, "B": 0.5},
        {},
        {"A": 4.83, "B": 8.70},
        1.0,
    )
    lots_a = targets["A"] / (4.83 * 100)
    lots_b = targets["B"] / (8.70 * 100)
    assert np.isclose(lots_a, round(lots_a))
    assert np.isclose(lots_b, round(lots_b))
    assert sum(targets.values()) + cost <= 2_100_000.0
    assert trades == targets


def test_locked_limit_up_is_detected_directionally() -> None:
    bar = pd.Series({"open": 11.0, "high": 11.0, "low": 11.0})
    assert research._locked_direction(bar, 10.0) == "up"
    down = pd.Series({"open": 9.0, "high": 9.0, "low": 9.0})
    assert research._locked_direction(down, 10.0) == "down"
    normal = pd.Series({"open": 11.0, "high": 11.1, "low": 10.9})
    assert research._locked_direction(normal, 10.0) is None


def test_block_bootstrap_is_deterministic() -> None:
    series = pd.Series([0.01, -0.02, 0.03, 0.00, 0.04, -0.01])
    first = research.block_bootstrap_mean_ci(series, draws=100, block=2, seed=7)
    second = research.block_bootstrap_mean_ci(series, draws=100, block=2, seed=7)
    assert first == second


def test_newey_west_mean_is_finite_for_varying_series() -> None:
    result = research.newey_west_mean(pd.Series([0.01, -0.01, 0.02, 0.00, 0.03]), lags=2)
    assert result["n"] == 5
    assert np.isfinite(result["mean"])
    assert np.isfinite(result["t"])


def test_gate_requires_every_preregistered_condition() -> None:
    trend = {"cagr": 0.12, "sharpe": 0.8, "max_drawdown": -0.20}
    hold = {"cagr": 0.09, "sharpe": 0.6, "max_drawdown": -0.25}
    comparison = {
        "hac": {"t": 2.0},
        "block_bootstrap_95": {"lower": 0.001},
    }
    folds = [{"cagr_delta": 0.01}] * 3 + [{"cagr_delta": -0.01}]
    whipsaw = {"a": {"delta": -0.02}, "b": {"delta": 0.01}}
    execution = {"participation_pass_rate": 1.0, "max_participation": 0.005}
    passed = research.evaluate_gates(
        trend, hold, comparison, folds, whipsaw, execution, True
    )
    assert passed["all_pass"] is True
    failed = research.evaluate_gates(
        {**trend, "cagr": 0.10}, hold, comparison, folds, whipsaw, execution, True
    )
    assert failed["all_pass"] is False
    assert failed["gates"]["net_cagr_delta_at_least_2pp"] is False


def test_validate_qfq_rejects_unadjusted_like_extreme_move() -> None:
    dates = pd.date_range("2020-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [1.0, 1.0, 4.0],
            "close": [1.0, 1.0, 4.0],
            "high": [1.0, 1.0, 4.0],
            "low": [1.0, 1.0, 4.0],
            "volume_lots": 1.0,
            "turnover_pct": 1.0,
            "amount_cny": 1_000_000.0,
            "ticker": "A",
        }
    )
    result = research.validate_qfq_frame(frame)
    assert result["adjusted_daily_moves_over_80pct"] == 1
    assert result["pass"] is False


def test_period_comparison_is_paired_by_signal_date() -> None:
    dates = pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"])
    trend = pd.DataFrame({"signal_date": dates, "return": [0.02, 0.01, -0.01]})
    hold = pd.DataFrame({"signal_date": dates[::-1], "return": [-0.02, 0.00, 0.01]})
    result = research.compare_periods(trend, hold)
    assert result["paired_months"] == 3
    assert result["hac"]["mean"] == np.mean([0.01, 0.01, 0.01])


def test_daily_nav_controls_max_drawdown_instead_of_monthly_endpoints() -> None:
    periods = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2024-01-31", "2024-02-29"]),
            "return": [0.0, 0.0],
            "turnover": [0.0, 0.0],
            "cost": [0.0, 0.0],
            "n_selected": [1, 1],
            "cash_weight": [0.0, 0.0],
        }
    )
    daily = pd.DataFrame(
        {"date": pd.date_range("2024-02-01", periods=3), "nav": [2_100_000, 1_050_000, 2_100_000]}
    )
    result = research.performance_metrics(periods, daily)
    assert result["max_drawdown"] == -0.5
    assert result["max_drawdown_frequency"] == "daily"


def test_calendar_windows_are_attributed_by_entry_month_not_signal_month() -> None:
    periods = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2023-12-29", "2024-01-31"]),
            "entry_date": pd.to_datetime(["2024-01-02", "2024-02-01"]),
            "return": [0.10, -0.20],
        }
    )
    january = research._cumulative_window_return(periods, "2024-01-01", "2024-01-31")
    assert np.isclose(january, 0.10)
