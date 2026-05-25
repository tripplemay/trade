"""Unit tests for the B025 US Quality Momentum factor zoo."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trade.data.us_quality_universe import (
    load_fundamentals,
    load_prices,
    load_universe,
)
from trade.strategies.us_quality_momentum.factors import (
    FactorInputError,
    low_vol_score,
    momentum_6m,
    momentum_12_1,
    quality_score,
    trend_score,
    value_score,
)

FIXTURE_AS_OF = date(2024, 1, 2)
EXPECTED_TICKER_COUNT = 30


# ---------------------------------------------------------------------------
# Helpers — small synthetic frames for edge-case tests
# ---------------------------------------------------------------------------


def _synthetic_prices(
    tickers: list[str],
    start: date,
    days: int,
    *,
    daily_return: dict[str, float] | None = None,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Long-format price frame with a per-ticker constant daily return."""

    daily_return = daily_return or {ticker: 0.0 for ticker in tickers}
    dates = pd.bdate_range(start=pd.Timestamp(start), periods=days)
    rows: list[pd.DataFrame] = []
    for ticker in tickers:
        ret = daily_return[ticker]
        # Deterministic geometric series (no randomness) so tests are exact.
        path = start_price * np.power(1.0 + ret, np.arange(days))
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "open": path,
                    "high": path,
                    "low": path,
                    "close": path,
                    "adj_close": path,
                    "volume": 1_000_000,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def _synthetic_fundamentals(rows: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["report_date"] = pd.to_datetime(df["report_date"])
    if "fiscal_quarter_end" in df.columns:
        df["fiscal_quarter_end"] = pd.to_datetime(df["fiscal_quarter_end"])
    return df


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


def test_momentum_12_1_returns_positive_for_uptrending_ticker() -> None:
    prices = _synthetic_prices(
        tickers=["UP", "DOWN"],
        start=date(2022, 1, 3),
        days=400,
        daily_return={"UP": 0.001, "DOWN": -0.001},
    )
    result = momentum_12_1(prices, date(2023, 6, 1))
    assert result["UP"] > 0
    assert result["DOWN"] < 0


def test_momentum_12_1_returns_nan_when_history_too_short() -> None:
    prices = _synthetic_prices(
        tickers=["SHORT"],
        start=date(2023, 1, 3),
        days=20,  # well below 12 months
        daily_return={"SHORT": 0.001},
    )
    result = momentum_12_1(prices, date(2023, 2, 1))
    assert pd.isna(result["SHORT"])


def test_momentum_12_1_is_point_in_time() -> None:
    prices = _synthetic_prices(
        tickers=["AA"],
        start=date(2022, 1, 3),
        days=600,
        daily_return={"AA": 0.001},
    )
    # If we accidentally peeked at future data, this would change.
    early = momentum_12_1(prices, date(2023, 1, 3))
    later = momentum_12_1(prices, date(2023, 12, 1))
    assert early["AA"] != later["AA"]


def test_momentum_6m_uses_six_month_lookback() -> None:
    # Same ticker, identical drift — 6-month return should be < 12-1 return.
    prices = _synthetic_prices(
        tickers=["AA"],
        start=date(2022, 1, 3),
        days=400,
        daily_return={"AA": 0.001},
    )
    m12 = momentum_12_1(prices, date(2023, 6, 1))
    m6 = momentum_6m(prices, date(2023, 6, 1))
    assert m12["AA"] > m6["AA"] > 0


def test_momentum_12_1_rejects_invalid_lookback() -> None:
    prices = _synthetic_prices(["AA"], date(2022, 1, 3), 100)
    with pytest.raises(FactorInputError, match="lookback"):
        momentum_12_1(prices, date(2023, 1, 1), lookback_months=0)


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------


def test_quality_score_orders_by_composite_metric() -> None:
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2023-11-01",
                "ticker": "STRONG",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.50,
                "gross_margin": 0.80,
                "fcf_yield": 0.10,
                "debt_to_assets": 0.10,
                "pe": 20.0,
                "pb": 4.0,
                "ev_ebitda": 12.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2023-11-01",
                "ticker": "WEAK",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.05,
                "gross_margin": 0.10,
                "fcf_yield": 0.01,
                "debt_to_assets": 0.80,
                "pe": 35.0,
                "pb": 6.0,
                "ev_ebitda": 25.0,
                "earnings_yield": 0.02,
            },
        ]
    )
    result = quality_score(fundamentals, date(2024, 1, 1))
    assert result["STRONG"] > result["WEAK"]


