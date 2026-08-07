"""B113 F002 — partial_rebalance A/B runner/报告的单测（含 H7 机器判据）。"""

from __future__ import annotations

import json

import pytest

from scripts.research.b113_partial_rebalance_ab import _comparison
from scripts.research.b113_partial_rebalance_report import render

_FORBIDDEN = (
    "GO",
    "NO-GO",
    "NOGO",
    "INCONCLUSIVE",
    "值得投入",
    "有 edge",
    "有edge",
    "建议投入",
    "应当继续",
    "结论是",
)


def _cell(cagr_full: float, cagr_oos: float, mdd_oos: float, annual_turnover: float) -> dict:
    return {
        "annual_turnover": annual_turnover,
        "segments": {
            "full": {
                "annualized_return": cagr_full,
                "max_drawdown": -0.50,
                "sharpe_ratio": 0.50,
            },
            "oos": {
                "annualized_return": cagr_oos,
                "max_drawdown": mdd_oos,
                "sharpe_ratio": 0.60,
            },
        },
        "per_year_returns": {"2025": 0.01},
    }


def test_comparison_has_oos_deltas_and_turnover_ratio() -> None:
    v0 = _cell(0.10, 0.12, -0.30, 1.5)
    v1 = _cell(0.13, 0.165, -0.32, 3.6)
    comp = _comparison(v0, v1)
    oos = comp["deltas"]["oos"]
    assert oos["delta_cagr_pp"] == pytest.approx(4.5)
    assert oos["delta_max_drawdown_pp"] == pytest.approx(-2.0)
    assert comp["annual_turnover_ratio"] == pytest.approx(2.4)


def _sample_payload() -> dict:
    v0 = {
        **_cell(0.10, 0.12, -0.30, 1.5),
        "total_turnover": 10.0,
        "total_cost": 4000.0,
        "rebalance_count": 60,
    }
    v1 = {
        **_cell(0.13, 0.165, -0.32, 3.6),
        "total_turnover": 24.0,
        "total_cost": 9600.0,
        "rebalance_count": 142,
    }
    comp = {"v0": v0, "v1": v1, **_comparison(v0, v1)}
    return {
        "honesty_statement": "只算不裁",
        "frozen_window": {"start": "2019-04-01", "end": "2026-07-31", "is_oos": "70/30"},
        "ab_caliber": "V0 全 band vs V1 partial",
        "criterion_thresholds": {
            "main_oos_delta_cagr_min_pp": 1.0,
            "secondary_oos_delta_maxdd_min_pp": -2.0,
            "secondary_annual_turnover_ratio_max": 3.0,
            "note": "阈值为陈述值，独立于观测；施加与裁定归 F003（H7）。",
        },
        "input_coverage": "复用 B112",
        "comparisons": {"pure_momentum__100000": comp},
        "generator_boundary": "判据的施加与裁定归 F003 的 Codex（铁律 #4）。",
    }


def test_render_has_no_verdict_language() -> None:
    md = render(_sample_payload())
    for word in _FORBIDDEN:
        assert word not in md, f"报告中出现结论性措辞: {word}"


def test_render_contains_criterion_table() -> None:
    md = render(_sample_payload())
    assert "OOS ΔCAGR" in md
    assert "年化换手倍率" in md
    assert "+4.50pp" in md  # 0.165−0.12
    assert "×2.40" in md


def test_payload_has_no_verdict_language() -> None:
    payload = json.dumps(_sample_payload(), ensure_ascii=False, default=str)
    for word in _FORBIDDEN:
        assert word not in payload, f"产物中出现结论性措辞: {word}"
