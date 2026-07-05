#!/usr/bin/env python
"""B092 F002 — US concentrated momentum+quality "attack" backtest + walk-forward.

Research-only (touches NO strategy/production/Master code, NO data_root). Reads the
gitignored cache written by ``b092_us_universe_fetch``:
  * ``data/research/b092_us/unified_prices.csv``  (qfq daily, incl. SPY)
  * ``data/research/b092_us/fundamentals_annual.csv`` (SEC EDGAR PIT annual)

Strategy (priors chosen ONCE — no parameter tuning to the backtest):
  * Quality filter: using the latest annual SEC filing available as-of the
    rebalance (``filed <= t`` — point-in-time, no look-ahead), drop names with
    non-positive trailing earnings AND drop the bottom quartile by a quality
    composite = z(ROE) - z(debt/equity). Names lacking an available filing at t
    are not qualified that month.
  * Momentum: 6-month return skipping the most recent 1 month — window from
    ``t-7mo`` to ``t-1mo`` (standard 12-1-style, 6m variant). Rank the qualified
    pool by this and take the top 15.
  * Weight: equal-weight the 15. Rebalance MONTHLY (month-end signal dates).
  * Costs: turnover-based, 10 bps per unit of one-way turnover (a full 15-name
    swap = turnover 2.0 = 20 bps) — modest commission+slippage.

Baselines: (a) equal-weight the full ~100 universe, monthly; (b) buy-hold SPY.

Walk-forward: metrics are reported full-period AND split in-sample (first 60% of
rebalance periods) vs out-of-sample (last 40%). An edge that lives only in-sample
is overfit — the A-share sibling of this strategy (cn_attack) came back
OOS-negative (B070), so the OOS column is the one that matters.

Run:  workbench/backend/.venv/bin/python -m scripts.research.b092_us_attack_backtest
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_DATA_DIR = Path("data/research/b092_us")
_PRICES_CSV = _DATA_DIR / "unified_prices.csv"
_FUNDAMENTALS_CSV = _DATA_DIR / "fundamentals_annual.csv"

SPY_TICKER = "SPY"
TOP_N = 15
LOOKBACK_MONTHS = 6
SKIP_MONTHS = 1
QUALITY_DROP_QUANTILE = 0.25
COST_PER_TURNOVER = 0.0010  # 10 bps per unit one-way turnover
MONTHS_PER_YEAR = 12
MIN_WARMUP_MONTHS = LOOKBACK_MONTHS + SKIP_MONTHS + 1
IN_SAMPLE_FRACTION = 0.60
# DATA-QUALITY FLOOR (not a tuned parameter): akshare's free qfq US series has
# pervasive back-adjustment step-discontinuities before ~2017 (e.g. UNH shows a
# spurious +2800% month in 2013, MSFT swings wildly) — 200+ impossible monthly
# moves in 2010-2014 vs ~0/yr from 2017 on. The scored window is floored where
# the free data becomes trustworthy. A paid vendor (Tiingo etc.) would extend it.
START_DATE = pd.Timestamp("2017-01-01")
# Per-name single-month data-integrity guard. A megacap monthly return outside
# [-60%, +150%] is essentially always a residual data glitch (worst real COVID /
# 2022 megacap months are ~-40%; splits are qfq-adjusted) — such a name is dropped
# from that period's return so one bad tick cannot dominate. Bounds are wide
# enough that no legitimate move is excluded.
MIN_MONTH_RATIO = 0.40
MAX_MONTH_RATIO = 2.50


# ---------------------------------------------------------------------------
# Price helpers (pure)
# ---------------------------------------------------------------------------


SPIKE_UP_RATIO = 4.0  # a >4x single-day jump on a megacap is a data glitch, not a move
SPIKE_DOWN_RATIO = 0.25


def clean_price_spikes(prices: pd.DataFrame) -> pd.DataFrame:
    """Drop isolated round-trip price glitches from akshare qfq data.

    A row is a glitch iff its ratio to the previous row is > ``SPIKE_UP_RATIO``
    (or < ``SPIKE_DOWN_RATIO``) AND the next row reverts by the mirror ratio — a
    one-day spike that round-trips. Splits/dividends are already qfq-adjusted, so
    no legitimate daily move is this large for these mega/large-caps; leaving one
    in corrupts both returns and the momentum window (e.g. BLK's spurious +2740%
    Mar-2012 tick). Pure; per-ticker; only the single bad row is removed."""

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["ticker", "date"])
    keep_parts: list[pd.DataFrame] = []
    for _, grp in frame.groupby("ticker", sort=False):
        s = pd.to_numeric(grp["adj_close"], errors="coerce")
        r_prev = s / s.shift(1)
        r_next = s.shift(-1) / s
        spike_up = (r_prev > SPIKE_UP_RATIO) & (r_next < SPIKE_DOWN_RATIO)
        spike_dn = (r_prev < SPIKE_DOWN_RATIO) & (r_next > SPIKE_UP_RATIO)
        keep_parts.append(grp[~(spike_up | spike_dn).fillna(False)])
    return pd.concat(keep_parts, ignore_index=True)


def to_wide(prices: pd.DataFrame) -> pd.DataFrame:
    """Long price frame -> wide adj_close (index=datetime date, columns=ticker)."""

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return (
        frame.pivot_table(index="date", columns="ticker", values="adj_close", aggfunc="last")
        .sort_index()
    )


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Last available trading day of each calendar month present in ``index``."""

    ser = pd.Series(index, index=index)
    keys = ser.index.to_period("M")
    return [group.index.max() for _, group in ser.groupby(keys)]