def test_quality_score_uses_latest_report_per_ticker() -> None:
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2023-05-01",
                "ticker": "TGT",
                "fiscal_quarter": "2023Q1",
                "fiscal_quarter_end": "2023-03-31",
                "roe": 0.05,
                "gross_margin": 0.20,
                "fcf_yield": 0.02,
                "debt_to_assets": 0.40,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2023-11-01",
                "ticker": "TGT",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.60,  # latest report has very strong metrics
                "gross_margin": 0.80,
                "fcf_yield": 0.12,
                "debt_to_assets": 0.10,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2023-11-01",
                "ticker": "OTHER",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.10,
                "gross_margin": 0.30,
                "fcf_yield": 0.03,
                "debt_to_assets": 0.50,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
        ]
    )
    result = quality_score(fundamentals, date(2024, 1, 1))
    # TGT's latest (Q3 2023) is the strong row — it should outrank OTHER.
    assert result["TGT"] > result["OTHER"]


def test_quality_score_point_in_time_ignores_unpublished_reports() -> None:
    # Two tickers so percent_rank actually has a cross-section to differentiate
    # weak vs strong fundamentals (a single ticker collapses to rank == 1.0
    # across every metric).
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2023-05-01",
                "ticker": "T",
                "fiscal_quarter": "2023Q1",
                "fiscal_quarter_end": "2023-03-31",
                "roe": 0.05,
                "gross_margin": 0.20,
                "fcf_yield": 0.02,
                "debt_to_assets": 0.40,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2024-02-04",
                "ticker": "T",
                "fiscal_quarter": "2023Q4",
                "fiscal_quarter_end": "2023-12-31",
                "roe": 0.50,
                "gross_margin": 0.80,
                "fcf_yield": 0.12,
                "debt_to_assets": 0.10,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
            # Comparator ticker — same baseline both periods so the
            # cross-section keeps a stable reference point.
            {
                "report_date": "2023-05-01",
                "ticker": "REF",
                "fiscal_quarter": "2023Q1",
                "fiscal_quarter_end": "2023-03-31",
                "roe": 0.20,
                "gross_margin": 0.40,
                "fcf_yield": 0.05,
                "debt_to_assets": 0.30,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2024-02-04",
                "ticker": "REF",
                "fiscal_quarter": "2023Q4",
                "fiscal_quarter_end": "2023-12-31",
                "roe": 0.20,
                "gross_margin": 0.40,
                "fcf_yield": 0.05,
                "debt_to_assets": 0.30,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            },
        ]
    )
    # as_of = 2024-01-01 — only the Q1 2023 rows for both tickers are visible.
    early = quality_score(fundamentals, date(2024, 1, 1))
    # as_of = 2024-03-01 — both tickers now flip to their Q4 2023 rows; T's
    # stronger metrics should rank above REF.
    later = quality_score(fundamentals, date(2024, 3, 1))
    assert early["T"] < early["REF"]
    assert later["T"] > later["REF"]


def test_quality_score_returns_empty_when_no_visible_rows() -> None:
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2030-01-01",
                "ticker": "FUTURE",
                "fiscal_quarter": "2029Q4",
                "fiscal_quarter_end": "2029-12-31",
                "roe": 0.5,
                "gross_margin": 0.5,
                "fcf_yield": 0.05,
                "debt_to_assets": 0.3,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 14.0,
                "earnings_yield": 0.05,
            }
        ]
    )
    result = quality_score(fundamentals, date(2020, 1, 1))
    assert result.empty


# ---------------------------------------------------------------------------
# Low volatility
# ---------------------------------------------------------------------------


def test_low_vol_score_ranks_low_volatility_ticker_higher() -> None:
    # Two tickers, exact same arithmetic mean return but different vol via
    # alternating sign on one of them.
    days = 320
    dates = pd.bdate_range(start=pd.Timestamp(date(2022, 1, 3)), periods=days)
    # CALM: 0.0005 every day → vol ~ 0.
    calm = 100.0 * np.power(1.0 + 0.0005, np.arange(days))
    # CHOP: alternating +5% / -5% → very high vol.
    chop_returns = np.array([0.05 if i % 2 == 0 else -0.05 for i in range(days)])
    chop = 100.0 * np.cumprod(1.0 + chop_returns)
    prices = pd.concat(
        [
            pd.DataFrame({"date": dates, "ticker": "CALM", "adj_close": calm}),
            pd.DataFrame({"date": dates, "ticker": "CHOP", "adj_close": chop}),
        ],
        ignore_index=True,
    )
    result = low_vol_score(prices, date(2023, 6, 1))
    assert result["CALM"] > result["CHOP"]


