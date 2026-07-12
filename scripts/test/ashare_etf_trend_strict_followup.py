#!/usr/bin/env python
"""Strict evaluator follow-up for the B084 A-share ETF trend candidate.

The registered signal is unchanged: at each complete month end, hold each ETF
whose 12-month adjusted-price momentum is positive and otherwise keep cash.
Orders are executed at the next market open. The primary scope is the original
five fixed economic sleeves from B084; an expanded current-survivor basket is a
contaminated sensitivity only.

This script is research-only. It does not import or modify product strategy code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_B084 = ROOT / "data/research/b084_etf/prices.csv"
B082_512890 = ROOT / "data/research/b082/etf_512890.csv"
DEFAULT_CACHE = Path("/tmp/ashare_etf_trend_strict_cache")
DEFAULT_OUT = ROOT / "docs/test-reports/ashare-etf-trend-strict-followup-2026-07-12.json"

FROZEN_END = "20260710"
LOOKBACK_MONTHS = 12
INITIAL_CAPITAL_CNY = 2_100_000.0
COMMISSION_BPS = 2.5
SLIPPAGE_BPS = 5.0
MIN_COMMISSION_CNY = 5.0
LOT_SIZE = 100
PARTICIPATION_GATE = 0.01
BOOTSTRAP_SEED = 20260712
BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_BLOCK = 6
NW_LAGS = 3


@dataclass(frozen=True)
class EtfSpec:
    code: str
    name: str
    start: str
    group: str


B084_PRIMARY: tuple[EtfSpec, ...] = (
    EtfSpec("159915", "ChiNext", "20111209", "broad"),
    EtfSpec("510300", "CSI 300", "20120528", "broad"),
    EtfSpec("510500", "CSI 500", "20130315", "broad"),
    EtfSpec("512890", "Dividend Low Vol", "20190118", "style"),
    EtfSpec("588000", "STAR 50", "20201116", "broad"),
)

LEGACY_CORE3 = ("159915", "510300", "510500")

# Current surviving representatives chosen before this corrected run. This is
# intentionally secondary because the repository has no PIT ETF master.
EXPANDED_EXTRA: tuple[EtfSpec, ...] = (
    EtfSpec("510050", "SSE 50", "20050223", "broad"),
    EtfSpec("510880", "Dividend", "20061117", "style"),
    EtfSpec("159928", "Consumer", "20130916", "sector"),
    EtfSpec("512010", "Pharma", "20131028", "sector"),
    EtfSpec("512660", "Defense", "20160726", "sector"),
    EtfSpec("512880", "Securities", "20160808", "sector"),
    EtfSpec("512800", "Banks", "20170803", "sector"),
    EtfSpec("512480", "Semiconductors", "20190612", "sector"),
)

FROZEN_FOLDS: tuple[tuple[str, str, str], ...] = (
    ("2013-2016", "2013-01-01", "2016-12-31"),
    ("2017-2020", "2017-01-01", "2020-12-31"),
    ("2021-2023", "2021-01-01", "2023-12-31"),
    ("2024-2026", "2024-01-01", "2026-05-31"),
)

WHIPSAW_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("early_2022", "2022-01-01", "2022-04-30"),
    ("early_2024", "2024-01-01", "2024-02-29"),
)


def _market_symbol(code: str) -> str:
    return ("sh" if code[0] in "56" else "sz") + code


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_frame_sha(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["date"]).reset_index(drop=True)
    return _sha256_bytes(ordered.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def _request_tx_block(
    session: requests.Session,
    symbol: str,
    year: int,
    *,
    timeout: float = 25.0,
    retries: int = 3,
) -> list[list[Any]]:
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
    params = {
        "_var": f"kline_dayqfq{year}",
        "param": f"{symbol},day,{year}-01-01,{year + 1}-12-31,640,qfq",
        "r": "0.8205512681390605",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            text = response.text
            marker = text.find("={")
            if marker < 0:
                raise ValueError("Tencent response lacks JSON marker")
            payload = json.loads(text[marker + 1 :])
            node = payload["data"][symbol]
            rows = node.get("qfqday") or node.get("day") or node.get("hfqday")
            if rows is None:
                raise ValueError("Tencent response lacks daily rows")
            return rows
        except (KeyError, TypeError, ValueError, requests.RequestException) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Tencent fetch failed for {symbol}/{year}: {last_error}")


def _normalise_tx_rows(rows: Iterable[Sequence[Any]], code: str) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 9:
            continue
        records.append(
            {
                "date": row[0],
                "open": row[1],
                "close": row[2],
                "high": row[3],
                "low": row[4],
                "volume_lots": row[5],
                "turnover_pct": row[7],
                # Tencent encodes this field in ten-thousand CNY.
                "amount_cny": row[8],
                "ticker": code,
            }
        )
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    numeric = ["open", "close", "high", "low", "volume_lots", "turnover_pct", "amount_cny"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["amount_cny"] = frame["amount_cny"] * 10_000.0
    frame = frame.dropna(subset=["date", "open", "close", "high", "low", "amount_cny"])
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def fetch_qfq_etf(
    spec: EtfSpec,
    cache_dir: Path,
    *,
    refresh: bool = False,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{spec.code}-qfq-through-{FROZEN_END}.csv"
    if cache.is_file() and not refresh:
        frame = pd.read_csv(cache, dtype={"ticker": str}, parse_dates=["date"])
        frame.attrs["source_sha256"] = _sha256_file(cache)
        return frame.sort_values("date").reset_index(drop=True)

    owned_session = session is None
    active = session or requests.Session()
    active.headers.update({"User-Agent": "Mozilla/5.0 Codex evaluator research"})
    rows: list[list[Any]] = []
    start_year = int(spec.start[:4])
    end_year = int(FROZEN_END[:4])
    try:
        for year in range(start_year, end_year + 1, 2):
            rows.extend(_request_tx_block(active, _market_symbol(spec.code), year))
    finally:
        if owned_session:
            active.close()
    frame = _normalise_tx_rows(rows, spec.code)
    start = pd.Timestamp(spec.start)
    end = pd.Timestamp(FROZEN_END)
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)].reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"No adjusted ETF data for {spec.code}")
    frame.to_csv(cache, index=False)
    frame.attrs["source_sha256"] = _sha256_file(cache)
    return frame


def validate_qfq_frame(frame: pd.DataFrame) -> dict[str, Any]:
    duplicate_dates = int(frame["date"].duplicated().sum())
    core = frame[["open", "close", "high", "low", "amount_cny"]]
    missing_core = int(core.isna().any(axis=1).sum())
    nonpositive = int((core <= 0).any(axis=1).sum())
    ohlc_bad = int(
        (
            (frame["high"] < frame[["open", "close"]].max(axis=1))
            | (frame["low"] > frame[["open", "close"]].min(axis=1))
            | (frame["high"] < frame["low"])
        ).sum()
    )
    daily = frame["close"].pct_change()
    extreme_adjusted_moves = int((daily.abs() > 0.80).sum())
    return {
        "rows": int(len(frame)),
        "start": frame["date"].min().date().isoformat(),
        "end": frame["date"].max().date().isoformat(),
        "duplicate_dates": duplicate_dates,
        "missing_core_rows": missing_core,
        "nonpositive_rows": nonpositive,
        "ohlc_violation_rows": ohlc_bad,
        "adjusted_daily_moves_over_80pct": extreme_adjusted_moves,
        "sha256": frame.attrs.get("source_sha256", _canonical_frame_sha(frame)),
        "pass": duplicate_dates == 0
        and missing_core == 0
        and nonpositive == 0
        and ohlc_bad == 0
        and extreme_adjusted_moves == 0,
    }


def load_raw_b084(path: Path = RAW_B084) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"ticker": str}, parse_dates=["date"])
    return frame.sort_values(["ticker", "date"]).reset_index(drop=True)


def attach_nominal_prices(qfq: pd.DataFrame, raw_close: pd.DataFrame) -> pd.DataFrame:
    raw = raw_close[["date", "ticker", "close"]].rename(columns={"close": "raw_close"})
    merged = qfq.merge(raw, on=["date", "ticker"], how="left", validate="one_to_one")
    merged["adjustment_scale"] = merged["raw_close"] / merged["close"]
    merged["nominal_open"] = merged["open"] * merged["adjustment_scale"]
    merged["nominal_high"] = merged["high"] * merged["adjustment_scale"]
    merged["nominal_low"] = merged["low"] * merged["adjustment_scale"]
    return merged


def raw_corporate_action_diagnostics(
    raw: pd.DataFrame, adjusted: Mapping[str, pd.DataFrame]
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    action_candidates: list[dict[str, Any]] = []
    for code, group in raw.groupby("ticker"):
        monthly = group.set_index("date")["close"].sort_index().resample("ME").last()
        returns = monthly.pct_change()
        adjusted_monthly = (
            adjusted[str(code)].set_index("date")["close"].sort_index().resample("ME").last()
        )
        adjusted_returns = adjusted_monthly.pct_change()
        for date, value in returns[returns.abs() > 0.40].items():
            adjusted_value = float(adjusted_returns.get(date, float("nan")))
            record = {
                "ticker": str(code),
                "month": date.date().isoformat(),
                "raw_monthly_return": float(value),
                "adjusted_monthly_return": adjusted_value,
                "absolute_gap": abs(float(value) - adjusted_value),
            }
            records.append(record)
            if math.isfinite(adjusted_value) and record["absolute_gap"] > 0.20:
                action_candidates.append(record)
    return {
        "raw_monthly_moves_over_40pct": records,
        "raw_extreme_count": len(records),
        "corporate_action_candidates": action_candidates,
        "corporate_action_candidate_count": len(action_candidates),
    }


def amount_field_crosscheck(qfq_512890: pd.DataFrame) -> dict[str, Any]:
    raw = pd.read_csv(B082_512890, parse_dates=["date"])
    merged = qfq_512890[["date", "amount_cny"]].merge(
        raw[["date", "close", "volume"]], on="date", how="inner", validate="one_to_one"
    )
    proxy = merged["close"] * merged["volume"]
    relative_error = (merged["amount_cny"] - proxy).abs() / merged["amount_cny"]
    return {
        "rows": int(len(merged)),
        "b082_512890_sha256": _sha256_file(B082_512890),
        "median_absolute_relative_error_vs_close_times_volume": float(relative_error.median()),
        "p95_absolute_relative_error_vs_close_times_volume": float(relative_error.quantile(0.95)),
        "maximum_absolute_relative_error_vs_close_times_volume": float(relative_error.max()),
        "correlation_vs_close_times_volume": float(merged["amount_cny"].corr(proxy)),
    }


def build_signal_schedule(
    frames: Mapping[str, pd.DataFrame],
    codes: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_dates = sorted(set().union(*(set(frames[code]["date"]) for code in codes)))
    calendar = pd.DatetimeIndex(all_dates)
    complete = calendar[calendar.to_period("M") < calendar.max().to_period("M")]
    month_end_dates = pd.Series(complete, index=complete).groupby(complete.to_period("M")).max()

    close = pd.DataFrame(index=pd.DatetimeIndex(month_end_dates.values), columns=codes, dtype=float)
    close.index.name = "signal_date"
    for code in codes:
        series = frames[code].set_index("date")["close"].sort_index()
        close[code] = series.reindex(close.index, method="ffill")

    momentum = close / close.shift(LOOKBACK_MONTHS) - 1.0
    entry_rows: list[dict[str, Any]] = []
    for signal_date in close.index:
        later = calendar[calendar > signal_date]
        if len(later) == 0:
            continue
        entry_rows.append({"signal_date": signal_date, "entry_date": later[0]})
    entries = pd.DataFrame(entry_rows).set_index("signal_date")
    # Each evaluated signal needs the following month's entry as its exit mark.
    entries["exit_date"] = entries["entry_date"].shift(-1)
    entries = entries.dropna(subset=["exit_date"])
    momentum = momentum.reindex(entries.index)
    return momentum, entries


def _entry_bar(frame: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    rows = frame[frame["date"] == date]
    return None if rows.empty else rows.iloc[0]


def _locked_direction(bar: pd.Series, previous_close: float | None) -> str | None:
    if previous_close is None or not math.isfinite(previous_close) or previous_close <= 0:
        return None
    flat = abs(float(bar["high"]) - float(bar["low"])) <= 1e-12
    move = float(bar["open"]) / previous_close - 1.0
    if flat and move >= 0.095:
        return "up"
    if flat and move <= -0.095:
        return "down"
    return None


def _trade_cost(trade_notional: float, friction_multiplier: float = 1.0) -> float:
    if trade_notional <= 1e-9:
        return 0.0
    commission = max(
        trade_notional * COMMISSION_BPS / 10_000.0 * friction_multiplier,
        MIN_COMMISSION_CNY,
    )
    slippage = trade_notional * SLIPPAGE_BPS / 10_000.0 * friction_multiplier
    return commission + slippage


def _target_notionals(
    nav: float,
    weights: Mapping[str, float],
    current: Mapping[str, float],
    nominal_open: Mapping[str, float] | None,
    friction_multiplier: float,
) -> tuple[dict[str, float], float, dict[str, float]]:
    reserve = 0.0
    target: dict[str, float] = {}
    trades: dict[str, float] = {}
    for _ in range(8):
        investable = max(nav - reserve, 0.0)
        target = {}
        for code, weight in weights.items():
            desired = investable * weight
            if nominal_open is not None:
                price = nominal_open.get(code, float("nan"))
                if not math.isfinite(price) or price <= 0:
                    desired = float(current.get(code, 0.0))
                else:
                    desired = math.floor(desired / (price * LOT_SIZE)) * price * LOT_SIZE
            target[code] = max(float(desired), 0.0)
        universe = sorted(set(current) | set(target))
        trades = {code: abs(target.get(code, 0.0) - current.get(code, 0.0)) for code in universe}
        updated = sum(_trade_cost(value, friction_multiplier) for value in trades.values())
        if abs(updated - reserve) < 0.01:
            reserve = updated
            break
        reserve = updated
    while sum(target.values()) + reserve > nav + 1e-6 and target:
        code = max(target, key=target.get)
        if nominal_open is None:
            target[code] = max(target[code] - (sum(target.values()) + reserve - nav), 0.0)
        else:
            lot = nominal_open[code] * LOT_SIZE
            target[code] = max(target[code] - lot, 0.0)
        universe = sorted(set(current) | set(target))
        trades = {key: abs(target.get(key, 0.0) - current.get(key, 0.0)) for key in universe}
        reserve = sum(_trade_cost(value, friction_multiplier) for value in trades.values())
    return target, reserve, trades


def _trailing_amount(frame: pd.DataFrame, signal_date: pd.Timestamp, sessions: int = 20) -> float:
    values = frame.loc[frame["date"] <= signal_date, "amount_cny"].tail(sessions)
    return float(values.median()) if len(values) else float("nan")


def simulate_strategy(
    frames: Mapping[str, pd.DataFrame],
    codes: Sequence[str],
    *,
    trend: bool,
    nominal_lots: bool,
    allocation_mode: str,
    friction_multiplier: float,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    momentum, entries = build_signal_schedule(frames, codes)
    if start is not None:
        entries = entries[entries.index >= pd.Timestamp(start)]
    if end is not None:
        entries = entries[entries.index <= pd.Timestamp(end)]
    momentum = momentum.reindex(entries.index)
    has_eligible_asset = momentum.notna().any(axis=1)
    entries = entries.loc[has_eligible_asset]
    momentum = momentum.reindex(entries.index)

    current: dict[str, float] = {}
    cash = INITIAL_CAPITAL_CNY
    period_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    locked_buys = 0
    locked_sells = 0
    total_cost = 0.0
    total_turnover = 0.0

    for signal_date, dates in entries.iterrows():
        entry_date = pd.Timestamp(dates["entry_date"])
        exit_date = pd.Timestamp(dates["exit_date"])
        bars: dict[str, pd.Series] = {}
        exit_bars: dict[str, pd.Series] = {}
        for code in codes:
            bar = _entry_bar(frames[code], entry_date)
            exit_bar = _entry_bar(frames[code], exit_date)
            if bar is not None and exit_bar is not None:
                bars[code] = bar
                exit_bars[code] = exit_bar

        eligible = [
            code
            for code in codes
            if code in bars and pd.notna(momentum.at[signal_date, code])
        ]
        selected = (
            [code for code in eligible if float(momentum.at[signal_date, code]) > 0.0]
            if trend
            else eligible
        )
        if allocation_mode == "fixed_slots":
            weights = {code: 1.0 / len(codes) for code in selected}
        elif allocation_mode == "selected_full_weight":
            weights = {code: 1.0 / len(selected) for code in selected} if selected else {}
        else:
            raise ValueError(f"Unknown allocation mode: {allocation_mode}")

        nav_before = cash + sum(current.values())
        nominal_open: dict[str, float] | None = None
        if nominal_lots:
            nominal_open = {
                code: float(bars[code].get("nominal_open", float("nan"))) for code in selected
            }

        preliminary, _, _ = _target_notionals(
            nav_before, weights, current, nominal_open, friction_multiplier
        )
        for code in sorted(set(current) | set(preliminary)):
            bar = bars.get(code)
            if bar is None:
                preliminary[code] = current.get(code, 0.0)
                continue
            history = frames[code].loc[frames[code]["date"] < entry_date, "close"]
            previous_close = float(history.iloc[-1]) if len(history) else None
            direction = _locked_direction(bar, previous_close)
            prior = current.get(code, 0.0)
            wanted = preliminary.get(code, 0.0)
            if direction == "up" and wanted > prior:
                preliminary[code] = prior
                locked_buys += 1
            elif direction == "down" and wanted < prior:
                preliminary[code] = prior
                locked_sells += 1
        effective_weight_sum = sum(preliminary.values())
        if effective_weight_sum > 0:
            # Preserve blocked amounts as cash; do not redistribute among tradable names.
            effective_weights = {
                code: value / nav_before
                for code, value in preliminary.items()
                if value > 0
            }
        else:
            effective_weights = {}
        target, cost, trades = _target_notionals(
            nav_before,
            effective_weights,
            current,
            nominal_open if nominal_lots else None,
            friction_multiplier,
        )
        traded = sum(trades.values())
        turnover = traded / nav_before if nav_before > 0 else 0.0
        cash_after = nav_before - sum(target.values()) - cost
        if cash_after < -0.01:
            raise AssertionError(f"negative cash after rebalance: {cash_after}")
        cash_after = max(cash_after, 0.0)

        max_participation = 0.0
        for code, value in trades.items():
            if value <= 1e-9:
                continue
            median_amount = _trailing_amount(frames[code], signal_date)
            participation = value / median_amount if median_amount > 0 else float("inf")
            max_participation = max(max_participation, participation)
            trade_rows.append(
                {
                    "signal_date": signal_date,
                    "entry_date": entry_date,
                    "ticker": code,
                    "trade_notional": value,
                    "median_20d_amount": median_amount,
                    "participation": participation,
                }
            )

        end_positions: dict[str, float] = {}
        valuation_dates = sorted(
            {
                pd.Timestamp(date)
                for code in target
                for date in frames[code].loc[
                    (frames[code]["date"] >= entry_date)
                    & (frames[code]["date"] < exit_date),
                    "date",
                ]
            }
        )
        for valuation_date in valuation_dates:
            daily_value = cash_after
            for code, value in target.items():
                if value <= 0 or code not in bars:
                    continue
                rows = frames[code][frames[code]["date"] == valuation_date]
                if rows.empty:
                    prior = frames[code][frames[code]["date"] < valuation_date]
                    if prior.empty:
                        continue
                    mark = float(prior.iloc[-1]["close"])
                else:
                    mark = float(rows.iloc[0]["close"])
                daily_value += value * mark / float(bars[code]["open"])
            daily_rows.append(
                {"date": valuation_date, "phase": "close", "nav": daily_value}
            )
        for code, value in target.items():
            if value <= 0 or code not in bars or code not in exit_bars:
                continue
            asset_return = float(exit_bars[code]["open"] / bars[code]["open"] - 1.0)
            end_positions[code] = value * (1.0 + asset_return)
        nav_end = cash_after + sum(end_positions.values())
        daily_rows.append({"date": exit_date, "phase": "open", "nav": nav_end})
        period_return = nav_end / nav_before - 1.0 if nav_before > 0 else float("nan")
        period_rows.append(
            {
                "signal_date": signal_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "return": period_return,
                "nav_start": nav_before,
                "nav_end": nav_end,
                "cost": cost,
                "turnover": turnover,
                "n_eligible": len(eligible),
                "n_selected": len(selected),
                "cash_weight": cash_after / nav_before if nav_before > 0 else float("nan"),
                "max_participation": max_participation,
            }
        )
        current = end_positions
        cash = cash_after
        total_cost += cost
        total_turnover += turnover

    periods = pd.DataFrame(period_rows)
    trades_frame = pd.DataFrame(trade_rows)
    diagnostics = {
        "total_cost_cny": total_cost,
        "total_turnover": total_turnover,
        "locked_buy_events": locked_buys,
        "locked_sell_events": locked_sells,
        "trade_events": int(len(trades_frame)),
        "max_participation": float(trades_frame["participation"].max())
        if len(trades_frame)
        else 0.0,
        "participation_p95": float(trades_frame["participation"].quantile(0.95))
        if len(trades_frame)
        else 0.0,
        "participation_pass_rate": float(
            (trades_frame["participation"] <= PARTICIPATION_GATE).mean()
        )
        if len(trades_frame)
        else 1.0,
    }
    if len(trades_frame):
        maximum_trade = trades_frame.loc[trades_frame["participation"].idxmax()].to_dict()
        diagnostics["maximum_participation_trade"] = {
            key: (value.date().isoformat() if isinstance(value, pd.Timestamp) else value)
            for key, value in maximum_trade.items()
        }
        recent = trades_frame[trades_frame["signal_date"] >= pd.Timestamp("2024-01-01")]
        diagnostics["since_2024_max_participation"] = (
            float(recent["participation"].max()) if len(recent) else None
        )
        diagnostics["since_2024_participation_pass_rate"] = (
            float((recent["participation"] <= PARTICIPATION_GATE).mean())
            if len(recent)
            else None
        )
    daily_nav = pd.DataFrame(daily_rows)
    return periods, diagnostics, daily_nav


def performance_metrics(
    periods: pd.DataFrame, daily_nav: pd.DataFrame | None = None
) -> dict[str, Any]:
    returns = periods["return"].dropna().astype(float)
    if len(returns) == 0:
        return {
            "months": 0,
            "cagr": None,
            "sharpe": None,
            "max_drawdown": None,
            "annualized_volatility": None,
            "ending_nav": None,
            "annualized_turnover": None,
            "total_cost_cny": None,
        }
    equity = INITIAL_CAPITAL_CNY * (1.0 + returns).cumprod()
    years = len(returns) / 12.0
    standard_deviation = float(returns.std(ddof=1))
    if daily_nav is not None and len(daily_nav):
        daily_equity = pd.concat(
            [pd.Series([INITIAL_CAPITAL_CNY]), daily_nav["nav"].reset_index(drop=True)],
            ignore_index=True,
        )
        max_drawdown = float((daily_equity / daily_equity.cummax() - 1.0).min())
        daily_observations = int(len(daily_nav))
    else:
        max_drawdown = float((equity / equity.cummax() - 1.0).min())
        daily_observations = None
    return {
        "months": int(len(returns)),
        "start_signal": pd.Timestamp(periods.iloc[0]["signal_date"]).date().isoformat(),
        "end_signal": pd.Timestamp(periods.iloc[-1]["signal_date"]).date().isoformat(),
        "cagr": float((equity.iloc[-1] / INITIAL_CAPITAL_CNY) ** (1.0 / years) - 1.0),
        "sharpe": float(returns.mean() / standard_deviation * math.sqrt(12.0))
        if standard_deviation > 0
        else None,
        "max_drawdown": max_drawdown,
        "max_drawdown_frequency": "daily" if daily_nav is not None else "periodic",
        "daily_nav_observations": daily_observations,
        "annualized_volatility": standard_deviation * math.sqrt(12.0),
        "ending_nav": float(equity.iloc[-1]),
        "annualized_turnover": float(periods["turnover"].sum() / years),
        "total_cost_cny": float(periods["cost"].sum()),
        "average_selected": float(periods["n_selected"].mean()),
        "average_cash_weight": float(periods["cash_weight"].mean()),
    }


def newey_west_mean(series: pd.Series, lags: int = NW_LAGS) -> dict[str, Any]:
    values = series.dropna().to_numpy(dtype=float)
    count = len(values)
    if count < 2:
        return {"n": count, "mean": None, "se": None, "t": None, "lags": lags}
    centered = values - values.mean()
    long_run = float(centered @ centered / count)
    for lag in range(1, min(lags, count - 1) + 1):
        covariance = float(centered[lag:] @ centered[:-lag] / count)
        long_run += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    standard_error = math.sqrt(max(long_run, 0.0) / count)
    return {
        "n": count,
        "mean": float(values.mean()),
        "annualized_mean": float(values.mean() * 12.0),
        "se": standard_error,
        "t": float(values.mean() / standard_error) if standard_error > 0 else None,
        "lags": lags,
    }


def block_bootstrap_mean_ci(
    series: pd.Series,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    block: int = BOOTSTRAP_BLOCK,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    values = series.dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return {"lower": None, "upper": None, "draws": draws, "block": block, "seed": seed}
    rng = np.random.default_rng(seed)
    starts = np.arange(len(values))
    sampled_means = np.empty(draws, dtype=float)
    blocks_needed = math.ceil(len(values) / block)
    for draw in range(draws):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate(
            [values[(start + np.arange(block)) % len(values)] for start in chosen]
        )[: len(values)]
        sampled_means[draw] = sample.mean()
    lower, upper = np.quantile(sampled_means, [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "annualized_lower": float(lower * 12.0),
        "annualized_upper": float(upper * 12.0),
        "draws": draws,
        "block": block,
        "seed": seed,
    }


def compare_periods(trend: pd.DataFrame, hold: pd.DataFrame) -> dict[str, Any]:
    paired = trend[["signal_date", "return"]].merge(
        hold[["signal_date", "return"]], on="signal_date", suffixes=("_trend", "_hold")
    )
    paired["excess"] = paired["return_trend"] - paired["return_hold"]
    return {
        "paired_months": int(len(paired)),
        "hac": newey_west_mean(paired["excess"]),
        "block_bootstrap_95": block_bootstrap_mean_ci(paired["excess"]),
        "monthly_win_rate": float((paired["excess"] > 0).mean()),
    }


def _window_metrics(periods: pd.DataFrame, start: str, end: str) -> dict[str, Any]:
    mask = (periods["entry_date"] >= pd.Timestamp(start)) & (
        periods["entry_date"] <= pd.Timestamp(end)
    )
    subset = periods.loc[mask].copy()
    return performance_metrics(subset)


def fold_diagnostics(trend: pd.DataFrame, hold: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, start, end in FROZEN_FOLDS:
        trend_metrics = _window_metrics(trend, start, end)
        hold_metrics = _window_metrics(hold, start, end)
        rows.append(
            {
                "label": label,
                "start": start,
                "end": end,
                "trend": trend_metrics,
                "hold": hold_metrics,
                "cagr_delta": _finite_delta(trend_metrics.get("cagr"), hold_metrics.get("cagr")),
                "sharpe_delta": _finite_delta(
                    trend_metrics.get("sharpe"), hold_metrics.get("sharpe")
                ),
            }
        )
    return rows


def whipsaw_diagnostics(trend: pd.DataFrame, hold: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for label, start, end in WHIPSAW_WINDOWS:
        trend_metrics = _window_metrics(trend, start, end)
        trend_return = _cumulative_window_return(trend, start, end)
        hold_return = _cumulative_window_return(hold, start, end)
        output[label] = {
            "trend_return": trend_return,
            "hold_return": hold_return,
            "delta": trend_return - hold_return,
            "months": trend_metrics["months"],
        }
    return output


def _cumulative_window_return(periods: pd.DataFrame, start: str, end: str) -> float:
    mask = (periods["entry_date"] >= pd.Timestamp(start)) & (
        periods["entry_date"] <= pd.Timestamp(end)
    )
    return float((1.0 + periods.loc[mask, "return"]).prod() - 1.0)


def _finite_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    left_value = float(left)
    right_value = float(right)
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        return None
    return left_value - right_value


def evaluate_gates(
    trend_metrics: Mapping[str, Any],
    hold_metrics: Mapping[str, Any],
    comparison: Mapping[str, Any],
    folds: Sequence[Mapping[str, Any]],
    whipsaw: Mapping[str, Mapping[str, Any]],
    execution: Mapping[str, Any],
    data_pass: bool,
) -> dict[str, Any]:
    cagr_delta = _finite_delta(trend_metrics.get("cagr"), hold_metrics.get("cagr"))
    sharpe_delta = _finite_delta(trend_metrics.get("sharpe"), hold_metrics.get("sharpe"))
    drawdown_delta = _finite_delta(
        trend_metrics.get("max_drawdown"), hold_metrics.get("max_drawdown")
    )
    positive_folds = sum(
        1
        for row in folds
        if row.get("cagr_delta") is not None and float(row["cagr_delta"]) > 0.0
    )
    hac_t = comparison["hac"].get("t")
    bootstrap_lower = comparison["block_bootstrap_95"].get("lower")
    worst_whipsaw = min(float(row["delta"]) for row in whipsaw.values())
    gates = {
        "data_integrity": bool(data_pass),
        "net_cagr_delta_at_least_2pp": cagr_delta is not None and cagr_delta >= 0.02,
        "net_sharpe_delta_at_least_0_15": sharpe_delta is not None and sharpe_delta >= 0.15,
        "max_drawdown_not_worse": drawdown_delta is not None and drawdown_delta >= 0.0,
        "paired_hac_t_at_least_1_65": hac_t is not None
        and math.isfinite(float(hac_t))
        and float(hac_t) >= 1.65,
        "bootstrap_mean_lower_above_zero": bootstrap_lower is not None
        and math.isfinite(float(bootstrap_lower))
        and float(bootstrap_lower) > 0.0,
        "at_least_3_of_4_positive_cagr_folds": positive_folds >= 3,
        "worst_preregistered_whipsaw_not_below_minus_5pp": worst_whipsaw >= -0.05,
        "participation_pass_rate_at_least_95pct": float(execution["participation_pass_rate"])
        >= 0.95,
        "max_participation_at_most_1pct": float(execution["max_participation"])
        <= PARTICIPATION_GATE,
    }
    return {
        "thresholds": {
            "cagr_delta": 0.02,
            "sharpe_delta": 0.15,
            "max_drawdown_delta": 0.0,
            "hac_t": 1.65,
            "positive_folds": 3,
            "worst_whipsaw_delta": -0.05,
            "participation": PARTICIPATION_GATE,
        },
        "observed": {
            "cagr_delta": cagr_delta,
            "sharpe_delta": sharpe_delta,
            "max_drawdown_delta": drawdown_delta,
            "positive_cagr_folds": positive_folds,
            "worst_whipsaw_delta": worst_whipsaw,
        },
        "gates": gates,
        "all_pass": all(gates.values()),
    }


def run_scope(
    frames: Mapping[str, pd.DataFrame],
    codes: Sequence[str],
    *,
    nominal_lots: bool,
    allocation_mode: str,
    friction_multiplier: float = 1.0,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    trend, trend_execution, trend_daily = simulate_strategy(
        frames,
        codes,
        trend=True,
        nominal_lots=nominal_lots,
        allocation_mode=allocation_mode,
        friction_multiplier=friction_multiplier,
        start=start,
        end=end,
    )
    hold, hold_execution, hold_daily = simulate_strategy(
        frames,
        codes,
        trend=False,
        nominal_lots=nominal_lots,
        allocation_mode=allocation_mode,
        friction_multiplier=friction_multiplier,
        start=start,
        end=end,
    )
    return {
        "codes": list(codes),
        "allocation_mode": allocation_mode,
        "variable_friction_bps": (COMMISSION_BPS + SLIPPAGE_BPS)
        * friction_multiplier,
        "trend": performance_metrics(trend, trend_daily),
        "hold": performance_metrics(hold, hold_daily),
        "comparison": compare_periods(trend, hold),
        "folds": fold_diagnostics(trend, hold),
        "whipsaw": whipsaw_diagnostics(trend, hold),
        "trend_execution": trend_execution,
        "hold_execution": hold_execution,
        "periods": {
            "trend": _period_records(trend),
            "hold": _period_records(hold),
        },
    }


def _period_records(periods: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in periods.to_dict("records"):
        records.append(
            {
                key: (value.date().isoformat() if isinstance(value, pd.Timestamp) else value)
                for key, value in row.items()
            }
        )
    return records


def _common_start(frames: Mapping[str, pd.DataFrame], codes: Sequence[str]) -> str:
    momentum, entries = build_signal_schedule(frames, codes)
    complete = momentum.notna().all(axis=1)
    valid = entries.index[complete]
    if len(valid) == 0:
        raise ValueError("No common 12-month history for scope")
    return pd.Timestamp(valid[0]).date().isoformat()


def _compact_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in scope.items() if key != "periods"}


def build_report(cache_dir: Path, *, refresh: bool, skip_expanded: bool) -> dict[str, Any]:
    specs = list(B084_PRIMARY)
    if not skip_expanded:
        specs.extend(EXPANDED_EXTRA)
    shared_session = requests.Session()
    shared_session.headers.update({"User-Agent": "Mozilla/5.0 Codex evaluator research"})
    fetched: dict[str, pd.DataFrame] = {}
    validations: dict[str, Any] = {}
    try:
        for spec in specs:
            frame = fetch_qfq_etf(
                spec, cache_dir, refresh=refresh, session=shared_session
            )
            fetched[spec.code] = frame
            validations[spec.code] = validate_qfq_frame(frame)
    finally:
        shared_session.close()

    raw = load_raw_b084()
    primary_frames: dict[str, pd.DataFrame] = {}
    for spec in B084_PRIMARY:
        primary_frames[spec.code] = attach_nominal_prices(fetched[spec.code], raw)
    raw_coverage = {
        code: float(primary_frames[code]["nominal_open"].notna().mean()) for code in primary_frames
    }
    evaluation_raw_coverage = {
        code: float(
            primary_frames[code].loc[
                primary_frames[code]["date"] <= pd.Timestamp("2026-07-03"), "nominal_open"
            ].notna().mean()
        )
        for code in primary_frames
    }
    primary_codes = [spec.code for spec in B084_PRIMARY]
    source_data_pass = all(validations[code]["pass"] for code in primary_codes) and all(
        value >= 0.995 for value in evaluation_raw_coverage.values()
    )

    common_start = _common_start(primary_frames, primary_codes)
    primary = run_scope(
        primary_frames,
        primary_codes,
        nominal_lots=True,
        allocation_mode="fixed_slots",
    )
    legacy_normalized = run_scope(
        primary_frames,
        primary_codes,
        nominal_lots=True,
        allocation_mode="selected_full_weight",
    )
    cost_sensitivities = {
        "10bp": _compact_scope(
            run_scope(
                primary_frames,
                primary_codes,
                nominal_lots=True,
                allocation_mode="fixed_slots",
                friction_multiplier=10.0 / (COMMISSION_BPS + SLIPPAGE_BPS),
            )
        ),
        "25bp": _compact_scope(
            run_scope(
                primary_frames,
                primary_codes,
                nominal_lots=True,
                allocation_mode="fixed_slots",
                friction_multiplier=25.0 / (COMMISSION_BPS + SLIPPAGE_BPS),
            )
        ),
    }
    core3 = run_scope(
        primary_frames,
        LEGACY_CORE3,
        nominal_lots=True,
        allocation_mode="fixed_slots",
    )
    common5 = run_scope(
        primary_frames,
        primary_codes,
        nominal_lots=True,
        allocation_mode="fixed_slots",
        start=common_start,
    )
    common_history_months = int(common5["trend"]["months"])
    common_history_pass = common_history_months >= 60
    data_pass = source_data_pass and common_history_pass

    gates = evaluate_gates(
        primary["trend"],
        primary["hold"],
        primary["comparison"],
        primary["folds"],
        primary["whipsaw"],
        primary["trend_execution"],
        data_pass,
    )

    expanded: dict[str, Any] | None = None
    if not skip_expanded:
        expanded_codes = [spec.code for spec in specs]
        invalid_codes = [code for code in expanded_codes if not validations[code]["pass"]]
        expanded_data_pass = len(invalid_codes) == 0
        if expanded_data_pass:
            expanded_start = _common_start(fetched, expanded_codes)
            expanded = {
                "data_pass": True,
                "invalid_codes": [],
                "common_start": expanded_start,
                "result": run_scope(
                    fetched,
                    expanded_codes,
                    nominal_lots=False,
                    allocation_mode="fixed_slots",
                    start=expanded_start,
                ),
            }
        else:
            expanded = {
                "data_pass": False,
                "invalid_codes": invalid_codes,
                "common_start": None,
                "result": None,
                "verdict": "DATA_NO_GO",
            }

    if not data_pass:
        verdict = "DATA_NO_GO"
    elif gates["all_pass"]:
        # Historical ETF master/delistings are unavailable, and all dates have
        # already been inspected in B084. A positive result can only earn paper.
        verdict = "PAPER_ONLY"
    else:
        verdict = "NO_GO"
    diagnostic_gates = {
        key: value for key, value in gates["gates"].items() if key != "data_integrity"
    }
    diagnostic_signal_verdict = "PAPER_ONLY" if all(diagnostic_gates.values()) else "NO_GO"

    return {
        "study": "A-share ETF 12-month absolute-momentum strict B084 follow-up",
        "generated_on": "2026-07-12",
        "runner_sha256": _sha256_file(Path(__file__).resolve()),
        "research_boundary": {
            "research_only": True,
            "broker_calls": False,
            "product_code_changed": False,
            "historical_contamination": "C2-DIRECT: B084 dates and windows were already inspected",
            "pit_etf_master_available": False,
            "positive_result_ceiling": "PAPER_ONLY",
        },
        "frozen_protocol": {
            "signal": "12-month qfq close momentum > 0",
            "signal_time": "last complete month trading close",
            "execution": "next common trading-session open",
            "rebalance": "monthly",
            "selected_weighting": "equal weight; failed/locked buys remain cash; no replacement",
            "primary_allocation": (
                "five fixed 20% sleeves; negative or unavailable sleeve stays cash"
            ),
            "legacy_sensitivity": "positive signals renormalized to 100%, matching old B084 code",
            "cash_return": 0.0,
            "capital_cny": INITIAL_CAPITAL_CNY,
            "commission_bps_each_trade": COMMISSION_BPS,
            "slippage_bps_each_trade": SLIPPAGE_BPS,
            "minimum_commission_cny": MIN_COMMISSION_CNY,
            "lot_size": LOT_SIZE,
            "lot_model": (
                "target holdings rounded to nominal-open 100-share lots; existing holdings "
                "carry as total-return notionals, so trade shares/cost/capacity are an "
                "approximation rather than a full share ledger"
            ),
            "stamp_duty_bps": 0.0,
            "fund_fee_handling": "already embedded in ETF market total return; not deducted twice",
            "parameter_search": False,
        },
        "data": {
            "source": "Tencent qfq daily endpoint; raw Sina B084 close for nominal scale",
            "frozen_end": FROZEN_END,
            "validations": validations,
            "raw_b084_sha256": _sha256_file(RAW_B084),
            "raw_corporate_action_diagnostics": raw_corporate_action_diagnostics(
                raw, primary_frames
            ),
            "amount_field_crosscheck": amount_field_crosscheck(fetched["512890"]),
            "raw_nominal_full_coverage": raw_coverage,
            "raw_nominal_evaluation_coverage": evaluation_raw_coverage,
            "source_data_pass": source_data_pass,
            "common_history5_months": common_history_months,
            "common_history5_minimum_required": 60,
            "common_history5_pass": common_history_pass,
            "data_pass": data_pass,
            "amount_semantics": "Tencent row[8] * 10,000 CNY; retained before AkShare truncation",
        },
        "primary_b084_dynamic5": primary,
        "legacy_selected_full_weight_sensitivity": legacy_normalized,
        "primary_cost_sensitivities": cost_sensitivities,
        "legacy_core3_sensitivity": core3,
        "common_history5_sensitivity": {
            "common_start": common_start,
            "result": common5,
        },
        "expanded_current_survivors_sensitivity": expanded,
        "decision_gates": gates,
        "verdict": verdict,
        "diagnostic_signal_verdict": diagnostic_signal_verdict,
        "million_cny_target_lot_diagnostic_completed": source_data_pass,
        "exact_share_ledger_backtest_completed": False,
        "production_or_paper_adoption_allowed": verdict == "PAPER_ONLY",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-expanded", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.cache_dir, refresh=args.refresh, skip_expanded=args.skip_expanded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    args.out.write_text(payload, encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "verdict": report["verdict"],
                "primary_trend": report["primary_b084_dynamic5"]["trend"],
                "primary_hold": report["primary_b084_dynamic5"]["hold"],
                "gates": report["decision_gates"]["gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
