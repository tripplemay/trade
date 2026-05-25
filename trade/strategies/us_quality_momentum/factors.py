"""Five pure-function factors for the B025 US Quality Momentum strategy.

Every factor function:

- Accepts a long-format ``pd.DataFrame`` (output of the Repository loaders).
- Accepts an ``as_of`` :class:`datetime.date`. Inputs may already be
  point-in-time filtered by the Repository, but each function re-filters
  defensively so factor calculations cannot leak future data.
- Returns a ``pd.Series[float]`` indexed by ticker, NaN for tickers without
  enough history / data.
- Is pure (no IO, no mutation of inputs, no globals).

The composite-score combiner in F003 percent-ranks each factor before the
0.35/0.30/0.15/0.10/0.10 weighted sum, so raw factor outputs (e.g. momentum
returns) do not need to be self-normalized.

No ``sklearn`` is imported; ML ``fit/predict`` paths are explicitly outside
the B025 scope (spec §3 ML boundary).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trade.strategies.us_quality_momentum.ranking import (
    average_ranks,
    percent_rank,
    safe_inverse,
)

DEFAULT_LOW_VOL_WINDOWS: tuple[int, ...] = (60, 120, 252)
DEFAULT_MA_SHORT = 50
DEFAULT_MA_LONG = 200
DEFAULT_TREND_SLOPE_WINDOW = 20
DEFAULT_PASS_SCORE = 1.0
DEFAULT_FAIL_SCORE = 0.0
TRADING_DAYS_PER_YEAR = 252


class FactorInputError(ValueError):
    """Raised when a factor function receives malformed input."""


def _ensure_columns(frame: pd.DataFrame, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise FactorInputError(f"input frame missing columns: {missing}")


def _visible_prices(prices: pd.DataFrame, as_of: date) -> pd.DataFrame:
    _ensure_columns(prices, ("date", "ticker", "adj_close"))
    cutoff = pd.Timestamp(as_of)
    visible = prices.loc[prices["date"] <= cutoff].copy()
    visible["date"] = pd.to_datetime(visible["date"])
    return visible


def _wide_adjusted_close(prices: pd.DataFrame, as_of: date) -> pd.DataFrame:
    visible = _visible_prices(prices, as_of)
    return (
        visible.pivot_table(
            index="date", columns="ticker", values="adj_close", aggfunc="last"
        )
        .sort_index()
    )


def _latest_fundamentals_row_per_ticker(
    fundamentals: pd.DataFrame, as_of: date
) -> pd.DataFrame:
    required = (
        "report_date",
        "ticker",
        "roe",
        "gross_margin",
        "fcf_yield",
        "debt_to_assets",
        "pe",
        "pb",
        "ev_ebitda",
        "earnings_yield",
    )
    _ensure_columns(fundamentals, required)
    cutoff = pd.Timestamp(as_of)
    visible = fundamentals.loc[fundamentals["report_date"] <= cutoff]
    if visible.empty:
        return visible.iloc[0:0].set_index("ticker")
    # Latest row per ticker by report_date (then ticker for stable tie-break).
    ordered = visible.sort_values(["ticker", "report_date"])
    latest = ordered.groupby("ticker", as_index=False).tail(1)
    return latest.set_index("ticker")


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


def _last_price_on_or_before(wide: pd.DataFrame, cutoff: pd.Timestamp) -> pd.Series:
    eligible = wide.loc[wide.index <= cutoff]
    if eligible.empty:
        return pd.Series(np.nan, index=wide.columns, dtype=float)
    return eligible.iloc[-1]


def momentum_12_1(
    prices: pd.DataFrame,
    as_of: date,
    lookback_months: int = 12,
    skip_months: int = 1,
) -> pd.Series:
    """Classic 12-1 cross-sectional momentum.

    Returns ``adj_close(end) / adj_close(start) - 1`` per ticker, where
    ``end = as_of - skip_months`` and ``start = end - lookback_months``.
    Tickers without both anchors return NaN.
    """

    if lookback_months <= 0 or skip_months < 0:
        raise FactorInputError("lookback_months > 0 and skip_months >= 0 required")
    wide = _wide_adjusted_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=float)
    end_cutoff = pd.Timestamp(as_of) - pd.DateOffset(months=skip_months)
    start_cutoff = end_cutoff - pd.DateOffset(months=lookback_months)
    end_prices = _last_price_on_or_before(wide, end_cutoff)
    start_prices = _last_price_on_or_before(wide, start_cutoff)
    start_safe = start_prices.where(start_prices > 0)
    return (end_prices / start_safe) - 1.0


def momentum_6m(prices: pd.DataFrame, as_of: date) -> pd.Series:
    """Auxiliary 6-month momentum (still skips the most recent month)."""

    return momentum_12_1(prices, as_of, lookback_months=6, skip_months=1)


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------


def quality_score(fundamentals: pd.DataFrame, as_of: date) -> pd.Series:
    """Quality composite per spec §F002.

    Formula::

        rank(roe) + rank(gross_margin) + rank(fcf_yield) - rank(debt_to_assets)

    Each component is percent-ranked across the cross-section before the
    additive composition. Higher debt-to-assets is penalized via subtraction.
    The result is the raw additive score; F003 percent-ranks again before the
    weighted total.
    """

    latest = _latest_fundamentals_row_per_ticker(fundamentals, as_of)
    if latest.empty:
        return pd.Series(dtype=float)
    return (
        percent_rank(latest["roe"])
        + percent_rank(latest["gross_margin"])
        + percent_rank(latest["fcf_yield"])
        - percent_rank(latest["debt_to_assets"])
    )


# ---------------------------------------------------------------------------
# Low Volatility
# ---------------------------------------------------------------------------


def _trailing_log_return_vol(
    wide_prices: pd.DataFrame, window: int
) -> pd.Series:
    """Annualized stdev of daily log returns over the trailing ``window`` days."""

    if window <= 1:
        raise FactorInputError("low_vol window must be > 1")
    log_returns = np.log(wide_prices).diff()
    rolling_std = log_returns.rolling(window=window, min_periods=window).std()
    if rolling_std.empty:
        return pd.Series(dtype=float)
    return rolling_std.iloc[-1] * np.sqrt(TRADING_DAYS_PER_YEAR)


def low_vol_score(
    prices: pd.DataFrame,
    as_of: date,
    windows: tuple[int, ...] = DEFAULT_LOW_VOL_WINDOWS,
) -> pd.Series:
    """Average percent-rank of ``1/vol`` across the supplied trailing windows.

    Higher score == lower realized volatility. Tickers with insufficient
    history for *any* window return NaN; tickers with enough history for at
    least one window are averaged across whichever windows produced a value.
    """

    if not windows:
        raise FactorInputError("low_vol_score requires at least one window")
    wide = _wide_adjusted_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=float)
    inv_vol_ranks: list[pd.Series] = []
    for window in windows:
        vol = _trailing_log_return_vol(wide, window)
        inv_vol = safe_inverse(vol)
        inv_vol_ranks.append(percent_rank(inv_vol))
    return average_ranks(*inv_vol_ranks)


# ---------------------------------------------------------------------------
# Value
# ---------------------------------------------------------------------------


def value_score(fundamentals: pd.DataFrame, as_of: date) -> pd.Series:
    """Value composite: average percent-rank of five yield-style metrics.

    ``avg(rank(1/pe), rank(1/pb), rank(1/ev_ebitda), rank(fcf_yield), rank(earnings_yield))``
    per spec §F002. Non-positive denominators on the inverse-ratio components
    become NaN and are skipped by the averaging.
    """

    latest = _latest_fundamentals_row_per_ticker(fundamentals, as_of)
    if latest.empty:
        return pd.Series(dtype=float)
    return average_ranks(
        percent_rank(safe_inverse(latest["pe"])),
        percent_rank(safe_inverse(latest["pb"])),
        percent_rank(safe_inverse(latest["ev_ebitda"])),
        percent_rank(latest["fcf_yield"]),
        percent_rank(latest["earnings_yield"]),
    )


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------


def trend_score(
    prices: pd.DataFrame,
    as_of: date,
    ma_short: int = DEFAULT_MA_SHORT,
    ma_long: int = DEFAULT_MA_LONG,
    slope_window: int = DEFAULT_TREND_SLOPE_WINDOW,
) -> pd.Series:
    """Three-condition trend filter with slope-rank interpolation for the middle band.

    Hard outputs:
      - all three of ``close > MA_long``, ``MA_short > MA_long``, and
        ``MA_long_slope > 0`` met  → ``1.0``
      - all three failed                                  → ``0.0``

    Partial pass / fail (1 or 2 of 3 conditions met) is interpolated to
    ``[0.0, 1.0]`` via the percent-rank of ``MA_long`` slope, so a borderline
    ticker with a stronger underlying slope receives a higher score.
    """

    if ma_short <= 0 or ma_long <= 0 or slope_window <= 0:
        raise FactorInputError("ma_short, ma_long, slope_window must all be > 0")
    if ma_short >= ma_long:
        raise FactorInputError("ma_short must be strictly less than ma_long")
    wide = _wide_adjusted_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=float)
    ma_short_series = wide.rolling(window=ma_short, min_periods=ma_short).mean()
    ma_long_series = wide.rolling(window=ma_long, min_periods=ma_long).mean()
    ma_long_slope_series = ma_long_series.diff(slope_window) / float(slope_window)

    if ma_long_series.empty:
        return pd.Series(dtype=float)

    latest_close = wide.iloc[-1]
    latest_ma_short = ma_short_series.iloc[-1]
    latest_ma_long = ma_long_series.iloc[-1]
    latest_slope = ma_long_slope_series.iloc[-1]

    cond_close = latest_close > latest_ma_long
    cond_short = latest_ma_short > latest_ma_long
    cond_slope = latest_slope > 0
    count = cond_close.astype(int) + cond_short.astype(int) + cond_slope.astype(int)

    slope_rank = percent_rank(latest_slope)
    score = pd.Series(np.nan, index=wide.columns, dtype=float)
    all_pass = count == 3
    all_fail = count == 0
    partial = ~all_pass & ~all_fail
    score[all_pass] = DEFAULT_PASS_SCORE
    score[all_fail] = DEFAULT_FAIL_SCORE
    score[partial] = slope_rank[partial]
    # Tickers missing MA inputs (NaN MA50/MA200/slope) remain NaN.
    insufficient_history = (
        latest_ma_long.isna() | latest_ma_short.isna() | latest_slope.isna()
    )
    score[insufficient_history] = np.nan
    return score