def test_low_vol_score_returns_nan_for_insufficient_history() -> None:
    prices = _synthetic_prices(
        tickers=["A"],
        start=date(2024, 1, 1),
        days=30,
        daily_return={"A": 0.0},
    )
    result = low_vol_score(prices, date(2024, 2, 1))
    assert pd.isna(result["A"])


def test_low_vol_score_supports_custom_windows() -> None:
    prices = _synthetic_prices(
        tickers=["A", "B"],
        start=date(2022, 1, 3),
        days=300,
        daily_return={"A": 0.001, "B": -0.001},
    )
    # Smaller windows make the test cheaper and still exercise the codepath.
    result = low_vol_score(prices, date(2023, 1, 1), windows=(20, 40))
    assert set(result.index) == {"A", "B"}


def test_low_vol_score_rejects_invalid_window() -> None:
    prices = _synthetic_prices(["A"], date(2022, 1, 3), 100)
    with pytest.raises(FactorInputError, match="window"):
        low_vol_score(prices, date(2022, 3, 1), windows=(1,))


# ---------------------------------------------------------------------------
# Value
# ---------------------------------------------------------------------------


def test_value_score_orders_cheap_above_expensive() -> None:
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2023-11-01",
                "ticker": "CHEAP",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.2,
                "gross_margin": 0.3,
                "fcf_yield": 0.10,
                "debt_to_assets": 0.4,
                "pe": 8.0,
                "pb": 1.0,
                "ev_ebitda": 6.0,
                "earnings_yield": 0.12,
            },
            {
                "report_date": "2023-11-01",
                "ticker": "EXPENSIVE",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.2,
                "gross_margin": 0.3,
                "fcf_yield": 0.01,
                "debt_to_assets": 0.4,
                "pe": 50.0,
                "pb": 10.0,
                "ev_ebitda": 30.0,
                "earnings_yield": 0.02,
            },
        ]
    )
    result = value_score(fundamentals, date(2024, 1, 1))
    assert result["CHEAP"] > result["EXPENSIVE"]


def test_value_score_handles_non_positive_denominator_via_nan() -> None:
    fundamentals = _synthetic_fundamentals(
        [
            {
                "report_date": "2023-11-01",
                "ticker": "POS",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": 0.1,
                "gross_margin": 0.3,
                "fcf_yield": 0.05,
                "debt_to_assets": 0.3,
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": 12.0,
                "earnings_yield": 0.05,
            },
            {
                "report_date": "2023-11-01",
                "ticker": "NEG",
                "fiscal_quarter": "2023Q3",
                "fiscal_quarter_end": "2023-09-30",
                "roe": -0.05,
                "gross_margin": 0.3,
                "fcf_yield": 0.05,
                "debt_to_assets": 0.3,
                "pe": -10.0,  # negative earnings → safe_inverse → NaN
                "pb": 3.0,
                "ev_ebitda": 12.0,
                "earnings_yield": -0.01,
            },
        ]
    )
    result = value_score(fundamentals, date(2024, 1, 1))
    assert result.isna().sum() == 0  # NaN cells skipped by average_ranks, ticker still scored
    assert (result.between(0.0, 1.0)).all()


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------


def test_trend_score_returns_one_for_all_bull_conditions() -> None:
    prices = _synthetic_prices(
        tickers=["BULL"],
        start=date(2022, 1, 3),
        days=400,
        daily_return={"BULL": 0.001},
    )
    result = trend_score(prices, date(2023, 6, 1))
    assert result["BULL"] == pytest.approx(1.0)


def test_trend_score_returns_zero_for_all_bear_conditions() -> None:
    prices = _synthetic_prices(
        tickers=["BEAR"],
        start=date(2022, 1, 3),
        days=400,
        daily_return={"BEAR": -0.001},
    )
    result = trend_score(prices, date(2023, 6, 1))
    assert result["BEAR"] == pytest.approx(0.0)


def test_trend_score_returns_nan_for_insufficient_history() -> None:
    prices = _synthetic_prices(
        tickers=["NEW"],
        start=date(2024, 6, 1),
        days=30,
        daily_return={"NEW": 0.0},
    )
    result = trend_score(prices, date(2024, 7, 15))
    assert pd.isna(result["NEW"])


