#!/usr/bin/env python
"""Independent A-share multiscale price-volume trend first-look.

This evaluator-only runner tests the published Liu-Zhou-Zhu trend measure on
the B070 point-in-time A-share universe.  It does not modify or call the frozen
CN attack portfolio engine.  The signal uses nine price moving-average ratios,
nine traded-value moving-average ratios, monthly cross-sectional OLS, and the
paper's lambda=0.02 online coefficient forecast.  Parameters are frozen before
the real-data run and no grid search is performed.

The primary target is the return from the first tradeable open after a month-end
signal to the N20 tradeable close.  N60 is confirmation.  Classic 12-1 momentum
is evaluated on the identical PIT cross-section and execution labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_PATH = REPO_ROOT / "data" / "research" / "b070" / "b081_prices_cache.pkl"
UNIVERSE_PATH = (
    REPO_ROOT
    / "data"
    / "research"
    / "b070"
    / "snapshots"
    / "universe"
    / "cn_pit_universe.csv"
)
SIZE_PATH = REPO_ROOT / "data" / "research" / "b076" / "cn_size.csv"
DEFAULT_OUT = (
    REPO_ROOT
    / "docs"
    / "test-reports"
    / "ashare-multiscale-pv-trend-first-look-2026-07-11.json"
)

PAPER_DOI = "https://doi.org/10.1093/rapstu/raae003"
PAPER_WORKING_COPY = (
    "https://acfr.aut.ac.nz/__data/assets/pdf_file/0014/324113/"
    "Y-Liu-New-TrendChina_12_1_WithAppendix.pdf"
)
MA_LAGS = (3, 5, 10, 20, 50, 100, 200, 300, 400)
EMA_LAMBDA = 0.02
COEFFICIENT_BURN_IN = 38
MIN_REGRESSION_CROSS_SECTION = 100
MIN_IC_CROSS_SECTION = 100
MIN_VALID_MONTHS = 36
HORIZONS = (1, 20, 60)
BOOTSTRAP_SAMPLES = 5_000
BOOTSTRAP_BLOCK_MONTHS = 6
BOOTSTRAP_SEED = 20260711


@dataclass(frozen=True, slots=True)
class UniverseSchedule:
    dates: pd.DatetimeIndex
    members: tuple[frozenset[str], ...]

    def members_on(self, timestamp: pd.Timestamp) -> frozenset[str]:
        position = int(self.dates.searchsorted(pd.Timestamp(timestamp), side="right")) - 1
        return self.members[position] if position >= 0 else frozenset()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_universe_schedule(path: Path = UNIVERSE_PATH) -> tuple[pd.DataFrame, UniverseSchedule]:
    if not path.is_file():
        raise FileNotFoundError(f"PIT universe missing: {path}")
    universe = pd.read_csv(path, dtype={"ticker": str})
    required = {"as_of_date", "ticker"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"PIT universe missing columns: {sorted(missing)}")
    universe["as_of_date"] = pd.to_datetime(universe["as_of_date"], errors="raise")
    universe["ticker"] = universe["ticker"].str.upper()
    grouped = universe.groupby("as_of_date", sort=True)["ticker"].agg(
        lambda values: frozenset(values)
    )
    return universe, UniverseSchedule(
        dates=pd.DatetimeIndex(grouped.index),
        members=tuple(grouped.tolist()),
    )


def _complete_month_end_dates(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last observed market date per complete month.

    The terminal observed month is always excluded because the local snapshot
    has no exchange calendar marker proving that month is complete.  Its daily
    bars remain available as forward-return labels for the prior signal.  This
    conservative rule may discard one complete terminal month but cannot admit
    a partially observed month as a coefficient or signal month.
    """

    ordered = pd.DatetimeIndex(pd.to_datetime(dates).unique()).sort_values()
    if ordered.empty:
        return ordered
    grouped = pd.Series(ordered, index=ordered.to_period("M")).groupby(level=0).max()
    grouped = grouped.iloc[:-1]
    return pd.DatetimeIndex(grouped.to_numpy())