def last_on_or_before(wide: pd.DataFrame, cutoff: pd.Timestamp) -> pd.Series:
    """Row of the last date <= cutoff (NaN series if none)."""

    eligible = wide.loc[wide.index <= cutoff]
    if eligible.empty:
        return pd.Series(np.nan, index=wide.columns, dtype=float)
    return eligible.iloc[-1]


def momentum_skip(
    wide: pd.DataFrame,
    t: pd.Timestamp,
    lookback_months: int = LOOKBACK_MONTHS,
    skip_months: int = SKIP_MONTHS,
) -> pd.Series:
    """6m-skip-1m momentum per ticker as-of ``t`` (uses only prices <= t-skip).

    Return = price(end) / price(start) - 1, end = t - skip_months,
    start = end - lookback_months. NaN when either anchor is missing / non-positive.
    Point-in-time: any price dated after ``end`` is irrelevant to the value."""

    end_cutoff = t - pd.DateOffset(months=skip_months)
    start_cutoff = end_cutoff - pd.DateOffset(months=lookback_months)
    end_p = last_on_or_before(wide, end_cutoff)
    start_p = last_on_or_before(wide, start_cutoff)
    start_safe = start_p.where(start_p > 0)
    return (end_p / start_safe) - 1.0


# ---------------------------------------------------------------------------
# Quality helpers (pure, point-in-time)
# ---------------------------------------------------------------------------


