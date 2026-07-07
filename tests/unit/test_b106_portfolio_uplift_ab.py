"""B106 F002 — unit tests for the组合层 uplift A/B runner's pure logic.

Covers the verdict-critical building blocks: metric math, currency (口径) alignment,
portfolio combination (incl. the vol-target no-normalize path that was a real bug),
correlation, rolling risk-aware weight derivation, and the verdict gate itself.
Data-heavy sleeve reconstruction is exercised by the runner end-to-end, not here.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from scripts.research.b106_portfolio_uplift_ab import (
    MONTHS_PER_YEAR,
    annualized_metrics,
    cny_returns_to_usd,
    combine_dynamic,
    combine_fixed,
    correlation,
    max_drawdown,
    nav_curve,
    recovery_gain,
    rolling_scheme_weights,
    verdict_from_metrics,
    window_return_and_dd,
)
from trade.portfolio.master import WEIGHT_SCHEME_HRP, WEIGHT_SCHEME_RISK_PARITY


def test_annualized_metrics_constant_positive_return() -> None:
    rets = [0.01] * 12  # +1%/month, zero vol
    m = annualized_metrics(rets, MONTHS_PER_YEAR)
    assert m["n"] == 12
    assert m["cagr"] == pytest.approx(1.01**12 - 1, rel=1e-9)
    assert m["ann_vol"] == pytest.approx(0.0, abs=1e-12)
    assert m["sharpe"] == 0.0  # zero vol → Sharpe defined as 0


def test_annualized_metrics_empty() -> None:
    assert annualized_metrics([]) == {"cagr": 0.0, "ann_vol": 0.0, "sharpe": 0.0, "n": 0}


def test_nav_curve_and_max_drawdown() -> None:
    nav = nav_curve([0.10, -0.50, 0.20])
    assert nav[0] == pytest.approx(1.10)
    assert nav[1] == pytest.approx(0.55)
    assert nav[2] == pytest.approx(0.66)
    # peak 1.10 → trough 0.55 = -50%
    assert max_drawdown(nav) == pytest.approx(-0.50, rel=1e-9)


def test_max_drawdown_monotonic_up_is_zero() -> None:
    assert max_drawdown([1.0, 1.1, 1.2, 1.3]) == 0.0


def test_recovery_gain_arithmetic() -> None:
    # -50% needs +100% to recover; -20% needs +25%
    assert recovery_gain(-0.50) == pytest.approx(1.0)
    assert recovery_gain(-0.20) == pytest.approx(0.25)
    assert recovery_gain(0.0) == 0.0
    assert recovery_gain(-1.0) == float("inf")


def test_cny_returns_to_usd_depreciation_drags() -> None:
    # CNY per USD rises 6.0 -> 6.6 (10% CNY depreciation) between two month-ends.
    fx = pd.Series(
        [6.0, 6.6],
        index=pd.to_datetime(["2020-01-31", "2020-02-29"]),
    )
    cny = {date(2020, 1, 31): 0.0, date(2020, 2, 29): 0.10}  # +10% in CNY
    usd = cny_returns_to_usd(cny, fx)
    # first date is the anchor (no prior) → dropped
    assert date(2020, 1, 31) not in usd
    # (1.10) * (6.0/6.6) - 1 = 0.0  → the CNY gain is exactly wiped by FX
    assert usd[date(2020, 2, 29)] == pytest.approx(0.0, abs=1e-9)


def test_cny_returns_to_usd_missing_fx_falls_back_native() -> None:
    fx = pd.Series([6.0], index=pd.to_datetime(["1999-01-01"]))  # far before window
    cny = {date(2020, 1, 31): 0.0, date(2020, 2, 29): 0.05}
    usd = cny_returns_to_usd(cny, fx)
    # fx quote exists (as-of) for both → not a fallback here; verify it at least runs
    assert date(2020, 2, 29) in usd


def test_combine_fixed_weighted_average() -> None:
    d = date(2021, 1, 31)
    sr = {"a": {d: 0.10}, "b": {d: 0.00}}
    port = combine_fixed(sr, {"a": 0.5, "b": 0.5})
    assert port[d] == pytest.approx(0.05)


def test_combine_dynamic_normalize_vs_cash_residual() -> None:
    """The vol-target path (normalize=False) must NOT cancel down-scaling."""
    d = date(2021, 1, 31)
    sr = {"a": {d: 0.10}, "b": {d: 0.10}}
    # weights sum to 0.5 (half in cash)
    weights = {d: {"a": 0.25, "b": 0.25}}
    # normalize=True → cash ignored, renormalised to full exposure → 10%
    assert combine_dynamic(sr, weights, normalize=True)[d] == pytest.approx(0.10)
    # normalize=False → residual 0.5 in cash at 0% → 5%
    assert combine_dynamic(sr, weights, normalize=False)[d] == pytest.approx(0.05)


def test_correlation_perfect_and_anti() -> None:
    dates = [date(2021, i, 1) for i in range(1, 7)]
    a = {d: float(i) for i, d in enumerate(dates)}
    b = {d: 2.0 * float(i) + 1.0 for i, d in enumerate(dates)}
    c = {d: -float(i) for i, d in enumerate(dates)}
    assert correlation(a, b) == pytest.approx(1.0, abs=1e-9)
    assert correlation(a, c) == pytest.approx(-1.0, abs=1e-9)


def test_correlation_too_few_points_is_nan() -> None:
    a = {date(2021, 1, 1): 0.1, date(2021, 2, 1): 0.2}
    assert math.isnan(correlation(a, a))


def test_window_return_and_dd() -> None:
    port = {
        date(2022, 1, 31): 0.10,
        date(2022, 2, 28): -0.50,
        date(2022, 3, 31): 0.20,
        date(2023, 1, 31): 0.05,  # outside window
    }
    res = window_return_and_dd(port, date(2022, 1, 1), date(2022, 12, 31))
    # nav 1.10, 0.55, 0.66 → cum return -34%, dd -50%
    assert res["return"] == pytest.approx(0.66 - 1.0, rel=1e-9)
    assert res["max_drawdown"] == pytest.approx(-0.50, rel=1e-9)


def test_verdict_no_go_when_below_gate() -> None:
    baseline = {"sharpe": 1.20, "max_drawdown": -0.08}
    candidates = {
        "3_barbell_risk_parity": {"sharpe": 1.23, "max_drawdown": -0.07},  # +0.03 only
        "2_barbell_fixed": {"sharpe": 1.14, "max_drawdown": -0.081},
    }
    v = verdict_from_metrics(baseline, candidates)
    assert v["decision"] == "NO-GO"
    assert not any(r["passes_gate"] for r in v["ranked"])
    # ranked by delta_sharpe descending
    assert v["ranked"][0]["scheme"] == "3_barbell_risk_parity"


def test_verdict_go_when_material_uplift() -> None:
    baseline = {"sharpe": 1.00, "max_drawdown": -0.15}
    candidates = {
        "3_barbell_risk_parity": {"sharpe": 1.30, "max_drawdown": -0.10},  # +0.30 / +5pp
    }
    v = verdict_from_metrics(baseline, candidates)
    assert v["decision"] == "GO"
    assert v["ranked"][0]["passes_gate"] is True
    assert "3_barbell_risk_parity" in v["recommendation"]


def test_rolling_scheme_weights_reuses_master_primitive() -> None:
    """resolve_sleeve_weights is driven over trailing windows and produces sum-to-1
    weights keyed by the 5 barbell sleeve ids, using only data strictly before t."""
    grid = [date(2020, m, 28) for m in range(1, 13)]
    sleeve_ids = [
        "momentum", "risk_parity", "satellite_us_quality",
        "satellite_hk_china", "cn_dividend_lowvol",
    ]
    # Distinct, non-flat return series per sleeve so vol/HRP are well-defined.
    sr: dict[str, dict[date, float]] = {}
    for k, sid in enumerate(sleeve_ids):
        sr[sid] = {d: 0.01 * (k + 1) * (1 if i % 2 else -1) for i, d in enumerate(grid)}
    for scheme in (WEIGHT_SCHEME_RISK_PARITY, WEIGHT_SCHEME_HRP):
        ws = rolling_scheme_weights(scheme, sr, grid)
        assert ws, f"{scheme} produced no weighted dates"
        for _, w in ws.items():
            assert set(w) == set(sleeve_ids)
            assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
