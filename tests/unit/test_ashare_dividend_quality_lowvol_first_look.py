from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/test/ashare_dividend_quality_lowvol_first_look.py"
SPEC = importlib.util.spec_from_file_location(
    "ashare_dividend_quality_lowvol_first_look", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
research = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = research
SPEC.loader.exec_module(research)


def test_parse_index_records_validates_code_and_keeps_last_duplicate() -> None:
    records = [
        {"tradeDate": "20200102", "indexCode": "H1", "close": 100.0},
        {"tradeDate": "20200103", "indexCode": "H1", "close": 101.0},
        {"tradeDate": "20200103", "indexCode": "H1", "close": 102.0},
    ]
    series = research.parse_index_records(records, "H1")
    assert list(series) == [100.0, 102.0]
    assert series.index.is_monotonic_increasing

    bad = [{"tradeDate": "20200102", "indexCode": "OTHER", "close": 100.0}]
    with pytest.raises(ValueError, match="unexpected CSI codes"):
        research.parse_index_records(bad, "H1")


def test_performance_metrics_use_daily_drawdown_and_target_capital() -> None:
    index = pd.to_datetime(["2020-01-02", "2020-06-30", "2020-09-30", "2021-01-04"])
    values = pd.Series([100.0, 120.0, 90.0, 110.0], index=index)
    metrics = research.performance_metrics(values)
    assert metrics["total_return"] == pytest.approx(0.10)
    assert metrics["max_drawdown"] == pytest.approx(-0.25)
    assert metrics["ending_value_cny_at_2_1m"] == pytest.approx(2_310_000.0)


def test_pair_window_reports_candidate_minus_baseline_deltas() -> None:
    index = pd.date_range("2020-01-02", periods=6, freq="90D")
    frame = pd.DataFrame(
        {
            "baseline": np.linspace(100.0, 110.0, len(index)),
            "candidate": np.linspace(100.0, 120.0, len(index)),
        },
        index=index,
    )
    result = research.pair_window(frame, index[0], index[-1])
    assert result["delta"]["cagr"] > 0
    assert result["delta"]["ending_value_cny_at_2_1m"] == pytest.approx(210_000.0)


def test_newey_west_and_block_bootstrap_are_deterministic() -> None:
    excess = pd.Series([0.01, -0.02, 0.03, 0.00, 0.04, -0.01, 0.02, 0.01])
    hac = research.newey_west_mean(excess, lags=2)
    assert hac["n"] == 8
    assert np.isfinite(hac["t"])
    first = research.block_bootstrap_mean_ci(excess, draws=200, block=3, seed=9)
    second = research.block_bootstrap_mean_ci(excess, draws=200, block=3, seed=9)
    assert first == second


def test_chronological_folds_do_not_interleave_months() -> None:
    index = pd.date_range("2020-01-31", periods=12, freq="ME")
    monthly = pd.DataFrame(
        {
            "baseline": [0.01] * 12,
            "candidate": [0.02] * 12,
            "excess": [0.01] * 12,
        },
        index=index,
    )
    folds = research.chronological_folds(monthly, 4)
    assert len(folds) == 4
    assert [fold["months"] for fold in folds] == [3, 3, 3, 3]
    assert folds[0]["end"] < folds[1]["start"]
    assert all(fold["cagr_delta"] > 0 for fold in folds)


def _passing_gate_inputs() -> tuple[
    dict[str, object], dict[str, object], list[dict[str, float]], dict[str, dict[str, object]]
]:
    post = {
        "baseline": {"months": 72},
        "delta": {
            "cagr": 0.03,
            "sharpe_rf0": 0.20,
            "max_drawdown_improvement": 0.01,
        },
    }
    inference = {
        "newey_west_hac": {"t": 2.0},
        "block_bootstrap_95": {"annualized_lower": 0.01},
    }
    folds = [{"cagr_delta": 0.01}] * 3 + [{"cagr_delta": -0.01}]
    windows: dict[str, dict[str, object]] = {
        "stress": {
            "available": True,
            "delta": {"max_drawdown_improvement": -0.01},
        }
    }
    return post, inference, folds, windows


def test_index_gate_requires_return_priority_and_investability() -> None:
    post, inference, folds, windows = _passing_gate_inputs()
    passed = research.evaluate_index_gates(
        post, inference, folds, windows, has_tracking_product=True
    )
    assert passed["all_pass"] is True

    failed_post = {
        **post,
        "delta": {**post["delta"], "cagr": 0.019},
    }
    failed = research.evaluate_index_gates(
        failed_post, inference, folds, windows, has_tracking_product=False
    )
    assert failed["all_pass"] is False
    assert failed["gates"]["cagr_delta_at_least_2pp"] is False
    assert failed["gates"]["official_tracking_product_exists"] is False
    assert research.derive_overall_verdict(failed) == failed["verdict"] == "NO_GO"
    with pytest.raises(ValueError, match="unexpected index gate verdict"):
        research.derive_overall_verdict({"verdict": "DATA_NO_GO"})


def test_component_coverage_is_visibility_aware() -> None:
    universe = pd.DataFrame(
        {
            "as_of_date": ["2020-03-31", "2020-03-31", "2020-06-30", "2020-06-30"],
            "ticker": ["A", "B", "A", "B"],
        }
    )
    fundamentals = pd.DataFrame(
        {
            "report_date": ["2020-01-01", "2020-05-01"],
            "ticker": ["A", "B"],
        }
    )
    result = research.summarize_component_coverage(universe, fundamentals)
    assert result["union_ticker_coverage"] == 1.0
    assert result["per_date"][0]["coverage"] == 0.5
    assert result["per_date"][1]["coverage"] == 1.0


def test_parse_tracking_flag_requires_exact_official_yes_no() -> None:
    frame = pd.DataFrame(
        {
            "指数代码": [931130],
            "指数简称": ["红利成长低波"],
            "指数全称": ["中证红利成长低波动指数"],
            "跟踪产品": ["否"],
            "发布时间": ["2018-12-04"],
        }
    )
    result = research.parse_tracking_flag(frame, "931130")
    assert result["has_tracking_product"] is False
    frame.loc[0, "跟踪产品"] = "未知"
    with pytest.raises(ValueError, match="unexpected tracking-product flag"):
        research.parse_tracking_flag(frame, "931130")


def test_tier_weights_pin_legacy_b082_boundaries() -> None:
    spreads = pd.Series([1.49, 1.50, 2.49, 2.50])
    assert list(research.tier_weights(spreads)) == [0.25, 0.50, 0.50, 1.00]
