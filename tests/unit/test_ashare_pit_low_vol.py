"""B111 F005 — A 股低波 first-look 计算工具的单测（含 H7 只算不裁的机器判据）。"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from scripts.research.ashare_pit import low_vol
from scripts.research.ashare_pit.signal_stats import (
    geometric_annual as geometric_annual_decimal,
)

# --- 基础统计等价性 ---


def test_float_geometric_annual_matches_decimal_reference() -> None:
    series = [0.02, -0.01, 0.03, 0.00, 0.015, -0.02]
    got = low_vol.geometric_annual(series)
    ref = geometric_annual_decimal([Decimal(str(x)) for x in series])
    assert got is not None and ref is not None
    assert got == pytest.approx(ref, abs=1e-9)


def test_newey_west_and_simple_t_are_finite() -> None:
    excess = [0.01, -0.005, 0.02, 0.0, 0.015, -0.01, 0.008, 0.003]
    assert low_vol.simple_tstat(excess) is not None
    assert low_vol.newey_west_tstat(excess) is not None


def test_bootstrap_is_deterministic_by_seed() -> None:
    top = [0.02, 0.01, 0.03, -0.01, 0.015, 0.005]
    bench = [0.015, 0.012, 0.02, -0.008, 0.01, 0.004]
    a = low_vol.bootstrap_geometric_excess(top, bench, n_boot=500, seed=7)
    b = low_vol.bootstrap_geometric_excess(top, bench, n_boot=500, seed=7)
    assert a["ci95"] == b["ci95"]
    assert a["p_positive"] == b["p_positive"]


# --- 无前视 σ + G1 滞后 ---


def _grid(n: int) -> list[str]:
    return [f"2013{m:02d}01" if m <= 12 else f"2014{m - 12:02d}01" for m in range(1, n + 1)]


def test_trailing_sigma_uses_only_prior_window() -> None:
    grid = _grid(15)
    series = {date: 0.01 * (i % 3) for i, date in enumerate(grid)}
    # idx=12 → window [0,12): 12 prior months present → sigma finite.
    assert low_vol.trailing_sigma(series, grid, 12, window=12, lag=0) is not None
    # idx=11 → window [-1,11): lo<0 → None (no look-ahead into insufficient history).
    assert low_vol.trailing_sigma(series, grid, 11, window=12, lag=0) is None


def test_g1_lag_shifts_the_window_back_one_month() -> None:
    grid = _grid(20)
    # Non-linear series so shifted windows have genuinely different σ (a linear
    # ramp would give equal σ — std is translation-invariant).
    series = {date: float(i * i) for i, date in enumerate(grid)}
    idx = 15
    no_lag = low_vol.trailing_sigma(series, grid, idx, window=12, lag=0)  # indices [3,15)
    lagged = low_vol.trailing_sigma(series, grid, idx, window=12, lag=1)  # indices [2,14)
    assert no_lag is not None and lagged is not None
    assert no_lag != lagged  # different window members → different realized σ


def test_missing_month_in_window_yields_none() -> None:
    grid = _grid(15)
    series = {date: 0.01 for i, date in enumerate(grid) if i != 5}  # month 5 missing
    assert low_vol.trailing_sigma(series, grid, 12, window=12, lag=0) is None


# --- 分组：V1 = σ 最低 ---


def test_quantiles_put_lowest_sigma_in_v1() -> None:
    obs = [
        low_vol.LowVolObservation(ts_code=f"S{i}", sigma=float(i), forward_return=0.0)
        for i in range(10)
    ]
    assignment = low_vol.assign_low_vol_quantiles(obs)
    assert assignment["S0"] == "V1"  # lowest sigma
    assert assignment["S9"] == "V5"  # highest sigma


def test_liquidity_filter_drops_lowest_turnover() -> None:
    obs = [
        low_vol.LowVolObservation(ts_code=f"S{i}", sigma=0.1, forward_return=0.0)
        for i in range(10)
    ]
    turnover = {f"S{i}": float(i) for i in range(10)}
    kept = low_vol._apply_liquidity_filter(obs, turnover, 0.3)
    kept_codes = {o.ts_code for o in kept}
    assert "S0" not in kept_codes and "S1" not in kept_codes  # lowest 30% dropped
    assert "S9" in kept_codes


# --- 端到端截面 + G1 对照（合成面板）---


def _synthetic_rows() -> list[dict[str, str]]:
    """36 个月 × 200 只股。低 σ 股给略高的前向收益，使 V1 可产生正超额（背景，不作判据）。"""
    rows: list[dict[str, str]] = []
    grid = [f"{2013 + (m // 12)}{(m % 12) + 1:02d}01" for m in range(36)]
    rng_state = 12345
    for stock in range(200):
        vol_scale = 0.01 + 0.001 * (stock % 20)  # per-stock volatility tier
        for date in grid:
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            unit = (rng_state / 0x7FFFFFFF) - 0.5  # deterministic pseudo-noise
            ret = unit * vol_scale + (0.002 if stock % 20 < 4 else 0.0)
            rows.append(
                {
                    "ts_code": f"{stock:06d}.SZ",
                    "formation_date": date,
                    "fwd_ret_stub_0.00": f"{ret:.6f}",
                    "ep": "0.05",
                }
            )
    return rows


def test_build_sections_and_summarize_shape() -> None:
    rows = _synthetic_rows()
    main = low_vol.build_sections(rows, stub="0.00", lag=0)
    g1 = low_vol.build_sections(rows, stub="0.00", lag=1)
    assert main and g1
    summary = low_vol.summarize_low_vol(main, label="main")
    assert summary["n_months"] > 0
    assert "excess_ann_geometric_vs_scored" in summary
    assert "realized_sigma" in summary
    assert summary["arithmetic_side_by_side"]["role"].startswith("disclosed_not_relied")
    # G1 has fewer usable months (needs one more month of history).
    assert low_vol.summarize_low_vol(g1, label="g1_lag1")["n_months"] <= summary["n_months"]


# --- ★H7 机器判据：产物中无任何裁定措辞 ---

_FORBIDDEN = (
    "GO",
    "NO-GO",
    "NOGO",
    "值得投入",
    "有 edge",
    "有edge",
    "建议投入",
    "应当继续",
    "结论是",
)


def test_summary_contains_no_verdict_language_anywhere() -> None:
    rows = _synthetic_rows()
    for lag, label in ((0, "main"), (1, "g1_lag1")):
        sections = low_vol.build_sections(rows, stub="0.00", lag=lag)
        payload = json.dumps(
            low_vol.summarize_low_vol(sections, label=label),
            ensure_ascii=False,
            default=str,
        )
        for word in _FORBIDDEN:
            assert word not in payload, f"产物中出现了结论性措辞: {word}"


def test_cli_run_output_has_no_verdict_language() -> None:
    from scripts.research.ashare_pit import low_vol_cli

    payload = json.dumps(
        low_vol_cli.run(_synthetic_rows()), ensure_ascii=False, default=str
    )
    for word in _FORBIDDEN:
        assert word not in payload, f"CLI 产物中出现了结论性措辞: {word}"
    # G2 defaults to not_executed until the liquidity CSV is fetched.
    result = low_vol_cli.run(_synthetic_rows())
    assert result["variants"]["g2_liquidity_stub_0.00"]["status"] == "not_executed"
    assert "背景不作证据" in result["honesty_statement"]


def test_cli_g2_executes_with_liquidity() -> None:
    from scripts.research.ashare_pit import low_vol_cli

    rows = _synthetic_rows()
    dates = sorted({r["formation_date"] for r in rows})
    stocks = sorted({r["ts_code"] for r in rows})
    # Give every stock a turnover so G2's 30% drop applies uniformly.
    liquidity = {d: {s: float(i + 1) for i, s in enumerate(stocks)} for d in dates}
    result = low_vol_cli.run(rows, liquidity=liquidity)
    g2 = result["variants"]["g2_liquidity_stub_0.00"]
    assert g2["n_months"] > 0  # executed → real stats, not a status stub


def test_honesty_statement_and_thresholds_present() -> None:
    assert "背景不作证据" in low_vol.HONESTY_STATEMENT
    rows = _synthetic_rows()
    summary = low_vol.summarize_low_vol(
        low_vol.build_sections(rows, stub="0.00"), label="main"
    )
    thresholds = summary["criterion_thresholds"]
    assert thresholds["main_risk_sigma_ratio_max"] == 0.90
    assert thresholds["hard_gate_excess_min_pp"] == 1.0
    assert summary["honest_limits"]  # §B.5 limits ride along