def quality_asof(fundamentals: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Latest annual filing available as-of ``t`` (filed <= t) per ticker.

    Returns a ticker-indexed frame with columns roe, debt_to_equity, net_income.
    Point-in-time: rows filed after ``t`` are invisible (no look-ahead)."""

    if fundamentals.empty:
        return pd.DataFrame(columns=["roe", "debt_to_equity", "net_income"])
    frame = fundamentals.copy()
    frame["filed"] = pd.to_datetime(frame["filed"])
    frame["period_end"] = pd.to_datetime(frame["period_end"])
    visible = frame[frame["filed"] <= t]
    if visible.empty:
        return pd.DataFrame(columns=["roe", "debt_to_equity", "net_income"])
    ordered = visible.sort_values(["ticker", "period_end"])
    latest = ordered.groupby("ticker", as_index=False).tail(1).set_index("ticker")
    return latest[["roe", "debt_to_equity", "net_income"]].apply(pd.to_numeric, errors="coerce")


def qualified_tickers(
    quality: pd.DataFrame, drop_quantile: float = QUALITY_DROP_QUANTILE
) -> set[str]:
    """Names that pass the quality filter: positive earnings, not bottom-quartile.

    Composite = z(roe) - z(debt_to_equity) over names with usable data. Names in
    the bottom ``drop_quantile`` of the composite, or with non-positive earnings,
    or missing ROE, are dropped."""

    if quality.empty:
        return set()
    q = quality.copy()
    q = q[q["net_income"] > 0]
    q = q[q["roe"].notna()]
    if q.empty:
        return set()

    def z(col: pd.Series) -> pd.Series:
        std = col.std(ddof=0)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=col.index)
        return (col - col.mean()) / std

    dte = q["debt_to_equity"].fillna(q["debt_to_equity"].median())
    composite = z(q["roe"]) - z(dte)
    cutoff = composite.quantile(drop_quantile)
    kept = composite[composite > cutoff]
    return set(kept.index.astype(str))


def select_top(momentum: pd.Series, candidates: set[str], n: int = TOP_N) -> list[str]:
    """Top-``n`` tickers by momentum among ``candidates`` with non-NaN momentum."""

    elig = momentum[[c for c in momentum.index if c in candidates]].dropna()
    return list(elig.sort_values(ascending=False).head(n).index.astype(str))


def equal_weight(tickers: list[str]) -> dict[str, float]:
    """Equal-weight dict over ``tickers`` (empty -> empty)."""

    if not tickers:
        return {}
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}


# ---------------------------------------------------------------------------
# Return / metrics helpers (pure)
# ---------------------------------------------------------------------------


def period_return(
    wide: pd.DataFrame, weights: dict[str, float], t0: pd.Timestamp, t1: pd.Timestamp
) -> float:
    """Weighted return from t0 to t1; names missing a t1 price are dropped + renormed."""

    if not weights:
        return 0.0
    p0 = last_on_or_before(wide, t0)
    p1 = last_on_or_before(wide, t1)
    contrib: list[tuple[str, float]] = []
    for tkr, w in weights.items():
        a, b = p0.get(tkr, np.nan), p1.get(tkr, np.nan)
        if pd.notna(a) and pd.notna(b) and a > 0:
            ratio = b / a
            if ratio < MIN_MONTH_RATIO or ratio > MAX_MONTH_RATIO:
                continue  # data-integrity guard — drop implausible single-month move
            contrib.append((tkr, w * (ratio - 1.0)))
    if not contrib:
        return 0.0
    total_w = sum(weights[t] for t, _ in contrib)
    if total_w == 0:
        return 0.0
    return sum(r for _, r in contrib) / total_w


def turnover(prev: dict[str, float], new: dict[str, float]) -> float:
    """One-way turnover = sum |w_new - w_prev| over the union of holdings."""

    names = set(prev) | set(new)
    return float(sum(abs(new.get(n, 0.0) - prev.get(n, 0.0)) for n in names))


def cagr(returns: list[float], dates: list[pd.Timestamp]) -> float:
    if len(returns) < 1 or len(dates) < 2:
        return float("nan")
    growth = float(np.prod([1.0 + r for r in returns]))
    years = (dates[-1] - dates[0]).days / 365.25
    if years <= 0 or growth <= 0:
        return float("nan")
    return growth ** (1.0 / years) - 1.0


def sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return float("nan")
    arr = np.asarray(returns, dtype=float)
    sd = arr.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(arr.mean() / sd * np.sqrt(MONTHS_PER_YEAR))


def max_drawdown(returns: list[float]) -> float:
    if not returns:
        return float("nan")
    equity = np.cumprod([1.0 + r for r in returns])
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def summarize(returns: list[float], dates: list[pd.Timestamp]) -> dict[str, float]:
    return {
        "cagr": cagr(returns, dates),
        "sharpe": sharpe(returns),
        "max_drawdown": max_drawdown(returns),
        "n_periods": len(returns),
    }


# ---------------------------------------------------------------------------
# Backtest driver
# ---------------------------------------------------------------------------


def run_backtest(
    prices: pd.DataFrame, fundamentals: pd.DataFrame
) -> tuple[list[pd.Timestamp], dict[str, list[float]], dict[str, int]]:
    """Return (rebalance_end_dates, {series_name: monthly_returns}, diagnostics)."""

    wide = to_wide(clean_price_spikes(prices))
    universe = [c for c in wide.columns if c != SPY_TICKER]
    uni_wide = wide[universe]
    signal_dates = month_end_dates(wide.index)

    # Warm-up floor: need lookback+skip months of history before first signal.
    first = signal_dates[0]
    warm_floor = max(first + pd.DateOffset(months=MIN_WARMUP_MONTHS), START_DATE)
    signal_dates = [d for d in signal_dates if d >= warm_floor]

    strat_r: list[float] = []
    ew_r: list[float] = []
    spy_r: list[float] = []
    dates: list[pd.Timestamp] = []
    prev_weights: dict[str, float] = {}
    n_qualified_hist: list[int] = []
    n_selected_hist: list[int] = []

    for t, t_next in zip(signal_dates[:-1], signal_dates[1:], strict=True):
        mom = momentum_skip(uni_wide, t)
        quality = quality_asof(fundamentals, t)
        qualified = qualified_tickers(quality)
        n_qualified_hist.append(len(qualified))
        selected = select_top(mom, qualified, TOP_N)
        n_selected_hist.append(len(selected))
        weights = equal_weight(selected)

        gross = period_return(uni_wide, weights, t, t_next)
        cost = turnover(prev_weights, weights) * COST_PER_TURNOVER
        strat_r.append(gross - cost)
        prev_weights = weights

        # Baseline (a): equal-weight full universe with a t & t_next price.
        p0 = last_on_or_before(uni_wide, t)
        alive = [c for c in universe if pd.notna(p0.get(c, np.nan)) and p0.get(c) > 0]
        ew_r.append(period_return(uni_wide, equal_weight(alive), t, t_next))

        # Baseline (b): buy-hold SPY.
        spy_r.append(period_return(wide[[SPY_TICKER]], {SPY_TICKER: 1.0}, t, t_next))

        dates.append(t_next)

    diagnostics = {
        "n_signal_periods": len(strat_r),
        "median_qualified": int(np.median(n_qualified_hist)) if n_qualified_hist else 0,
        "median_selected": int(np.median(n_selected_hist)) if n_selected_hist else 0,
        "min_selected": int(np.min(n_selected_hist)) if n_selected_hist else 0,
        "n_universe": len(universe),
    }
    return dates, {"strategy": strat_r, "equal_weight": ew_r, "spy": spy_r}, diagnostics


def _segment(returns: list[float], dates: list[pd.Timestamp], lo: int, hi: int) -> dict[str, float]:
    return summarize(returns[lo:hi], dates[lo:hi])


def main() -> int:
    if not _PRICES_CSV.is_file():
        print(f"ERROR: {_PRICES_CSV} missing — run b092_us_universe_fetch first.")
        return 1
    prices = pd.read_csv(_PRICES_CSV, dtype={"ticker": str})
    fundamentals = (
        pd.read_csv(_FUNDAMENTALS_CSV, dtype={"ticker": str})
        if _FUNDAMENTALS_CSV.is_file()
        else pd.DataFrame()
    )
    print(f"prices: {len(prices)} rows, {prices['ticker'].nunique()} tickers")
    print(f"fundamentals: {len(fundamentals)} rows, "
          f"{fundamentals['ticker'].nunique() if not fundamentals.empty else 0} tickers")

    dates, series, diag = run_backtest(prices, fundamentals)
    print(f"\ndiagnostics: {diag}")

    n = len(dates)
    split = int(n * IN_SAMPLE_FRACTION)
    print(f"\nwindow: {dates[0].date()} .. {dates[-1].date()}  ({n} monthly periods)")
    print(f"in-sample: first {split} periods ({dates[0].date()} .. {dates[split - 1].date()})")
    print(f"out-of-sample: last {n - split} periods ({dates[split].date()} .. {dates[-1].date()})")

    print(f"\n{'':16s}{'CAGR':>10s}{'Sharpe':>9s}{'MaxDD':>9s}")
    for label, key in (("STRATEGY", "strategy"), ("EqualWeight", "equal_weight"), ("SPY", "spy")):
        for seg_name, lo, hi in (("full", 0, n), ("in-samp", 0, split), ("oos", split, n)):
            m = _segment(series[key], dates, lo, hi)
            print(f"{label + '/' + seg_name:16s}"
                  f"{m['cagr'] * 100:9.2f}%{m['sharpe']:9.2f}{m['max_drawdown'] * 100:8.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