def test_trend_score_intermediate_band_falls_in_unit_interval() -> None:
    # Construct two tickers where bull/bear differ; partial cases come from the
    # transition region. Use mixed slopes so the partial result is in (0, 1).
    prices = _synthetic_prices(
        tickers=["BULL", "BEAR", "FLAT"],
        start=date(2022, 1, 3),
        days=400,
        daily_return={"BULL": 0.001, "BEAR": -0.001, "FLAT": 0.0},
    )
    result = trend_score(prices, date(2023, 6, 1))
    for ticker in ("BULL", "BEAR", "FLAT"):
        assert 0.0 <= result[ticker] <= 1.0


def test_trend_score_rejects_inverted_ma_lengths() -> None:
    prices = _synthetic_prices(["A"], date(2022, 1, 3), 300)
    with pytest.raises(FactorInputError, match="ma_short"):
        trend_score(prices, date(2023, 1, 1), ma_short=200, ma_long=50)


# ---------------------------------------------------------------------------
# Cross-factor / fixture-backed integration
# ---------------------------------------------------------------------------


def test_all_factors_against_real_fixture_return_full_universe_series() -> None:
    universe = load_universe()
    prices = load_prices()
    fundamentals = load_fundamentals()
    factor_outputs = {
        "momentum_12_1": momentum_12_1(prices, FIXTURE_AS_OF),
        "momentum_6m": momentum_6m(prices, FIXTURE_AS_OF),
        "quality_score": quality_score(fundamentals, FIXTURE_AS_OF),
        "low_vol_score": low_vol_score(prices, FIXTURE_AS_OF),
        "value_score": value_score(fundamentals, FIXTURE_AS_OF),
        "trend_score": trend_score(prices, FIXTURE_AS_OF),
    }
    expected_tickers = {entry.ticker for entry in universe}
    for name, series in factor_outputs.items():
        assert set(series.index).issubset(expected_tickers), name
        assert series.count() >= EXPECTED_TICKER_COUNT - 3, (
            f"{name} returned too many NaNs"
        )


def test_factor_outputs_are_deterministic_across_repeat_calls() -> None:
    prices = load_prices()
    fundamentals = load_fundamentals()
    m1 = momentum_12_1(prices, FIXTURE_AS_OF)
    m2 = momentum_12_1(prices, FIXTURE_AS_OF)
    pd.testing.assert_series_equal(m1, m2)
    q1 = quality_score(fundamentals, FIXTURE_AS_OF)
    q2 = quality_score(fundamentals, FIXTURE_AS_OF)
    pd.testing.assert_series_equal(q1, q2)
    t1 = trend_score(prices, FIXTURE_AS_OF)
    t2 = trend_score(prices, FIXTURE_AS_OF)
    pd.testing.assert_series_equal(t1, t2)


def test_low_vol_score_against_fixture_outranks_synthetic_chop_tickers() -> None:
    # The synthetic ZQ* tickers were specced with higher sigmas; they should
    # consistently land at the *low* end of low_vol_score (high vol → low score).
    prices = load_prices()
    result = low_vol_score(prices, FIXTURE_AS_OF)
    synthetic_chop = result[["ZQAI", "ZQPT", "ZQLH"]].dropna()
    real_calm = result[["KO", "PG", "JNJ"]].dropna()
    if not synthetic_chop.empty and not real_calm.empty:
        assert synthetic_chop.mean() < real_calm.mean()


def test_strategy_package_has_no_sklearn_or_ml_fit_predict_imports() -> None:
    """Hard safety net for the B025 ML boundary (spec §3).

    Scans only Python source (not docstrings) for ``import sklearn`` /
    ``from sklearn`` / ``.fit(`` / ``.predict(`` so docstring references to
    the ban (allowed) do not trip the check.
    """

    import ast
    import importlib
    from pathlib import Path

    package = importlib.import_module("trade.strategies.us_quality_momentum")
    pkg_dir = Path(package.__file__).parent  # type: ignore[arg-type]
    banned_modules = {"sklearn", "lightgbm", "xgboost", "catboost"}
    banned_method_calls = {"fit", "predict"}
    for py_file in pkg_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned_modules, (
                        f"{py_file.name} imports banned module {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in banned_modules, (
                    f"{py_file.name} imports from banned module {node.module}"
                )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in banned_method_calls, (
                    f"{py_file.name} calls banned method .{node.func.attr}() "
                    f"at line {node.lineno}"
                )
