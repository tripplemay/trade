"""B092 — deterministic unit tests for the US attack backtest mechanics.

Covers the mechanical, no-look-ahead pieces of the research backtest:
momentum window, top-15 selection, equal-weight, monthly signal dates, the
point-in-time quality gate, the data-integrity spike/return guards, and the
SEC annual-fundamentals extractor. No network / no cached data is touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research.b092_us_attack_backtest import (
    MAX_MONTH_RATIO,
    cagr,
    clean_price_spikes,
    equal_weight,
    max_drawdown,
    momentum_skip,
    month_end_dates,
    period_return,
    qualified_tickers,
    quality_asof,
    select_top,
    sharpe,
    turnover,
)
from scripts.research.b092_us_universe_fetch import extract_annual_fundamentals


def _wide(prices_by_ticker: dict[str, dict[str, float]]) -> pd.DataFrame:
    """{ticker: {iso_date: price}} -> wide adj_close frame (index datetime)."""

    frame = pd.DataFrame(prices_by_ticker)
    frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


# ---------------------------------------------------------------------------
# Momentum window + no look-ahead
# ---------------------------------------------------------------------------


def test_momentum_skip_uses_6m_to_1m_window() -> None:
    # Daily-ish anchors: t=2020-12-31. end=t-1mo=2020-11-30, start=end-6mo=2020-05-31.
    dates = pd.date_range("2020-01-31", "2020-12-31", freq="ME")
    prices = {d.strftime("%Y-%m-%d"): 100.0 for d in dates}
    prices["2020-05-31"] = 100.0  # start anchor (last <= 2020-05-31)
    prices["2020-11-30"] = 130.0  # end anchor (last <= 2020-11-30)
    wide = _wide({"AAA": prices})
    mom = momentum_skip(wide, pd.Timestamp("2020-12-31"))
    assert mom["AAA"] == pytest.approx(0.30)


def test_momentum_skip_ignores_recent_month_and_future() -> None:
    dates = pd.date_range("2020-01-31", "2020-11-30", freq="ME")
    prices = {d.strftime("%Y-%m-%d"): 100.0 for d in dates}
    prices["2020-05-31"] = 100.0
    prices["2020-11-30"] = 120.0
    base = momentum_skip(_wide({"AAA": dict(prices)}), pd.Timestamp("2020-12-31"))
    # Add the skipped month (Dec) AND a future spike — momentum must not change.
    prices["2020-12-31"] = 500.0
    prices["2021-06-30"] = 999.0
    after = momentum_skip(_wide({"AAA": prices}), pd.Timestamp("2020-12-31"))
    assert after["AAA"] == pytest.approx(base["AAA"]) == pytest.approx(0.20)


def test_momentum_skip_nan_without_anchor() -> None:
    wide = _wide({"AAA": {"2020-11-30": 100.0, "2020-12-31": 110.0}})
    mom = momentum_skip(wide, pd.Timestamp("2020-12-31"))
    assert np.isnan(mom["AAA"])  # no start anchor 7 months back


# ---------------------------------------------------------------------------
# Selection / weighting
# ---------------------------------------------------------------------------


def test_select_top_ranks_by_momentum_within_candidates() -> None:
    mom = pd.Series({"A": 0.5, "B": 0.9, "C": 0.1, "D": 0.7, "E": 0.8})
    # C excluded by candidate set even though it would rank last anyway; B,D,E top-3.
    picked = select_top(mom, {"A", "B", "D", "E"}, n=3)
    assert picked == ["B", "E", "D"]


def test_select_top_skips_nan_and_non_candidates() -> None:
    mom = pd.Series({"A": np.nan, "B": 0.9, "C": 0.5})
    assert select_top(mom, {"A", "B", "C"}, n=5) == ["B", "C"]


def test_equal_weight_sums_to_one() -> None:
    w = equal_weight(["A", "B", "C", "D", "E"])
    assert all(v == pytest.approx(0.2) for v in w.values())
    assert sum(w.values()) == pytest.approx(1.0)
    assert equal_weight([]) == {}


# ---------------------------------------------------------------------------
# Monthly signal dates
# ---------------------------------------------------------------------------


def test_month_end_dates_picks_last_trading_day_per_month() -> None:
    idx = pd.to_datetime(
        ["2021-01-04", "2021-01-29", "2021-02-01", "2021-02-26", "2021-03-31"]
    )
    ends = month_end_dates(pd.DatetimeIndex(idx))
    assert ends == [
        pd.Timestamp("2021-01-29"),
        pd.Timestamp("2021-02-26"),
        pd.Timestamp("2021-03-31"),
    ]


# ---------------------------------------------------------------------------
# No look-ahead in the forward return + data guard
# ---------------------------------------------------------------------------


def test_period_return_uses_forward_prices_only() -> None:
    wide = _wide({"A": {"2021-01-29": 100.0, "2021-02-26": 110.0}})
    r = period_return(wide, {"A": 1.0}, pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26"))
    assert r == pytest.approx(0.10)


def test_period_return_equal_weight_two_names() -> None:
    wide = _wide(
        {
            "A": {"2021-01-29": 100.0, "2021-02-26": 110.0},
            "B": {"2021-01-29": 100.0, "2021-02-26": 90.0},
        }
    )
    r = period_return(
        wide, equal_weight(["A", "B"]),
        pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26"),
    )
    assert r == pytest.approx(0.0)


def test_period_return_drops_implausible_move() -> None:
    # B's 10x move exceeds MAX_MONTH_RATIO -> dropped; only A contributes.
    assert MAX_MONTH_RATIO < 10.0
    wide = _wide(
        {
            "A": {"2021-01-29": 100.0, "2021-02-26": 110.0},
            "B": {"2021-01-29": 100.0, "2021-02-26": 1000.0},
        }
    )
    r = period_return(
        wide, equal_weight(["A", "B"]),
        pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26"),
    )
    assert r == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Point-in-time quality gate
# ---------------------------------------------------------------------------


def _fund_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ticker": "A", "period_end": "2019-12-31", "filed": "2020-02-15",
             "net_income": 10.0, "equity": 100.0, "liabilities": 50.0,
             "roe": 0.10, "debt_to_equity": 0.5},
            {"ticker": "A", "period_end": "2020-12-31", "filed": "2021-02-15",
             "net_income": 20.0, "equity": 100.0, "liabilities": 50.0,
             "roe": 0.20, "debt_to_equity": 0.5},
        ]
    )


def test_quality_asof_is_point_in_time() -> None:
    # Before the 2020 filing is public, only the 2019 filing is visible.
    q = quality_asof(_fund_frame(), pd.Timestamp("2021-01-01"))
    assert q.loc["A", "roe"] == pytest.approx(0.10)
    # After it is filed, the newer one wins.
    q2 = quality_asof(_fund_frame(), pd.Timestamp("2021-03-01"))
    assert q2.loc["A", "roe"] == pytest.approx(0.20)


def test_qualified_tickers_drops_negative_earnings_and_bottom_quartile() -> None:
    q = pd.DataFrame(
        {
            "roe": [0.30, 0.25, 0.20, 0.15, 0.05, -0.10],
            "debt_to_equity": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "net_income": [30.0, 25.0, 20.0, 15.0, 5.0, -10.0],
        },
        index=["A", "B", "C", "D", "E", "F"],
    )
    keep = qualified_tickers(q, drop_quantile=0.25)
    assert "F" not in keep  # negative earnings
    assert "E" not in keep  # bottom-quartile composite
    assert {"A", "B", "C"} <= keep


# ---------------------------------------------------------------------------
# Spike cleaning
# ---------------------------------------------------------------------------


def test_clean_price_spikes_removes_roundtrip_glitch() -> None:
    rows = []
    for iso, px in [
        ("2021-01-04", 100.0),
        ("2021-01-05", 101.0),
        ("2021-01-06", 5000.0),  # spurious spike up
        ("2021-01-07", 102.0),   # reverts
        ("2021-01-08", 103.0),
    ]:
        rows.append({"date": iso, "ticker": "A", "adj_close": px})
    cleaned = clean_price_spikes(pd.DataFrame(rows))
    assert 5000.0 not in set(cleaned["adj_close"])
    assert len(cleaned) == 4


def test_clean_price_spikes_keeps_legit_trend() -> None:
    rows = [{"date": f"2021-01-0{i}", "ticker": "A", "adj_close": 100.0 + i} for i in range(1, 9)]
    cleaned = clean_price_spikes(pd.DataFrame(rows))
    assert len(cleaned) == 8  # a smooth uptrend loses nothing


# ---------------------------------------------------------------------------
# Turnover + metrics
# ---------------------------------------------------------------------------


def test_turnover_full_swap_is_two() -> None:
    prev = {"A": 0.5, "B": 0.5}
    new = {"C": 0.5, "D": 0.5}
    assert turnover(prev, new) == pytest.approx(2.0)
    assert turnover({}, {"A": 1.0}) == pytest.approx(1.0)
    assert turnover(new, new) == pytest.approx(0.0)


def test_metrics_on_known_series() -> None:
    dates = [pd.Timestamp("2020-01-31"), pd.Timestamp("2021-01-31")]
    assert cagr([0.10, 0.10], dates) == pytest.approx((1.21) ** (365.25 / 366.0) - 1.0, rel=1e-3)
    # Zero-variance returns -> undefined Sharpe.
    assert np.isnan(sharpe([0.01, 0.01, 0.01]))
    # Positive-variance sanity: sign is positive.
    assert sharpe([0.02, -0.01, 0.03, 0.01]) > 0
    assert max_drawdown([0.1, -0.5, 0.2]) == pytest.approx(-0.5)
    assert max_drawdown([0.1, 0.1, 0.1]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# SEC annual-fundamentals extractor (fetch module, pure)
# ---------------------------------------------------------------------------


def test_extract_annual_fundamentals_joins_ni_equity_liabilities() -> None:
    companyfacts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {"units": {"USD": [
                    {"end": "2022-12-31", "val": 20.0, "filed": "2023-02-10",
                     "fp": "FY", "form": "10-K"},
                    {"end": "2022-09-30", "val": 5.0, "filed": "2022-11-01",
                     "fp": "Q3", "form": "10-Q"},
                ]}},
                "StockholdersEquity": {"units": {"USD": [
                    {"end": "2022-12-31", "val": 100.0, "filed": "2023-02-10"},
                ]}},
                "Liabilities": {"units": {"USD": [
                    {"end": "2022-12-31", "val": 40.0, "filed": "2023-02-10"},
                ]}},
            }
        }
    }
    recs = extract_annual_fundamentals(companyfacts, "A")
    assert len(recs) == 1  # only the annual FY period, not the Q3
    rec = recs[0]
    assert rec["roe"] == pytest.approx(0.20)
    assert rec["debt_to_equity"] == pytest.approx(0.40)
    assert rec["filed"] == "2023-02-10"


def test_extract_annual_fundamentals_skips_nonpositive_equity() -> None:
    companyfacts = {
        "facts": {"us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [
                {"end": "2022-12-31", "val": 20.0, "filed": "2023-02-10",
                 "fp": "FY", "form": "10-K"},
            ]}},
            "StockholdersEquity": {"units": {"USD": [
                {"end": "2022-12-31", "val": -5.0, "filed": "2023-02-10"},
            ]}},
        }}
    }
    assert extract_annual_fundamentals(companyfacts, "A") == []
