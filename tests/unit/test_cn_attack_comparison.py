"""B066 F003 — unit tests for the CN attack multi-variant comparison report."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.cn_attack_momentum_quality.engine import CnAttackBacktestConfig
from trade.reporting.cn_attack_momentum_quality import (
    build_cn_attack_comparison,
    build_cn_attack_report_payload,
    render_cn_attack_markdown,
)

_GROWTH = {
    "600519.SH": 0.0020,
    "000858.SZ": 0.0017,
    "600036.SH": 0.0014,
    "300750.SZ": 0.0011,
    "002594.SZ": 0.0008,
}
_START = date(2025, 8, 1)
_END = date(2025, 12, 31)


def _prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-04-01", "2025-12-31")
    rows: list[dict[str, object]] = []
    for ticker, growth in _GROWTH.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.005,
                    "low": price * 0.995,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _universe_history() -> dict[date, tuple[str, ...]]:
    return {date(2024, 4, 1): tuple(_GROWTH)}


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _prices()


def test_runs_all_six_variants(prices: pd.DataFrame) -> None:
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None, universe_history=_universe_history()
    )
    # 2 factor variants × 3 exit variants = 6 cells.
    assert len(comparison.variants) == 6
    pairs = {(v.factor_variant, v.exit_variant) for v in comparison.variants}
    assert len(pairs) == 6
    assert comparison.headline_label == "quality_momentum+momentum_decay"


def test_walk_forward_split_present(prices: pd.DataFrame) -> None:
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None, universe_history=_universe_history()
    )
    assert comparison.in_sample_end is not None
    assert _START < comparison.in_sample_end < _END
    # Each variant carries both in- and out-of-sample metrics.
    for v in comparison.variants:
        assert isinstance(v.in_sample_cagr, float)
        assert isinstance(v.out_sample_cagr, float)


def test_benchmark_unavailable_when_absent(prices: pd.DataFrame) -> None:
    comparison = build_cn_attack_comparison(
        _START,
        _END,
        prices=prices,
        fundamentals=None,
        universe_history=_universe_history(),
        benchmark=pd.Series(dtype=float),
    )
    assert comparison.benchmark.available is False
    md = render_cn_attack_markdown(comparison)
    assert "benchmark unavailable" in md


def test_benchmark_available_when_provided(prices: pd.DataFrame) -> None:
    bench_days = pd.bdate_range("2025-08-01", "2025-12-31")
    benchmark = pd.Series(
        [3800.0 * (1.0 + 0.0005) ** i for i in range(len(bench_days))],
        index=bench_days,
    )
    comparison = build_cn_attack_comparison(
        _START,
        _END,
        prices=prices,
        fundamentals=None,
        universe_history=_universe_history(),
        benchmark=benchmark,
    )
    assert comparison.benchmark.available is True
    assert comparison.benchmark.cagr != 0.0


def test_no_activity_flag_when_headline_degenerate(prices: pd.DataFrame) -> None:
    # fundamentals=None → the quality_momentum variants (incl. the HEADLINE) have an
    # empty cross-section and never trade. The report must NOT silently surface a
    # clean 0.00% — it must raise a no_activity flag, loud for the headline.
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None, universe_history=_universe_history()
    )
    no_activity = [f for f in comparison.overfitting_flags if f.startswith("no_activity")]
    assert no_activity
    assert "INCLUDES HEADLINE" in no_activity[0]


def test_exit_overlay_inert_flagged(prices: pd.DataFrame) -> None:
    # On a smooth uptrend (no >20% dip, no +30% within window) the exit overlays
    # never engage → the 3 exit variants per factor are identical → the report flags
    # the inert-toggle over-fitting symptom the global-spread test would miss.
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None, universe_history=_universe_history()
    )
    assert any(f.startswith("exit_overlay_inert") for f in comparison.overfitting_flags)


def test_implausible_sharpe_flagged(prices: pd.DataFrame) -> None:
    # The synthetic monotone uptrend yields an extreme Sharpe → red flag fires.
    # lot_rounding=False (old口径): B081 F001(2) round-lot cash-drag lowers the Sharpe
    # on this tiny synthetic book below the implausible threshold; the detector's
    # subject here is the OLD extreme-Sharpe口径, so pin it.
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None,
        universe_history=_universe_history(),
        config=CnAttackBacktestConfig(lot_rounding=False),
    )
    assert any("implausible_sharpe" in flag for flag in comparison.overfitting_flags)


def test_payload_and_markdown_shapes(prices: pd.DataFrame) -> None:
    comparison = build_cn_attack_comparison(
        _START, _END, prices=prices, fundamentals=None, universe_history=_universe_history()
    )
    payload = build_cn_attack_report_payload(comparison, "run-cn-1")
    assert set(payload["metrics"]) >= {"CAGR", "Sharpe", "max_drawdown", "turnover"}  # type: ignore[arg-type]
    assert len(payload["variants"]) == 6  # type: ignore[arg-type]
    assert payload["research_only"] is True
    md = render_cn_attack_markdown(comparison)
    assert "多变体对比报告" in md
    assert "沪深300" in md
    assert "research-only" in md
    # All 6 variants appear in the table.
    assert md.count("quality_momentum") + md.count("pure_momentum") >= 6
