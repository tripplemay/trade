"""B068 F003 — unit tests for the WIDE-universe 4-config weighting comparison.

Covers the mechanics (4 cells, exit fixed, walk-forward, benchmark, red flags,
Q1/Q2/Q3 answers, payload + markdown), not real market values — the real wide-data
numbers are produced + verified at L2 (Codex F004). The synthetic prices give each
name a distinct drift (momentum ordering) and a distinct alternating-amplitude
volatility so inverse_vol weighting genuinely differs from equal.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.reporting.cn_attack_wide_comparison import (
    build_cn_attack_wide_comparison,
    build_cn_attack_wide_payload,
    render_cn_attack_wide_markdown,
)

# Distinct drift → momentum ordering; distinct amplitude → distinct realized σ.
_NAMES = {
    "600519.SH": (0.0016, 0.004),
    "000858.SZ": (0.0013, 0.012),
    "600036.SH": (0.0010, 0.020),
    "300750.SZ": (0.0008, 0.030),
    "002594.SZ": (0.0006, 0.045),
}
# 002594.SZ deliberately gets NO fundamentals → quality drops it, pure keeps it.
_NO_FUNDAMENTALS = "002594.SZ"
_START = date(2023, 6, 1)
_END = date(2024, 12, 31)


def _prices_varied() -> pd.DataFrame:
    days = pd.bdate_range("2022-01-03", "2024-12-31")
    rows: list[dict[str, object]] = []
    for ticker, (drift, amp) in _NAMES.items():
        for i, day in enumerate(days):
            trend = 100.0 * (1.0 + drift) ** i
            price = trend * (1.0 + amp * (1.0 if i % 2 == 0 else -1.0))
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.02,
                    "low": price * 0.98,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _prices_smooth() -> pd.DataFrame:
    # Constant per-name return → σ≈0 → inverse_vol cannot differ from equal.
    days = pd.bdate_range("2022-01-03", "2024-12-31")
    rows: list[dict[str, object]] = []
    for ticker, (drift, _amp) in _NAMES.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + drift) ** i
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _fundamentals() -> pd.DataFrame:
    report_date = pd.Timestamp("2023-04-30")
    rows: list[dict[str, object]] = []
    for i, ticker in enumerate(_NAMES):
        if ticker == _NO_FUNDAMENTALS:
            continue  # dropped by the quality filter, kept by pure momentum
        rows.append(
            {
                "report_date": report_date,
                "ticker": ticker,
                "fiscal_quarter": "2023Q1",
                "fiscal_quarter_end": pd.Timestamp("2023-03-31"),
                "roe": 0.05 + 0.03 * i,
                "gross_margin": 0.20 + 0.05 * i,
                "fcf_yield": 0.01 + 0.005 * i,
                "debt_to_assets": 0.70 - 0.05 * i,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": float("nan"),
                "earnings_yield": 0.05,
            }
        )
    return pd.DataFrame(rows)


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2022, 1, 3): tuple(_NAMES)}


@pytest.fixture(scope="module")
def varied() -> pd.DataFrame:
    return _prices_varied()


@pytest.fixture(scope="module")
def fundamentals() -> pd.DataFrame:
    return _fundamentals()


def test_runs_four_configs_exit_fixed(varied: pd.DataFrame, fundamentals: pd.DataFrame) -> None:
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    assert len(comparison.variants) == 4
    pairs = {(v.factor_variant, v.weighting_scheme) for v in comparison.variants}
    assert pairs == {
        ("quality_momentum", "equal"),
        ("quality_momentum", "inverse_vol"),
        ("pure_momentum", "equal"),
        ("pure_momentum", "inverse_vol"),
    }
    assert comparison.universe_breadth == len(_NAMES)


def test_walk_forward_and_q_answers_present(
    varied: pd.DataFrame, fundamentals: pd.DataFrame
) -> None:
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    assert comparison.in_sample_end is not None
    assert _START < comparison.in_sample_end < _END
    a = comparison.answers
    for verdict in (a.q1_quality_verdict, a.q2_inverse_vol_verdict, a.q3_fragility_verdict):
        assert isinstance(verdict, str) and verdict
    assert a.q1_evidence and a.q2_evidence and a.q3_evidence


def test_inverse_vol_differs_from_equal_with_varying_vol(
    varied: pd.DataFrame, fundamentals: pd.DataFrame
) -> None:
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    by_key = {(v.factor_variant, v.weighting_scheme): v for v in comparison.variants}
    # For pure momentum, equal vs inverse_vol must produce different CAGRs (the
    # weighting genuinely engaged — end-to-end F002→F003 wiring).
    eq = by_key[("pure_momentum", "equal")]
    iv = by_key[("pure_momentum", "inverse_vol")]
    assert eq.cagr != iv.cagr
    # And no weighting_overlay_inert flag (the overlay DID engage on varied vol).
    assert not any(f.startswith("weighting_overlay_inert") for f in comparison.overfitting_flags)


def test_weighting_overlay_inert_flagged_on_constant_vol(fundamentals: pd.DataFrame) -> None:
    # σ≈0 everywhere → inverse_vol degrades to equal → the two weightings are
    # identical per factor → the §29 inert-overlay symptom must be flagged.
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=_prices_smooth(),
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    assert any(f.startswith("weighting_overlay_inert") for f in comparison.overfitting_flags)


def test_no_activity_flag_when_quality_degenerate(varied: pd.DataFrame) -> None:
    # fundamentals=None → quality_momentum has an empty cross-section, never trades.
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=None,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    assert any(f.startswith("no_activity") for f in comparison.overfitting_flags)


def test_benchmark_available_when_provided(
    varied: pd.DataFrame, fundamentals: pd.DataFrame
) -> None:
    bench_days = pd.bdate_range(_START, _END)
    benchmark = pd.Series(
        [3800.0 * (1.0 + 0.0003) ** i for i in range(len(bench_days))], index=bench_days
    )
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=benchmark,
    )
    assert comparison.benchmark.available is True
    assert comparison.benchmark.cagr != 0.0


def test_payload_and_markdown_shapes(varied: pd.DataFrame, fundamentals: pd.DataFrame) -> None:
    comparison = build_cn_attack_wide_comparison(
        _START,
        _END,
        prices=varied,
        fundamentals=fundamentals,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    payload = build_cn_attack_wide_payload(comparison, "run-wide-1")
    assert len(payload["variants"]) == 4  # type: ignore[arg-type]
    assert payload["run"]["research_only"] is True  # type: ignore[index]
    answers = payload["answers"]
    assert set(answers) == {  # type: ignore[arg-type]
        "Q1_quality_adds_value",
        "Q2_inverse_vol_tames_crash",
        "Q3_oos_still_fragile",
    }
    md = render_cn_attack_wide_markdown(comparison)
    assert "宽宇宙重验" in md
    assert "沪深300" in md
    assert "research-only" in md
    assert "Q1" in md and "Q2" in md and "Q3" in md
    # All 4 configs appear in the tables.
    assert md.count("inverse_vol") >= 2
    assert md.count("equal") >= 2
