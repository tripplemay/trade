"""B076 F001 — unit tests for the size-tilt sweep's deterministic logic.

The sweep's NUMBERS come from the real backtest (run on the research roots); this locks
the parts that must be stable regardless of data: the GO/NO-GO verdict mapping (spec §0,
verdict-gated), the breadth metrics, and the market-cap loader's schema/downsample rules.
No network / no backtest here.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.research.b076_size_tilt_comparison import (
    breadth_metrics,
    judge_size_tilt,
    latest_caps,
    load_marketcap,
)


def _row(level: str, tilt: float, *, oos_sharpe: float, small: float, pctile: float) -> dict:
    return {
        "level": level,
        "size_tilt_weight": tilt,
        "oos_sharpe": oos_sharpe,
        "small_cap_frac": small,
        "median_cap_pctile": pctile,
    }


def test_go_when_a_tilt_holds_sharpe_and_adds_breadth() -> None:
    rows = [
        _row("current", 0.0, oos_sharpe=0.90, small=0.10, pctile=0.80),
        _row("light", 0.15, oos_sharpe=0.88, small=0.20, pctile=0.74),
        _row("strong", 0.50, oos_sharpe=0.92, small=0.50, pctile=0.40),
    ]
    verdict = judge_size_tilt(rows)
    assert verdict["verdict"] == "GO"
    assert verdict["winning_level"] == "strong"
    assert verdict["winning_size_tilt_weight"] == 0.50


def test_no_go_when_no_tilt_adds_real_breadth() -> None:
    # Selection barely moves (small names still rank too low) → size factor is inert.
    rows = [
        _row("current", 0.0, oos_sharpe=0.90, small=0.10, pctile=0.80),
        _row("light", 0.15, oos_sharpe=0.95, small=0.11, pctile=0.79),
        _row("strong", 0.50, oos_sharpe=0.93, small=0.12, pctile=0.78),
    ]
    verdict = judge_size_tilt(rows)
    assert verdict["verdict"] == "NO-GO"
    assert "does not meaningfully change selection" in verdict["reason"]


def test_no_go_when_breadth_only_comes_with_worse_sharpe() -> None:
    # Every tilt that adds breadth degrades OOS Sharpe (small-caps blow up).
    rows = [
        _row("current", 0.0, oos_sharpe=0.90, small=0.10, pctile=0.80),
        _row("light", 0.15, oos_sharpe=0.55, small=0.30, pctile=0.60),
        _row("strong", 0.50, oos_sharpe=0.40, small=0.50, pctile=0.40),
    ]
    verdict = judge_size_tilt(rows)
    assert verdict["verdict"] == "NO-GO"
    assert "WORSE" in verdict["reason"]


def test_no_go_when_breadth_and_risk_never_coincide() -> None:
    # One tilt holds Sharpe but no breadth; another adds breadth but worse Sharpe.
    rows = [
        _row("current", 0.0, oos_sharpe=0.90, small=0.10, pctile=0.80),
        _row("light", 0.15, oos_sharpe=0.92, small=0.11, pctile=0.79),  # risk ok, no breadth
        _row("strong", 0.50, oos_sharpe=0.50, small=0.50, pctile=0.40),  # breadth, risk worse
    ]
    verdict = judge_size_tilt(rows)
    assert verdict["verdict"] == "NO-GO"
    assert "never coincided" in verdict["reason"]


def test_breadth_metrics_flags_small_cap_basket() -> None:
    universe_caps = pd.Series(
        {"A": 2.0e12, "B": 1.0e12, "C": 8.0e11, "D": 5.0e9, "E": 2.0e9, "F": 1.0e9}
    )
    # Picked the two smallest (E, F) → low cap-percentile, all below universe median.
    metrics = breadth_metrics(("E", "F"), universe_caps, frozenset({"A", "B"}))
    assert metrics["selected_count"] == 2
    assert metrics["small_cap_frac"] == 1.0
    assert metrics["median_cap_pctile"] < 0.4  # smaller-cap basket
    assert metrics["seed43_overlap_frac"] == 0.0  # neither E nor F is a "seed"


def test_breadth_metrics_flags_blue_chip_basket() -> None:
    universe_caps = pd.Series(
        {"A": 2.0e12, "B": 1.0e12, "C": 8.0e11, "D": 5.0e9, "E": 2.0e9, "F": 1.0e9}
    )
    # Picked the two biggest (A, B), both "seeds" → high percentile, zero small-cap frac.
    metrics = breadth_metrics(("A", "B"), universe_caps, frozenset({"A", "B"}))
    assert metrics["small_cap_frac"] == 0.0
    assert metrics["median_cap_pctile"] > 0.7
    assert metrics["seed43_overlap_frac"] == 1.0


def test_load_marketcap_maps_circ_mv_and_downsamples_to_month_end(tmp_path) -> None:
    path = tmp_path / "cn_marketcap.csv"
    # B068 schema (circ_mv, daily) — must rename + keep last per month.
    rows = [
        "data_date,ticker,total_mv,circ_mv,total_shares,close",
        "2025-01-10,T1,3e10,2.0e10,1,10",
        "2025-01-31,T1,3e10,2.1e10,1,10",  # last of Jan → kept
        "2025-02-27,T1,3e10,2.2e10,1,10",  # last of Feb → kept
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    frame = load_marketcap(path)
    assert list(frame.columns) == ["data_date", "ticker", "market_cap"]
    assert len(frame) == 2  # two month-ends
    feb = frame[frame["data_date"] == pd.Timestamp("2025-02-27")]
    assert float(feb["market_cap"].iloc[0]) == pytest.approx(2.2e10)


def test_latest_caps_is_point_in_time(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "data_date": pd.to_datetime(["2025-01-31", "2025-05-31", "2025-08-31"]),
            "ticker": ["T1", "T1", "T1"],
            "market_cap": [2.0e10, 1.0e10, 5.0e9],
        }
    )
    caps = latest_caps(frame, __import__("datetime").date(2025, 6, 1))
    assert caps["T1"] == pytest.approx(1.0e10)  # latest <= as_of, not the Aug row