def _load_price_panels(
    path: Path = PRICE_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not path.is_file():
        raise FileNotFoundError(f"B070 price cache missing: {path}")
    frame = pd.read_pickle(path)  # noqa: S301 - trusted local research cache
    required = {
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "tradestatus",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"B070 price cache missing columns: {sorted(missing)}")
    frame = frame[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    if frame.duplicated(["date", "ticker"]).any():
        raise ValueError("B070 price cache has duplicate date/ticker rows")
    frame = frame.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    close = frame.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    volume = frame.pivot(index="date", columns="ticker", values="volume").reindex(close.index)
    status = frame.pivot(index="date", columns="ticker", values="tradestatus").reindex(close.index)
    return frame, close, volume, status


def build_feature_frames(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    status: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
    *,
    volume_mode: str = "amount_proxy",
    lags: tuple[int, ...] = MA_LAGS,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Build the paper's normalized MA features at each market month-end.

    The paper uses RMB traded value.  B070 stores share volume and qfq close, so
    the primary input is the explicit proxy ``qfq_close * share_volume``.  A
    share-volume-only rerun is reported as a fixed sensitivity, never selected
    after observing results.
    """

    if volume_mode not in {"amount_proxy", "share_volume"}:
        raise ValueError("volume_mode must be amount_proxy or share_volume")
    if not close.index.equals(volume.index) or not close.index.equals(status.index):
        raise ValueError("price, volume, and status panels must share an index")
    if not close.columns.equals(volume.columns) or not close.columns.equals(status.columns):
        raise ValueError("price, volume, and status panels must share columns")

    month_ends = pd.DatetimeIndex(month_ends)
    if month_ends.empty:
        return {}, {
            "volume_mode": volume_mode,
            "lags": list(lags),
            "feature_coverage_all_panel_cells": {},
        }
    # Enforce the as-of boundary even when a unit test or future caller supplies
    # an intra-month signal date rather than the normal completed month-end.
    last_signal_date = pd.Timestamp(month_ends.max())
    close = close.loc[close.index <= last_signal_date]
    volume = volume.loc[volume.index <= last_signal_date]
    status = status.loc[status.index <= last_signal_date]
    monthly_close = close.reindex(month_ends)
    observed = close.notna() & status.notna()
    metric = close * volume if volume_mode == "amount_proxy" else volume.copy()
    tradeable = status.eq(1) & close.gt(0) & metric.gt(0)
    metric_with_zeros = metric.where(tradeable, 0.0).where(observed)
    trade_count_daily = tradeable.astype(float).where(observed)
    periods = close.index.to_period("M")
    target_periods = month_ends.to_period("M")
    current_metric = metric.where(tradeable).groupby(periods).last().reindex(target_periods)
    current_metric.index = month_ends
    current_month_trades = tradeable.astype(int).groupby(periods).sum().reindex(target_periods)
    current_month_trades.index = month_ends

    features: dict[str, pd.DataFrame] = {}
    coverage: dict[str, dict[str, float | int]] = {}
    for lag in lags:
        price_feature = close.rolling(lag, min_periods=lag).mean().reindex(month_ends)
        price_feature = price_feature / monthly_close.where(monthly_close.gt(0))
        price_feature = price_feature.where(np.isfinite(price_feature))

        volume_mean = (
            metric_with_zeros.rolling(lag, min_periods=lag).sum().reindex(month_ends) / lag
        )
        trade_count = trade_count_daily.rolling(lag, min_periods=lag).sum().reindex(month_ends)
        volume_feature = volume_mean / current_metric.where(current_metric.gt(0))
        valid_volume = trade_count.gt(lag / 2.0) & current_month_trades.gt(0)
        volume_feature = volume_feature.where(valid_volume)
        # The paper carries the prior month's volume signal when the current
        # month has insufficient trading records.  Do not carry past a delist.
        volume_feature = volume_feature.ffill().where(monthly_close.notna())
        volume_feature = volume_feature.where(np.isfinite(volume_feature))

        p_name = f"p{lag:03d}"
        v_name = f"v{lag:03d}"
        features[p_name] = price_feature
        features[v_name] = volume_feature
        coverage[p_name] = {
            "finite": int(np.isfinite(price_feature.to_numpy()).sum()),
            "total": int(price_feature.size),
            "fraction": float(np.isfinite(price_feature.to_numpy()).mean()),
        }
        coverage[v_name] = {
            "finite": int(np.isfinite(volume_feature.to_numpy()).sum()),
            "total": int(volume_feature.size),
            "fraction": float(np.isfinite(volume_feature.to_numpy()).mean()),
        }
    return features, {
        "volume_mode": volume_mode,
        "lags": list(lags),
        "feature_coverage_all_panel_cells": coverage,
    }


def raw_momentum_12_1(monthly_close: pd.DataFrame) -> pd.DataFrame:
    """Classic month-end 12-1 momentum: close[t-1] / close[t-13] - 1."""

    return monthly_close.shift(1) / monthly_close.shift(13) - 1.0


def _feature_matrix(
    features: Mapping[str, pd.DataFrame],
    feature_order: tuple[str, ...],
    timestamp: pd.Timestamp,
    tickers: list[str],
) -> np.ndarray:
    return np.column_stack(
        [
            features[name].loc[timestamp].reindex(tickers).to_numpy(dtype=float)
            for name in feature_order
        ]
    )


def estimate_online_trend(
    features: Mapping[str, pd.DataFrame],
    monthly_close: pd.DataFrame,
    schedule: UniverseSchedule,
    *,
    burn_in: int = COEFFICIENT_BURN_IN,
    ema_lambda: float = EMA_LAMBDA,
    min_cross_section: int = MIN_REGRESSION_CROSS_SECTION,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Estimate monthly OLS coefficients and emit strictly real-time trend scores."""

    if not 0 < ema_lambda <= 1:
        raise ValueError("ema_lambda must be in (0, 1]")
    if burn_in < 1:
        raise ValueError("burn_in must be >= 1")
    feature_order = tuple(
        sorted(features, key=lambda name: (0 if name.startswith("p") else 1, int(name[1:])))
    )
    if not feature_order or not any(name.startswith("p") for name in feature_order):
        raise ValueError("at least one price feature is required")
    dates = pd.DatetimeIndex(monthly_close.index)
    monthly_returns = monthly_close / monthly_close.shift(1) - 1.0
    raw_momentum = raw_momentum_12_1(monthly_close)
    expected_beta: np.ndarray | None = None
    coefficient_months = 0
    signals: list[dict[str, Any]] = []
    fits: list[dict[str, Any]] = []
    signal_coverage: list[dict[str, Any]] = []

    for offset in range(1, len(dates)):
        previous_date = pd.Timestamp(dates[offset - 1])
        current_date = pd.Timestamp(dates[offset])
        regression_members = sorted(schedule.members_on(previous_date))
        if not regression_members:
            continue
        x_previous = _feature_matrix(features, feature_order, previous_date, regression_members)
        y_current = monthly_returns.loc[current_date].reindex(regression_members).to_numpy(float)
        valid_fit = np.isfinite(y_current) & np.isfinite(x_previous).all(axis=1)
        if int(valid_fit.sum()) < min_cross_section:
            continue
        design = np.column_stack([np.ones(int(valid_fit.sum())), x_previous[valid_fit]])
        coefficients, _, rank, singular_values = np.linalg.lstsq(
            design, y_current[valid_fit], rcond=None
        )
        beta = coefficients[1:]
        expected_beta = (
            beta.copy()
            if expected_beta is None
            else (1.0 - ema_lambda) * expected_beta + ema_lambda * beta
        )
        coefficient_months += 1
        condition = (
            float(singular_values[0] / singular_values[-1])
            if len(singular_values) and singular_values[-1] > 0
            else math.inf
        )
        fits.append(
            {
                "month": current_date,
                "n": int(valid_fit.sum()),
                "rank": int(rank),
                "condition_number": condition,
                "beta_l2": float(np.linalg.norm(beta)),
            }
        )
        if coefficient_months < burn_in:
            continue

        signal_members = sorted(schedule.members_on(current_date))
        if not signal_members:
            continue
        x_current = _feature_matrix(features, feature_order, current_date, signal_members)
        valid_signal = np.isfinite(x_current).all(axis=1)
        valid_tickers = np.asarray(signal_members, dtype=object)[valid_signal]
        valid_x = x_current[valid_signal]
        scores = valid_x @ expected_beta
        price_positions = np.array([name.startswith("p") for name in feature_order])
        price_scores = valid_x[:, price_positions] @ expected_beta[price_positions]
        volume_scores = valid_x[:, ~price_positions] @ expected_beta[~price_positions]
        raw_row = raw_momentum.loc[current_date].reindex(valid_tickers).to_numpy(float)
        signal_coverage.append(
            {
                "month": current_date,
                "universe_n": len(signal_members),
                "signal_n": int(valid_signal.sum()),
                "coverage": float(valid_signal.mean()) if valid_signal.size else 0.0,
            }
        )
        for ticker, score, p_score, v_score, raw_score in zip(
            valid_tickers,
            scores,
            price_scores,
            volume_scores,
            raw_row,
            strict=True,
        ):
            signals.append(
                {
                    "signal_date": current_date,
                    "ticker": str(ticker),
                    "trend_pv": float(score),
                    "trend_price_component": float(p_score),
                    "trend_volume_component": float(v_score),
                    "raw_momentum_12_1": float(raw_score) if np.isfinite(raw_score) else np.nan,
                }
            )

    fit_frame = pd.DataFrame(fits)
    coverage_frame = pd.DataFrame(signal_coverage)
    diagnostics = {
        "feature_order": list(feature_order),
        "coefficient_months": coefficient_months,
        "burn_in": burn_in,
        "first_fit_month": fit_frame["month"].min() if len(fit_frame) else None,
        "last_fit_month": fit_frame["month"].max() if len(fit_frame) else None,
        "fit_cross_section": _distribution(
            fit_frame["n"] if len(fit_frame) else pd.Series(dtype=float)
        ),
        "design_rank_min": int(fit_frame["rank"].min()) if len(fit_frame) else None,
        "design_columns": len(feature_order) + 1,
        "condition_number": _distribution(
            fit_frame["condition_number"] if len(fit_frame) else pd.Series(dtype=float)
        ),
        "signal_months": int(len(coverage_frame)),
        "signal_start": coverage_frame["month"].min() if len(coverage_frame) else None,
        "signal_end": coverage_frame["month"].max() if len(coverage_frame) else None,
        "pit_signal_coverage": _distribution(
            coverage_frame["coverage"] if len(coverage_frame) else pd.Series(dtype=float)
        ),
        "coverage_by_month": coverage_frame.to_dict("records"),
    }
    return pd.DataFrame(signals), diagnostics


def _distribution(values: pd.Series | np.ndarray) -> dict[str, float | int | None]:
    sample = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if sample.empty:
        return {"n": 0, "min": None, "p10": None, "median": None, "max": None}
    return {
        "n": int(len(sample)),
        "min": float(sample.min()),
        "p10": float(sample.quantile(0.10)),
        "median": float(sample.median()),
        "max": float(sample.max()),
    }


def _limit_band(ticker: str, entry_date: pd.Timestamp) -> float:
    code = ticker[:6]
    if code.startswith("688"):
        return 0.20
    if code.startswith(("300", "301")) and entry_date >= pd.Timestamp("2020-08-24"):
        return 0.20
    return 0.10


def _size_histories(path: Path = SIZE_PATH) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    size = pd.read_csv(path, dtype={"ticker": str})
    size["data_date"] = pd.to_datetime(size["data_date"], errors="coerce")
    size["market_cap"] = pd.to_numeric(size["market_cap"], errors="coerce")
    size = size.dropna(subset=["data_date", "market_cap"])
    size["ticker"] = size["ticker"].str.upper()
    return {
        ticker: (
            group["data_date"].to_numpy(dtype="datetime64[ns]"),
            group["market_cap"].to_numpy(float),
        )
        for ticker, group in size.sort_values("data_date").groupby("ticker", sort=False)
    }


def attach_forward_returns(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    size_path: Path = SIZE_PATH,
) -> pd.DataFrame:
    """Attach tradeable open-to-close labels without using frozen suspension bars."""

    signal_columns = [
        column for column in signals.columns if column not in {"signal_date", "ticker"}
    ]
    needed = ["date", "ticker", "open", "high", "low", "adj_close", "volume", "tradestatus"]
    panel = prices[needed].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    histories: dict[str, dict[str, np.ndarray]] = {}
    for ticker, group in panel.groupby("ticker", sort=False):
        ordered = group.sort_values("date")
        histories[ticker] = {
            "date": ordered["date"].to_numpy(dtype="datetime64[ns]"),
            "open": ordered["open"].to_numpy(float),
            "high": ordered["high"].to_numpy(float),
            "low": ordered["low"].to_numpy(float),
            "close": ordered["adj_close"].to_numpy(float),
            "volume": ordered["volume"].to_numpy(float),
            "status": ordered["tradestatus"].to_numpy(int),
        }
    size_histories = _size_histories(size_path)
    market_dates = pd.DatetimeIndex(panel["date"].drop_duplicates().sort_values())
    market_positions = {np.datetime64(day): position for position, day in enumerate(market_dates)}

    rows: list[dict[str, Any]] = []
    for event in signals.itertuples(index=False):
        ticker = str(event.ticker)
        history = histories.get(ticker)
        if history is None:
            continue
        dates = history["date"]
        position = int(np.searchsorted(dates, np.datetime64(event.signal_date), side="right"))
        while position < len(dates):
            if (
                history["status"][position] == 1
                and np.isfinite(history["open"][position])
                and history["open"][position] > 0
                and np.isfinite(history["close"][position])
                and history["close"][position] > 0
            ):
                break
            position += 1
        if position >= len(dates):
            continue
        previous_position = position - 1
        while previous_position >= 0 and not (
            np.isfinite(history["close"][previous_position])
            and history["close"][previous_position] > 0
        ):
            previous_position -= 1
        previous_close = (
            float(history["close"][previous_position]) if previous_position >= 0 else np.nan
        )
        entry_open = float(history["open"][position])
        opening_return = entry_open / previous_close - 1.0 if previous_close > 0 else np.nan
        entry_date = pd.Timestamp(dates[position])
        first_market_position = int(
            market_dates.searchsorted(pd.Timestamp(event.signal_date), side="right")
        )
        entry_market_position = market_positions.get(
            np.datetime64(entry_date), first_market_position
        )
        record: dict[str, Any] = {
            "signal_date": pd.Timestamp(event.signal_date),
            "ticker": ticker,
            "entry_date": entry_date,
            "entry_delay_market_sessions": int(entry_market_position - first_market_position),
            "entry_open_return": opening_return,
            "limit_up": bool(
                np.isfinite(opening_return)
                and opening_return >= _limit_band(ticker, entry_date) - 1e-6
            ),
        }
        for column in signal_columns:
            record[column] = getattr(event, column)
        record["pre20_return"] = (
            previous_close / float(history["close"][position - 21]) - 1.0
            if position >= 21
            and np.isfinite(history["close"][position - 21])
            and history["close"][position - 21] > 0
            else np.nan
        )
        recent = slice(max(0, position - 60), position)
        recent_close = history["close"][recent]
        recent_returns = pd.Series(recent_close).pct_change().replace([np.inf, -np.inf], np.nan)
        record["pre60_volatility"] = (
            float(recent_returns.std(ddof=1) * math.sqrt(252))
            if recent_returns.notna().sum() >= 40
            else np.nan
        )
        recent_amount = history["close"][max(0, position - 20) : position] * history["volume"][
            max(0, position - 20) : position
        ]
        finite_recent_amount = recent_amount[np.isfinite(recent_amount)]
        record["pre20_median_amount_proxy"] = (
            float(np.median(finite_recent_amount)) if len(finite_recent_amount) else np.nan
        )
        size_history = size_histories.get(ticker)
        if size_history is None:
            record["pit_market_cap"] = np.nan
        else:
            size_dates, size_values = size_history
            size_position = int(
                np.searchsorted(size_dates, np.datetime64(event.signal_date), side="right")
            ) - 1
            record["pit_market_cap"] = (
                float(size_values[size_position]) if size_position >= 0 else np.nan
            )
        for horizon in HORIZONS:
            # A shares bought today cannot be sold the same day.  N1 is the
            # earliest legal T+1 close; longer horizons retain the preregistered
            # entry-inclusive session count (N20 -> position + 19).
            target = position + 1 if horizon == 1 else position + horizon - 1
            exit_position = target
            while exit_position < len(dates):
                if (
                    history["status"][exit_position] == 1
                    and np.isfinite(history["close"][exit_position])
                    and history["close"][exit_position] > 0
                ):
                    break
                exit_position += 1
            if exit_position < len(dates):
                record[f"ret_{horizon}"] = (
                    float(history["close"][exit_position]) / entry_open - 1.0
                )
                record[f"exit_delay_{horizon}"] = int(exit_position - target)
            else:
                record[f"ret_{horizon}"] = np.nan
                record[f"exit_delay_{horizon}"] = np.nan
        rows.append(record)
    return pd.DataFrame(rows)


def _monthly_ic(events: pd.DataFrame, signal: str, return_column: str) -> pd.DataFrame:
    frame = events.dropna(subset=[signal, return_column]).copy()
    rows: list[dict[str, Any]] = []
    for month, cohort in frame.groupby("signal_date", sort=True):
        if len(cohort) < MIN_IC_CROSS_SECTION:
            continue
        signal_rank = cohort[signal].rank(method="average")
        return_rank = cohort[return_column].rank(method="average")
        if signal_rank.nunique() < 2 or return_rank.nunique() < 2:
            continue
        ic = float(signal_rank.corr(return_rank))
        if not math.isfinite(ic):
            continue
        rows.append(
            {
                "month": pd.Timestamp(month),
                "ic": ic,
                "n": int(len(cohort)),
            }
        )
    return pd.DataFrame(rows)


def _hac_mean(values: np.ndarray, lags: int = 3) -> dict[str, float | None]:
    sample = np.asarray(values, dtype=float)
    sample = sample[np.isfinite(sample)]
    if len(sample) < 2:
        return {"mean": None, "se": None, "t": None}
    centered = sample - sample.mean()
    gamma0 = float(np.dot(centered, centered) / len(sample))
    long_run = gamma0
    for lag in range(1, min(lags, len(sample) - 1) + 1):
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / len(sample))
        long_run += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    se = math.sqrt(max(long_run, 0.0) / len(sample))
    return {
        "mean": float(sample.mean()),
        "se": float(se),
        "t": float(sample.mean() / se) if se > 0 else None,
    }


def _block_bootstrap(values: np.ndarray) -> dict[str, float]:
    sample = np.asarray(values, dtype=float)
    sample = sample[np.isfinite(sample)]
    if len(sample) < BOOTSTRAP_BLOCK_MONTHS:
        return {"ci_low": np.nan, "ci_high": np.nan, "prob_positive": np.nan}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(len(sample))
    means = np.empty(BOOTSTRAP_SAMPLES)
    for iteration in range(BOOTSTRAP_SAMPLES):
        selected: list[float] = []
        while len(selected) < len(sample):
            start = int(rng.choice(starts))
            selected.extend(
                sample[(start + offset) % len(sample)]
                for offset in range(BOOTSTRAP_BLOCK_MONTHS)
            )
        means[iteration] = float(np.mean(selected[: len(sample)]))
    return {
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
        "prob_positive": float(np.mean(means > 0)),
    }


def _folds(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    if monthly.empty:
        return []
    rows: list[dict[str, Any]] = []
    for number, positions in enumerate(np.array_split(np.arange(len(monthly)), 3), start=1):
        fold = monthly.iloc[positions]
        rows.append(
            {
                "fold": number,
                "start": fold["month"].min(),
                "end": fold["month"].max(),
                "months": int(len(fold)),
                "mean_ic": float(fold["ic"].mean()),
            }
        )
    return rows


def _years(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    if monthly.empty:
        return []
    return [
        {"year": int(year), "months": int(len(group)), "mean_ic": float(group["ic"].mean())}
        for year, group in monthly.assign(year=monthly["month"].dt.year).groupby(
            "year", sort=True
        )
    ]


def _quintiles(
    events: pd.DataFrame,
    signal: str,
    return_column: str,
    *,
    cash_on_limit_up: bool = True,
) -> dict[str, Any]:
    """Freeze signal-date quintiles before applying the entry executability veto.

    A selected name that opens limit-up is not replaced by the next-ranked name;
    its return is zero (cash) for the long-only top-leg diagnostic.  This avoids
    ex-post re-ranking on an execution outcome known only after signal formation.
    """

    month_rows: list[dict[str, float]] = []
    for month, cohort in events.dropna(subset=[signal, return_column]).groupby(
        "signal_date", sort=True
    ):
        if len(cohort) < MIN_IC_CROSS_SECTION:
            continue
        ranks = cohort[signal].rank(method="average", pct=True)
        ranked = cohort.assign(quintile=np.ceil(ranks * 5).clip(1, 5).astype(int))
        effective_column = return_column
        if cash_on_limit_up and "limit_up" in ranked:
            effective_column = "_effective_return"
            ranked[effective_column] = ranked[return_column].where(~ranked["limit_up"], 0.0)
        means = ranked.groupby("quintile")[effective_column].mean().to_dict()
        if len(means) != 5:
            continue
        month_rows.append(
            {
                "month": pd.Timestamp(month),
                **{f"q{q}": float(means[q]) for q in range(1, 6)},
                "all": float(ranked[effective_column].mean()),
            }
        )
    if not month_rows:
        return {
            "months": 0,
            "means": {},
            "q5_minus_q1": None,
            "q5_minus_all": None,
            "monotonic_rank_corr": None,
            "q5_excess_hac": _hac_mean(np.array([])),
            "q5_excess_bootstrap": _block_bootstrap(np.array([])),
        }
    table = pd.DataFrame(month_rows)
    means = {str(q): float(table[f"q{q}"].mean()) for q in range(1, 6)}
    ordered = np.array([means[str(q)] for q in range(1, 6)], dtype=float)
    excess = (table["q5"] - table["all"]).to_numpy(float)
    return {
        "months": int(len(table)),
        "means": means,
        "q5_minus_q1": float(ordered[-1] - ordered[0]),
        "q5_minus_all": float(excess.mean()),
        "monotonic_rank_corr": float(
            pd.Series(range(1, 6), dtype=float).corr(pd.Series(ordered).rank())
        ),
        "q5_excess_hac": _hac_mean(excess),
        "q5_excess_bootstrap": _block_bootstrap(excess),
    }


def analyze_signal(events: pd.DataFrame, signal: str) -> dict[str, Any]:
    executable = events[~events["limit_up"]].copy()
    result: dict[str, Any] = {
        "signal": signal,
        "events": int(len(events)),
        "executable_events": int(len(executable)),
        "limit_up_fraction": float(events["limit_up"].mean()) if len(events) else None,
        "unique_tickers": int(executable["ticker"].nunique()),
        "horizons": {},
    }
    for horizon in HORIZONS:
        return_column = f"ret_{horizon}"
        monthly = _monthly_ic(events, signal, return_column)
        executable_monthly = _monthly_ic(executable, signal, return_column)
        values = monthly["ic"].to_numpy(float) if len(monthly) else np.array([])
        result["horizons"][f"N{horizon}"] = {
            "valid_events": int(events[[signal, return_column]].dropna().shape[0]),
            "valid_months": int(len(monthly)),
            "cross_section_observations": int(monthly["n"].sum()) if len(monthly) else 0,
            "hac": _hac_mean(values),
            "block_bootstrap": _block_bootstrap(values),
            "folds": _folds(monthly),
            "years": _years(monthly),
            "quintiles": _quintiles(events, signal, return_column),
            "executable_only_ic_sensitivity": {
                "valid_months": int(len(executable_monthly)),
                "hac": _hac_mean(
                    executable_monthly["ic"].to_numpy(float)
                    if len(executable_monthly)
                    else np.array([])
                ),
            },
            "monthly": monthly.to_dict("records"),
        }
    formation = _monthly_ic(events, signal, "pre20_return")
    result["formation_exposure"] = {
        "valid_months": int(len(formation)),
        "hac": _hac_mean(
            formation["ic"].to_numpy(float) if len(formation) else np.array([])
        ),
    }
    return result


def compare_monthly_ic(
    primary: dict[str, Any], baseline: dict[str, Any], *, horizon: str = "N20"
) -> dict[str, Any]:
    left = pd.DataFrame(primary["horizons"][horizon]["monthly"]).rename(
        columns={"ic": "primary_ic"}
    )
    right = pd.DataFrame(baseline["horizons"][horizon]["monthly"]).rename(
        columns={"ic": "baseline_ic"}
    )
    if left.empty or right.empty:
        return {
            "months": 0,
            "hac": _hac_mean(np.array([])),
            "block_bootstrap": _block_bootstrap(np.array([])),
            "excluding_2024q4_mean": None,
            "folds": [],
        }
    paired = left[["month", "primary_ic"]].merge(
        right[["month", "baseline_ic"]], on="month", how="inner", validate="one_to_one"
    )
    paired["month"] = pd.to_datetime(paired["month"])
    paired["ic"] = paired["primary_ic"] - paired["baseline_ic"]
    outside = paired[
        ~(
            paired["month"].dt.year.eq(2024)
            & paired["month"].dt.quarter.eq(4)
        )
    ]
    values = paired["ic"].to_numpy(float)
    return {
        "months": int(len(paired)),
        "hac": _hac_mean(values),
        "block_bootstrap": _block_bootstrap(values),
        "excluding_2024q4_mean": float(outside["ic"].mean()) if len(outside) else None,
        "q4_2024_mean": float(
            paired.loc[
                paired["month"].dt.year.eq(2024) & paired["month"].dt.quarter.eq(4), "ic"
            ].mean()
        ),
        "folds": _folds(paired[["month", "ic"]]),
        "monthly": paired.to_dict("records"),
    }


def analyze_delist_stress(
    events: pd.DataFrame, signal: str = "trend_pv"
) -> dict[str, Any]:
    """Worst-case sensitivity: path-ended/missing labels lose 100%, not silently drop.

    Right-censored observations remain missing because their investment outcome is
    genuinely not observed at the snapshot boundary.
    """

    result: dict[str, Any] = {}
    for horizon in (20, 60):
        column = f"ret_{horizon}_delist_stress"
        monthly = _monthly_ic(events, signal, column)
        values = monthly["ic"].to_numpy(float) if len(monthly) else np.array([])
        result[f"N{horizon}"] = {
            "valid_events": int(events[[signal, column]].dropna().shape[0]),
            "valid_months": int(len(monthly)),
            "hac": _hac_mean(values),
            "block_bootstrap": _block_bootstrap(values),
            "quintiles": _quintiles(events, signal, column),
        }
    return result


def exposure_diagnostics(events: pd.DataFrame, signal: str = "trend_pv") -> dict[str, Any]:
    frame = events[~events["limit_up"]].dropna(subset=[signal]).copy()
    if frame.empty:
        return {}
    frame["decile"] = frame.groupby("signal_date")[signal].rank(method="average", pct=True)
    frame["decile"] = np.ceil(frame["decile"] * 10).clip(1, 10).astype(int)
    by_decile = frame.groupby("decile")
    return {
        "median_market_cap_by_decile": {
            str(int(key)): float(value)
            for key, value in by_decile["pit_market_cap"].median().dropna().items()
        },
        "median_amount_proxy_by_decile": {
            str(int(key)): float(value)
            for key, value in by_decile["pre20_median_amount_proxy"].median().dropna().items()
        },
        "median_volatility_by_decile": {
            str(int(key)): float(value)
            for key, value in by_decile["pre60_volatility"].median().dropna().items()
        },
        "median_pre20_return_by_decile": {
            str(int(key)): float(value)
            for key, value in by_decile["pre20_return"].median().dropna().items()
        },
        "market_cap_coverage": float(frame["pit_market_cap"].notna().mean()),
        "industry_neutrality": "not testable: the PIT data has no historical industry labels",
    }


def _finite_ge(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) >= threshold


def _finite_gt(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > threshold


def evaluate_gates(
    primary: dict[str, Any],
    baseline_comparison: dict[str, Any],
    share_volume_sensitivity: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    n20 = primary["horizons"]["N20"]
    n60 = primary["horizons"]["N60"]
    q20 = n20["quintiles"]
    n20_mean = n20["hac"]["mean"]
    n20_t = n20["hac"]["t"]
    n60_mean = n60["hac"]["mean"]
    delta_mean = baseline_comparison["hac"]["mean"]
    share_mean = share_volume_sensitivity["horizons"]["N20"]["hac"]["mean"]
    positive_folds = sum(fold["mean_ic"] > 0 for fold in n20["folds"])
    data_gates = {
        "pit_universe_has_at_least_28_snapshots": diagnostics["universe_snapshots"] >= 28,
        "coefficient_burn_in_completed": diagnostics["coefficient_months"] >= COEFFICIENT_BURN_IN,
        "signal_coverage_p10_ge_70pct": (
            _finite_ge(diagnostics["pit_signal_coverage"]["p10"], 0.70)
        ),
        "n20_and_n60_at_least_36_months": (
            min(n20["valid_months"], n60["valid_months"]) >= MIN_VALID_MONTHS
        ),
        "exact_rmb_traded_value_available": diagnostics["exact_rmb_traded_value_available"],
    }
    signal_gates = {
        "n20_mean_ic_ge_003": _finite_ge(n20_mean, 0.03),
        "n20_hac_t_ge_2": _finite_ge(n20_t, 2.0),
        "n20_bootstrap_ci_above_zero": _finite_gt(
            n20["block_bootstrap"]["ci_low"], 0.0
        ),
        "n60_same_positive_sign": _finite_gt(n60_mean, 0.0),
        "n20_two_of_three_folds_positive": positive_folds >= 2,
        "n20_q5_minus_q1_positive_and_monotonic": (
            _finite_gt(q20["q5_minus_q1"], 0.0)
            and _finite_ge(q20["monotonic_rank_corr"], 0.70)
        ),
        "long_only_q5_excess_ci_above_zero": _finite_gt(
            q20["q5_excess_bootstrap"]["ci_low"], 0.0
        ),
        "paired_delta_vs_raw_ge_001": _finite_ge(delta_mean, 0.01),
        "paired_delta_bootstrap_ci_above_zero": (
            _finite_gt(baseline_comparison["block_bootstrap"]["ci_low"], 0.0)
        ),
        "delta_positive_excluding_2024q4": (
            _finite_gt(baseline_comparison["excluding_2024q4_mean"], 0.0)
        ),
        "share_volume_sensitivity_same_positive_sign": _finite_gt(share_mean, 0.0),
    }
    data_pass = all(data_gates.values())
    signal_pass = all(signal_gates.values())
    execution_data_ready = False
    proxy_signal_verdict = "PROXY_RESEARCH_GO" if signal_pass else "PROXY_SIGNAL_NO_GO"
    if not data_pass:
        verdict = "DATA_NO_GO"
    elif not signal_pass:
        verdict = "SIGNAL_NO_GO"
    else:
        verdict = "RESEARCH_GO_EXECUTION_DATA_REQUIRED"
    return {
        "data": data_gates,
        "signal": signal_gates,
        "data_pass": data_pass,
        "signal_pass": signal_pass,
        "execution_data_ready": execution_data_ready,
        "verdict": verdict,
        "proxy_signal_verdict": proxy_signal_verdict,
        "signal_portfolio_probe_allowed": bool(data_pass and signal_pass),
        "million_cny_portfolio_backtest_allowed": bool(
            data_pass and signal_pass and execution_data_ready
        ),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def run() -> dict[str, Any]:
    prices, close, volume, status = _load_price_panels()
    universe, schedule = load_universe_schedule()
    month_ends = _complete_month_end_dates(close.index)
    monthly_close = close.reindex(month_ends)

    primary_features, primary_feature_diagnostics = build_feature_frames(
        close, volume, status, month_ends, volume_mode="amount_proxy"
    )
    primary_signals, primary_diagnostics = estimate_online_trend(
        primary_features, monthly_close, schedule
    )
    share_features, share_feature_diagnostics = build_feature_frames(
        close, volume, status, month_ends, volume_mode="share_volume"
    )
    share_signals, share_diagnostics = estimate_online_trend(
        share_features, monthly_close, schedule
    )
    share_only = share_signals[["signal_date", "ticker", "trend_pv"]].rename(
        columns={"trend_pv": "trend_pv_share_volume"}
    )
    signals = primary_signals.merge(
        share_only, on=["signal_date", "ticker"], how="left", validate="one_to_one"
    )
    events = attach_forward_returns(signals, prices)
    market_dates = pd.DatetimeIndex(prices["date"].drop_duplicates().sort_values())
    n20_cutoff = market_dates[-20]
    n60_cutoff = market_dates[-60]
    n20_missing = events["ret_20"].isna()
    n60_missing = events["ret_60"].isna()
    n20_right_censored = n20_missing & events["entry_date"].gt(n20_cutoff)
    n60_right_censored = n60_missing & events["entry_date"].gt(n60_cutoff)
    events["ret_20_delist_stress"] = events["ret_20"]
    events["ret_60_delist_stress"] = events["ret_60"]
    events.loc[n20_missing & ~n20_right_censored, "ret_20_delist_stress"] = -1.0
    events.loc[n60_missing & ~n60_right_censored, "ret_60_delist_stress"] = -1.0
    primary = analyze_signal(events, "trend_pv")
    raw = analyze_signal(events, "raw_momentum_12_1")
    price_component = analyze_signal(events, "trend_price_component")
    volume_component = analyze_signal(events, "trend_volume_component")
    share_sensitivity = analyze_signal(events, "trend_pv_share_volume")
    baseline_comparison = compare_monthly_ic(primary, raw)
    delist_stress = analyze_delist_stress(events)

    member_counts = universe.groupby("as_of_date")["ticker"].nunique()
    limit_up_by_month = events.loc[events["limit_up"]].groupby("signal_date").size()
    combined_diagnostics = {
        **primary_diagnostics,
        "universe_snapshots": int(universe["as_of_date"].nunique()),
        "universe_member_count": _distribution(member_counts),
        "price_rows": int(len(prices)),
        "price_tickers": int(prices["ticker"].nunique()),
        "price_dates": int(prices["date"].nunique()),
        "price_start": prices["date"].min(),
        "price_end": prices["date"].max(),
        "suspended_rows": int(prices["tradestatus"].eq(0).sum()),
        "complete_month_ends": int(len(month_ends)),
        "primary_signal_rows": int(len(primary_signals)),
        "share_sensitivity_signal_rows": int(len(share_signals)),
        "priced_events": int(len(events)),
        "entry_delay_market_sessions": _distribution(events["entry_delay_market_sessions"]),
        "pit_market_cap_coverage": float(events["pit_market_cap"].notna().mean()),
        "exact_rmb_traded_value_available": False,
        "delayed_exit_events": {
            f"N{horizon}": int(events[f"exit_delay_{horizon}"].gt(0).sum())
            for horizon in HORIZONS
        },
        "max_exit_delay_sessions": {
            f"N{horizon}": int(events[f"exit_delay_{horizon}"].dropna().max())
            for horizon in HORIZONS
        },
        "limit_up_by_signal_month": {
            pd.Timestamp(month).date().isoformat(): int(count)
            for month, count in limit_up_by_month.items()
        },
    }
    gates = evaluate_gates(primary, baseline_comparison, share_sensitivity, combined_diagnostics)
    payload = {
        "study": "A-share multiscale price-volume trend first-look",
        "analysis_date": "2026-07-11",
        "protocol": {
            "candidate": (
                "Liu-Zhou-Zhu multiscale price-volume trend measure; 9 price and 9 "
                "traded-value MA ratios"
            ),
            "lags_sessions": list(MA_LAGS),
            "coefficient_estimation": (
                "monthly cross-sectional OLS of month-t return on month-(t-1) features; "
                "EMA coefficient forecast lambda=0.02"
            ),
            "coefficient_burn_in_months": COEFFICIENT_BURN_IN,
            "universe": "latest B070 PIT 800-member snapshot visible at each month-end",
            "execution": (
                "signal after month-end close; entry at first later tradestatus=1 open; "
                "N1 exits at the earliest legal T+1 close; N20/N60 exit at the first "
                "tradeable close at/after their entry-inclusive session target"
            ),
            "primary": "N20 monthly cross-sectional rank-IC for amount-proxy PV trend",
            "confirmation": "N60; N1 control; share-volume-only fixed sensitivity",
            "baseline": "classic 12-1 momentum on identical PIT rows and forward labels",
            "inference": (
                "Newey-West lag 3 and circular 6-month block bootstrap, 5000 draws"
            ),
            "no_parameter_sweep": True,
        },
        "literature": {
            "published_doi": PAPER_DOI,
            "author_hosted_working_copy": PAPER_WORKING_COPY,
            "published_result_context": (
                "2005-2018 long-short factor evidence is prior evidence only; this runner "
                "tests the predictive measure in a later, narrower long-only-compatible universe"
            ),
        },
        "inputs": {
            "prices": str(PRICE_PATH.relative_to(REPO_ROOT)),
            "prices_sha256": _sha256(PRICE_PATH),
            "universe": str(UNIVERSE_PATH.relative_to(REPO_ROOT)),
            "universe_sha256": _sha256(UNIVERSE_PATH),
            "pit_size": str(SIZE_PATH.relative_to(REPO_ROOT)),
            "pit_size_sha256": _sha256(SIZE_PATH),
            "script_sha256": _sha256(Path(__file__)),
        },
        "data_reality": {
            **combined_diagnostics,
            "primary_features": primary_feature_diagnostics,
            "share_volume_features": share_feature_diagnostics,
            "share_volume_estimator": share_diagnostics,
            "rmb_traded_value_exact": False,
            "traded_value_proxy": "qfq close * share volume",
            "portfolio_execution_data_ready": False,
            "portfolio_execution_blockers": [
                "qfq open cannot size 100-share lots at historical nominal prices",
                "exact RMB traded amount is absent",
                "historical ST and exact exchange limit prices are absent",
            ],
        },
        "sample": {
            "signal_rows": int(len(signals)),
            "priced_events": int(len(events)),
            "executable_events": int((~events["limit_up"]).sum()),
            "limit_up_events": int(events["limit_up"].sum()),
            "n20_valid_events": int(events["ret_20"].notna().sum()),
            "n60_valid_events": int(events["ret_60"].notna().sum()),
            "n20_missing": int(n20_missing.sum()),
            "n20_right_censored": int(n20_right_censored.sum()),
            "n20_path_ended_or_missing": int((n20_missing & ~n20_right_censored).sum()),
            "n60_missing": int(n60_missing.sum()),
            "n60_right_censored": int(n60_right_censored.sum()),
            "n60_path_ended_or_missing": int((n60_missing & ~n60_right_censored).sum()),
        },
        "signals": {
            "pv_trend_primary": primary,
            "raw_12_1_baseline": raw,
            "price_component_diagnostic": price_component,
            "volume_component_diagnostic": volume_component,
            "share_volume_sensitivity": share_sensitivity,
            "paired_primary_minus_raw": baseline_comparison,
            "path_ended_minus_100pct_sensitivity": delist_stress,
        },
        "exposures": exposure_diagnostics(events),
        "gates": gates,
        "interpretation_limits": [
            "This is a signal first-look, not a portfolio backtest or investment recommendation.",
            (
                "B070 covers a liquid HS300/CSI500/SSE50-derived 800-name PIT subset, "
                "not the full A-share market used by the paper."
            ),
            (
                "The paper uses RMB traded value; B070 lacks amount, so qfq close * share "
                "volume is the preregistered primary proxy and share volume is a sensitivity."
            ),
            (
                "PIT industry labels are unavailable, so industry neutrality cannot be claimed; "
                "market cap, volatility, liquidity, and recent-return exposures are "
                "diagnostic only."
            ),
            (
                "The 2018 start plus the paper's 400-session feature and 38-month coefficient "
                "warmups leaves a short post-2022 evaluation window."
            ),
            (
                "Historical ST flags and exact limit prices are absent; the normal-board "
                "10%/20% open-gap filter is conservative but incomplete."
            ),
            (
                "Signal-date quintiles are frozen before entry. A name that opens limit-up "
                "keeps its intended slot in cash and is not replaced by a lower-ranked name."
            ),
        ],
    }
    return _jsonable(payload)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), "verdict": payload["gates"]["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
