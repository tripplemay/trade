#!/usr/bin/env python
"""Independent A-share Quality + SUE signal first-look.

This evaluator-only runner deliberately stops before portfolio construction.  It
uses Eastmoney's structured earnings-report feed, the original ``NOTICE_DATE``
(not AkShare's misleading ``UPDATE_DATE`` mapping), the B070 point-in-time
membership snapshots, and the B070 survivorship-aware daily price panel.

Primary hypothesis (frozen before observing results): among companies passing a
simple contemporaneous quality constraint, higher time-series SUE predicts
higher returns from the first tradeable open after publication over N20, with
N60 as confirmation and N1 as a short-horizon control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data" / "research" / "codex_quality_sue"
RAW_CACHE = DATA_ROOT / "raw_reports.csv.gz"
CROSSCHECK_CACHE = DATA_ROOT / "notice_crosscheck_v2.json"
PRICE_CACHE = REPO_ROOT / "data" / "research" / "b070" / "b081_prices_cache.pkl"
SIZE_PATH = REPO_ROOT / "data" / "research" / "b076" / "cn_size.csv"
UNIVERSE_PATH = (
    REPO_ROOT / "data" / "research" / "b070" / "snapshots" / "universe" / "cn_pit_universe.csv"
)
DEFAULT_OUT = REPO_ROOT / "docs" / "test-reports" / "ashare-quality-sue-first-look-2026-07-11.json"

API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_NAME = "RPT_LICO_FN_CPD"
APPOINTMENT_REPORT_NAME = "RPT_PUBLIC_BS_APPOIN"
REPORT_FILTER = (
    "(REPORTDATE>='2014-03-31')(REPORTDATE<='2025-12-31')(SECURITY_TYPE_CODE=\"058001001\")"
)
RAW_COLUMNS = (
    "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORTDATE,NOTICE_DATE,"
    "UPDATE_DATE,BASIC_EPS,PARENT_NETPROFIT,WEIGHTAVG_ROE,XSMLL,MGJYXJJE,"
    "BOARD_CODE,BOARD_NAME,TRADE_MARKET_CODE,SECURITY_TYPE_CODE"
)
NUMERIC_COLUMNS = (
    "BASIC_EPS",
    "PARENT_NETPROFIT",
    "WEIGHTAVG_ROE",
    "XSMLL",
    "MGJYXJJE",
)
HORIZONS = (1, 20, 60)
MIN_MONTHLY_CROSS_SECTION = 20
MIN_VALID_MONTHS = 60
BOOTSTRAP_SAMPLES = 5_000
BOOTSTRAP_BLOCK_COHORTS = 6
BOOTSTRAP_SEED = 20260711


@dataclass(frozen=True, slots=True)
class UniverseSchedule:
    dates: pd.DatetimeIndex
    members: tuple[frozenset[str], ...]

    def members_on(self, timestamp: pd.Timestamp) -> frozenset[str]:
        position = int(self.dates.searchsorted(timestamp, side="right")) - 1
        return self.members[position] if position >= 0 else frozenset()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request_json(
    params: dict[str, str], *, attempts: int = 4, allow_empty: bool = False
) -> dict[str, Any]:
    import requests

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(API_URL, params=params, timeout=(10, 45))
            response.raise_for_status()
            payload = response.json()
            if allow_empty and payload.get("result") is None:
                return {"success": True, "result": {"data": [], "count": 0, "pages": 0}}
            if not payload.get("success") or payload.get("result") is None:
                raise RuntimeError(f"Eastmoney error: {payload.get('message')}")
            return payload
        except Exception as exc:  # noqa: BLE001 - bounded retry around external data
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"Eastmoney request failed after {attempts} attempts") from last_error


def _report_page_params(page: int, page_size: int) -> dict[str, str]:
    return {
        "sortColumns": "REPORTDATE,NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "1,1,1",
        "pageSize": str(page_size),
        "pageNumber": str(page),
        "reportName": REPORT_NAME,
        "columns": RAW_COLUMNS,
        "filter": REPORT_FILTER,
    }


def fetch_raw_reports(*, force: bool = False, workers: int = 8) -> pd.DataFrame:
    """Fetch and cache the structured actual-report panel."""

    if RAW_CACHE.is_file() and not force:
        return pd.read_csv(RAW_CACHE, low_memory=False)

    page_size = 500
    first = _request_json(_report_page_params(1, page_size))["result"]
    page_count = int(first["pages"])
    expected_count = int(first["count"])
    records: list[dict[str, Any]] = list(first.get("data") or [])

    def fetch_page(page: int) -> tuple[int, list[dict[str, Any]]]:
        result = _request_json(_report_page_params(page, page_size))["result"]
        return page, list(result.get("data") or [])

    completed = 1
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(fetch_page, page): page for page in range(2, page_count + 1)}
        for future in as_completed(futures):
            page, page_records = future.result()
            if not page_records and page < page_count:
                raise RuntimeError(f"empty non-terminal Eastmoney page {page}")
            records.extend(page_records)
            completed += 1
            if completed % 25 == 0 or completed == page_count:
                print(f"reports fetch: {completed}/{page_count} pages, {len(records)} rows")

    if len(records) != expected_count:
        raise RuntimeError(
            f"pagination count mismatch: expected {expected_count}, received {len(records)}"
        )
    frame = pd.DataFrame.from_records(records)
    missing = set(RAW_COLUMNS.split(",")) - set(frame.columns)
    if missing:
        raise RuntimeError(f"Eastmoney schema missing fields: {sorted(missing)}")
    frame = frame[list(RAW_COLUMNS.split(","))].sort_values(
        ["REPORTDATE", "NOTICE_DATE", "SECURITY_CODE"], kind="stable"
    )
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        RAW_CACHE,
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    return frame


def normalize_reports(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize raw records while preserving original and update timestamps."""

    frame = raw.copy()
    frame["ticker"] = frame["SECUCODE"].astype(str).str.upper()
    frame["report_date"] = pd.to_datetime(frame["REPORTDATE"], errors="coerce")
    frame["notice_date"] = pd.to_datetime(frame["NOTICE_DATE"], errors="coerce")
    frame["update_date"] = pd.to_datetime(frame["UPDATE_DATE"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    raw_rows = len(frame)
    parsed_notice_fraction = float(frame["notice_date"].notna().mean()) if raw_rows else 0.0
    frame = frame[
        frame["ticker"].str.match(r"^\d{6}\.(SH|SZ)$", na=False)
        & frame["report_date"].notna()
        & frame["notice_date"].notna()
    ].copy()
    frame["quarter"] = frame["report_date"].dt.quarter
    frame["period_index"] = frame["report_date"].dt.year * 4 + frame["quarter"]
    frame["announcement_lag_days"] = (frame["notice_date"] - frame["report_date"]).dt.days
    frame["update_lag_days"] = (frame["update_date"] - frame["notice_date"]).dt.days
    frame["fresh_report"] = frame["announcement_lag_days"].between(0, 180)

    duplicate_rows = int(frame.duplicated(["ticker", "report_date"], keep=False).sum())
    frame = (
        frame.sort_values(["ticker", "report_date", "update_date"], kind="stable")
        .drop_duplicates(["ticker", "report_date"], keep="last")
        .sort_values(["report_date", "ticker"], kind="stable")
        .reset_index(drop=True)
    )
    frame["quality_pass"] = (
        frame["WEIGHTAVG_ROE"].gt(0)
        & frame["MGJYXJJE"].gt(0)
        & (frame["XSMLL"].isna() | frame["XSMLL"].gt(0))
    )
    fresh_updates = frame.loc[frame["fresh_report"], "update_lag_days"].dropna()
    diagnostics = {
        "raw_rows": raw_rows,
        "normalized_rows": int(len(frame)),
        "unique_tickers": int(frame["ticker"].nunique()),
        "parsed_notice_fraction": parsed_notice_fraction,
        "duplicate_rows_before_dedup": duplicate_rows,
        "fresh_report_fraction": float(frame["fresh_report"].mean()),
        "notice_min": frame["notice_date"].min(),
        "notice_max": frame["notice_date"].max(),
        "fresh_update_lag_days": {
            "median": float(fresh_updates.median()),
            "p90": float(fresh_updates.quantile(0.90)),
            "after_120d_fraction": float(fresh_updates.gt(120).mean()),
            "after_365d_fraction": float(fresh_updates.gt(365).mean()),
        },
        "archived_as_filed_values_available": False,
    }
    return frame, diagnostics


def build_sue(reports: pd.DataFrame, *, value_column: str = "PARENT_NETPROFIT") -> pd.DataFrame:
    """Compute seasonal SUE from additive profit using strictly disclosed history."""

    frame = reports.sort_values(["ticker", "period_index"], kind="stable").copy()
    grouped = frame.groupby("ticker", sort=False)
    previous_value = grouped[value_column].shift(1)
    previous_period = grouped["period_index"].shift(1)
    previous_notice = grouped["notice_date"].shift(1)
    prior_quarter_available = previous_period.eq(frame["period_index"] - 1) & previous_notice.lt(
        frame["notice_date"]
    )
    frame["quarter_earnings"] = np.where(
        frame["quarter"].eq(1),
        frame[value_column],
        np.where(
            prior_quarter_available,
            frame[value_column] - previous_value,
            np.nan,
        ),
    )

    grouped = frame.groupby("ticker", sort=False)
    lag4_earnings = grouped["quarter_earnings"].shift(4)
    lag4_period = grouped["period_index"].shift(4)
    lag4_notice = grouped["notice_date"].shift(4)
    lag4_available = lag4_period.eq(frame["period_index"] - 4) & lag4_notice.lt(
        frame["notice_date"]
    )
    frame["unexpected_earnings"] = np.where(
        lag4_available,
        frame["quarter_earnings"] - lag4_earnings,
        np.nan,
    )

    scales = pd.Series(np.nan, index=frame.index, dtype=float)
    for positions in frame.groupby("ticker", sort=False).groups.values():
        ordered = list(positions)
        for offset, position in enumerate(ordered):
            current_period = int(frame.at[position, "period_index"])
            current_notice = frame.at[position, "notice_date"]
            prior_positions = ordered[max(0, offset - 8) : offset]
            prior_values = [
                float(frame.at[prior, "unexpected_earnings"])
                for prior in prior_positions
                if (
                    current_period - 8 <= int(frame.at[prior, "period_index"]) < current_period
                    and frame.at[prior, "notice_date"] < current_notice
                    and pd.notna(frame.at[prior, "unexpected_earnings"])
                )
            ]
            if len(prior_values) >= 6:
                scales.at[position] = float(np.std(prior_values, ddof=1))
    frame["sue_scale"] = scales
    frame["sue"] = frame["unexpected_earnings"] / frame["sue_scale"]
    frame.loc[~np.isfinite(frame["sue"]), "sue"] = np.nan
    return frame


def load_universe_schedule(path: Path = UNIVERSE_PATH) -> tuple[pd.DataFrame, UniverseSchedule]:
    universe = pd.read_csv(path, dtype={"ticker": str})
    universe["as_of_date"] = pd.to_datetime(universe["as_of_date"])
    universe["ticker"] = universe["ticker"].str.upper()
    grouped = universe.groupby("as_of_date", sort=True)["ticker"].agg(
        lambda values: frozenset(values)
    )
    return universe, UniverseSchedule(
        dates=pd.DatetimeIndex(grouped.index), members=tuple(grouped.tolist())
    )


def attach_pit_membership(events: pd.DataFrame, schedule: UniverseSchedule) -> pd.DataFrame:
    frame = events.copy()
    frame["pit_member"] = [
        ticker in schedule.members_on(pd.Timestamp(notice))
        for ticker, notice in zip(frame["ticker"], frame["notice_date"], strict=True)
    ]
    return frame


def coverage_by_period(
    reports: pd.DataFrame, universe: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Coverage against the B070 PIT membership snapshot at each quarter end."""

    max_report_date = reports["report_date"].max()
    snapshots = {
        pd.Timestamp(as_of): set(group["ticker"])
        for as_of, group in universe.groupby("as_of_date", sort=True)
        if pd.Timestamp(as_of) <= max_report_date
    }
    rows: list[dict[str, Any]] = []
    for as_of, members in snapshots.items():
        period = reports[reports["report_date"].eq(as_of) & reports["ticker"].isin(members)]
        fresh = period[period["fresh_report"]]
        quality_fields = fresh.dropna(subset=["WEIGHTAVG_ROE", "MGJYXJJE"])
        quality_pass_n = int(fresh.loc[fresh["quality_pass"], "ticker"].nunique())
        report_n = int(fresh["ticker"].nunique())
        rows.append(
            {
                "report_period": as_of,
                "universe_n": len(members),
                "report_n": report_n,
                "report_coverage": float(report_n / len(members)),
                "quality_field_n": int(quality_fields["ticker"].nunique()),
                "quality_field_coverage": float(quality_fields["ticker"].nunique() / len(members)),
                "quality_pass_n": quality_pass_n,
                "quality_pass_fraction_of_reports": float(
                    quality_pass_n / report_n if report_n else 0.0
                ),
                "sue_n": int(fresh.dropna(subset=["sue"])["ticker"].nunique()),
                "sue_coverage": float(
                    fresh.dropna(subset=["sue"])["ticker"].nunique() / len(members)
                ),
            }
        )
    table = pd.DataFrame(rows).sort_values("report_period")
    warm = table[table["report_period"].ge(pd.Timestamp("2019-03-31"))]

    def summarize(column: str) -> dict[str, float]:
        values = warm[column].dropna().to_numpy(dtype=float)
        return {
            "min": float(np.min(values)),
            "p10": float(np.quantile(values, 0.10)),
            "median": float(np.median(values)),
            "max": float(np.max(values)),
        }

    return table, {
        "periods": int(len(warm)),
        "report_coverage": summarize("report_coverage"),
        "quality_field_coverage": summarize("quality_field_coverage"),
        "quality_pass_fraction_of_reports": summarize("quality_pass_fraction_of_reports"),
        "sue_coverage": summarize("sue_coverage"),
    }


def _appointment_params(ticker: str, report_date: pd.Timestamp) -> dict[str, str]:
    report = report_date.strftime("%Y-%m-%d")
    code = ticker.split(".", 1)[0]
    return {
        "sortColumns": "FIRST_APPOINT_DATE",
        "sortTypes": "1",
        "pageSize": "20",
        "pageNumber": "1",
        "reportName": APPOINTMENT_REPORT_NAME,
        "columns": "ALL",
        "filter": f"(REPORT_DATE='{report}')(SECURITY_CODE=\"{code}\")",
    }


def crosscheck_notice_dates(
    reports: pd.DataFrame, *, force: bool = False, sample_size: int = 12
) -> dict[str, Any]:
    """Cross-check NOTICE_DATE against the independent actual-disclosure table."""

    if CROSSCHECK_CACHE.is_file() and not force:
        return json.loads(CROSSCHECK_CACHE.read_text(encoding="utf-8"))
    candidates = reports[
        reports["fresh_report"] & reports["notice_date"].between("2019-04-01", "2025-12-31")
    ].sort_values(["notice_date", "ticker"])
    positions = np.linspace(0, len(candidates) - 1, sample_size, dtype=int)
    sample = candidates.iloc[positions][["ticker", "report_date", "notice_date"]]

    def check(row: Any) -> dict[str, Any]:
        result = _request_json(_appointment_params(row.ticker, row.report_date), allow_empty=True)[
            "result"
        ]
        records = list(result.get("data") or [])
        actual = pd.to_datetime(
            records[0].get("ACTUAL_PUBLISH_DATE") if records else None, errors="coerce"
        )
        return {
            "ticker": row.ticker,
            "report_date": row.report_date.date().isoformat(),
            "notice_date": row.notice_date.date().isoformat(),
            "actual_publish_date": None if pd.isna(actual) else actual.date().isoformat(),
            "match": bool(
                not pd.isna(actual) and actual.normalize() == row.notice_date.normalize()
            ),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(check, sample.itertuples(index=False)))
    comparable = [item for item in checks if item["actual_publish_date"] is not None]
    payload = {
        "requested": sample_size,
        "comparable": len(comparable),
        "matches": sum(item["match"] for item in comparable),
        "match_rate": (
            sum(item["match"] for item in comparable) / len(comparable) if comparable else 0.0
        ),
        "samples": checks,
    }
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    CROSSCHECK_CACHE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def _limit_band(ticker: str, entry_date: pd.Timestamp) -> float:
    code = ticker[:6]
    if code.startswith("688"):
        return 0.20
    if code.startswith(("300", "301")) and entry_date >= pd.Timestamp("2020-08-24"):
        return 0.20
    return 0.10


def price_events(events: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Attach executable open-to-close forward returns and a pre-event placebo."""

    needed = ["date", "ticker", "open", "adj_close", "volume", "tradestatus"]
    panel = prices[needed].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    by_ticker = {
        ticker: group.sort_values("date").reset_index(drop=True)
        for ticker, group in panel.groupby("ticker", sort=False)
    }
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        history = by_ticker.get(event.ticker)
        if history is None:
            continue
        dates = history["date"].to_numpy(dtype="datetime64[ns]")
        position = int(np.searchsorted(dates, np.datetime64(event.notice_date), side="right"))
        while position < len(history):
            bar = history.iloc[position]
            if (
                int(bar["tradestatus"]) == 1
                and pd.notna(bar["open"])
                and float(bar["open"]) > 0
                and pd.notna(bar["adj_close"])
                and float(bar["adj_close"]) > 0
            ):
                break
            position += 1
        if position >= len(history):
            continue
        entry = history.iloc[position]
        record = {
            "ticker": event.ticker,
            "name": event.SECURITY_NAME_ABBR,
            "report_date": event.report_date,
            "notice_date": event.notice_date,
            "entry_date": entry["date"],
            "sue": float(event.sue),
            "quality_pass": bool(event.quality_pass),
            "industry": event.BOARD_NAME,
            "update_lag_days": event.update_lag_days,
        }
        previous_close = (
            float(history.iloc[position - 1]["adj_close"])
            if position > 0 and pd.notna(history.iloc[position - 1]["adj_close"])
            else np.nan
        )
        entry_open = float(entry["open"])
        opening_return = entry_open / previous_close - 1.0 if previous_close > 0 else np.nan
        record["limit_up"] = bool(
            np.isfinite(opening_return)
            and opening_return >= _limit_band(event.ticker, pd.Timestamp(entry["date"])) - 1e-6
        )
        record["entry_open_return"] = opening_return
        record["pre20_return"] = (
            previous_close / float(history.iloc[position - 21]["adj_close"]) - 1.0
            if position >= 21
            and pd.notna(history.iloc[position - 21]["adj_close"])
            and float(history.iloc[position - 21]["adj_close"]) > 0
            and previous_close > 0
            else np.nan
        )
        liquidity_slice = history.iloc[max(0, position - 20) : position]
        record["pre20_median_amount"] = float(
            (liquidity_slice["adj_close"] * liquidity_slice["volume"]).median()
        )
        for horizon in HORIZONS:
            target_exit_position = position + horizon - 1
            exit_position = target_exit_position
            while exit_position < len(history):
                exit_bar = history.iloc[exit_position]
                if (
                    int(exit_bar["tradestatus"]) == 1
                    and pd.notna(exit_bar["adj_close"])
                    and float(exit_bar["adj_close"]) > 0
                ):
                    break
                exit_position += 1
            exit_close = (
                float(history.iloc[exit_position]["adj_close"])
                if exit_position < len(history)
                and pd.notna(history.iloc[exit_position]["adj_close"])
                and float(history.iloc[exit_position]["adj_close"]) > 0
                else np.nan
            )
            record[f"ret_{horizon}"] = (
                exit_close / entry_open - 1.0 if np.isfinite(exit_close) else np.nan
            )
            record[f"exit_delay_{horizon}"] = (
                exit_position - target_exit_position if exit_position < len(history) else np.nan
            )
        rows.append(record)
    return pd.DataFrame(rows)


def attach_pit_size(events: pd.DataFrame, path: Path = SIZE_PATH) -> pd.DataFrame:
    """Attach the latest strictly historical B076 market cap for diagnostics."""

    size = pd.read_csv(path, dtype={"ticker": str})
    size["data_date"] = pd.to_datetime(size["data_date"])
    size["ticker"] = size["ticker"].str.upper()
    histories = {
        ticker: group.sort_values("data_date").reset_index(drop=True)
        for ticker, group in size.groupby("ticker", sort=False)
    }
    market_caps: list[float] = []
    for event in events.itertuples(index=False):
        history = histories.get(event.ticker)
        if history is None:
            market_caps.append(np.nan)
            continue
        dates = history["data_date"].to_numpy(dtype="datetime64[ns]")
        position = int(np.searchsorted(dates, np.datetime64(event.entry_date), side="left")) - 1
        market_caps.append(float(history.iloc[position]["market_cap"]) if position >= 0 else np.nan)
    frame = events.copy()
    frame["pit_market_cap"] = market_caps
    return frame


def _monthly_cross_section(events: pd.DataFrame, return_column: str) -> pd.DataFrame:
    frame = events.dropna(subset=["sue", return_column]).copy()
    frame["month"] = frame["entry_date"].dt.to_period("M").dt.to_timestamp()
    return (
        frame.sort_values(["month", "ticker", "notice_date", "report_date"], kind="stable")
        .drop_duplicates(["month", "ticker"], keep="last")
        .reset_index(drop=True)
    )


def _monthly_ic_table(events: pd.DataFrame, return_column: str) -> pd.DataFrame:
    frame = _monthly_cross_section(events, return_column)
    rows: list[dict[str, Any]] = []
    for month, cohort in frame.groupby("month", sort=True):
        if len(cohort) < MIN_MONTHLY_CROSS_SECTION:
            continue
        ic = cohort["sue"].rank(method="average").corr(cohort[return_column].rank(method="average"))
        rows.append({"month": month, "ic": float(ic), "n": int(len(cohort))})
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
    if len(sample) < BOOTSTRAP_BLOCK_COHORTS:
        return {"ci_low": np.nan, "ci_high": np.nan, "prob_positive": np.nan}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = np.arange(len(sample))
    means = np.empty(BOOTSTRAP_SAMPLES)
    for iteration in range(BOOTSTRAP_SAMPLES):
        selected: list[float] = []
        while len(selected) < len(sample):
            start = int(rng.choice(starts))
            selected.extend(
                sample[(start + offset) % len(sample)] for offset in range(BOOTSTRAP_BLOCK_COHORTS)
            )
        means[iteration] = float(np.mean(selected[: len(sample)]))
    return {
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
        "prob_positive": float(np.mean(means > 0)),
    }


def _fold_means(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    if monthly.empty:
        return []
    chunks = np.array_split(np.arange(len(monthly)), 3)
    rows = []
    for number, positions in enumerate(chunks, start=1):
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


def _year_means(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    if monthly.empty:
        return []
    grouped = monthly.assign(year=monthly["month"].dt.year).groupby("year", sort=True)
    return [
        {"year": int(year), "months": int(len(group)), "mean_ic": float(group["ic"].mean())}
        for year, group in grouped
    ]


def _quintile_summary(events: pd.DataFrame, return_column: str) -> dict[str, Any]:
    frame = _monthly_cross_section(events, return_column)
    month_rows: list[dict[int, float]] = []
    for _, cohort in frame.groupby("month", sort=True):
        if len(cohort) < MIN_MONTHLY_CROSS_SECTION:
            continue
        ranked = cohort["sue"].rank(method="average", pct=True)
        cohort = cohort.assign(quintile=np.ceil(ranked * 5).clip(1, 5).astype(int))
        values = cohort.groupby("quintile")[return_column].mean().to_dict()
        if len(values) == 5:
            month_rows.append({int(key): float(value) for key, value in values.items()})
    if not month_rows:
        return {"months": 0, "means": {}, "q5_minus_q1": None, "monotonic_rank_corr": None}
    means = {str(q): float(np.mean([row[q] for row in month_rows])) for q in range(1, 6)}
    ordered = np.array([means[str(q)] for q in range(1, 6)], dtype=float)
    rank_corr = float(pd.Series(range(1, 6)).corr(pd.Series(ordered).rank()))
    return {
        "months": len(month_rows),
        "means": means,
        "q5_minus_q1": float(ordered[-1] - ordered[0]),
        "monotonic_rank_corr": rank_corr,
    }


def analyze_variant(events: pd.DataFrame) -> dict[str, Any]:
    executable = events[~events["limit_up"]].copy()
    event_month = executable["entry_date"].dt.to_period("M")
    ticker_month_excess = int(
        len(executable)
        - executable.assign(_event_month=event_month)
        .drop_duplicates(["_event_month", "ticker"])
        .shape[0]
    )
    result: dict[str, Any] = {
        "events": int(len(events)),
        "executable_events": int(len(executable)),
        "limit_up_fraction": float(events["limit_up"].mean()) if len(events) else None,
        "unique_tickers": int(executable["ticker"].nunique()),
        "ticker_month_duplicate_excess": ticker_month_excess,
        "entry_start": executable["entry_date"].min() if len(executable) else None,
        "entry_end": executable["entry_date"].max() if len(executable) else None,
        "horizons": {},
    }
    for horizon in HORIZONS:
        column = f"ret_{horizon}"
        monthly = _monthly_ic_table(executable, column)
        stats = _hac_mean(monthly["ic"].to_numpy() if len(monthly) else np.array([]))
        result["horizons"][f"N{horizon}"] = {
            "valid_events": int(executable[column].notna().sum()),
            "valid_months": int(len(monthly)),
            "monthly_cross_section_observations": int(monthly["n"].sum()),
            "delayed_exit_events": int(executable[f"exit_delay_{horizon}"].gt(0).sum()),
            "max_exit_delay_sessions": int(executable[f"exit_delay_{horizon}"].dropna().max()),
            "hac": stats,
            "block_bootstrap": _block_bootstrap(
                monthly["ic"].to_numpy() if len(monthly) else np.array([])
            ),
            "folds": _fold_means(monthly),
            "years": _year_means(monthly),
            "quintiles": _quintile_summary(executable, column),
        }
    placebo = _monthly_ic_table(executable, "pre20_return")
    result["pre20_placebo"] = {
        "valid_months": int(len(placebo)),
        "hac": _hac_mean(placebo["ic"].to_numpy() if len(placebo) else np.array([])),
        "block_bootstrap": _block_bootstrap(
            placebo["ic"].to_numpy() if len(placebo) else np.array([])
        ),
    }
    return result


def exposure_diagnostics(events: pd.DataFrame) -> dict[str, Any]:
    frame = events[~events["limit_up"]].copy()
    frame["sue_decile"] = np.ceil(frame["sue"].rank(method="average", pct=True) * 10).clip(1, 10)
    top = frame[frame["sue_decile"].eq(10)]
    industry = top["industry"].fillna("UNKNOWN").value_counts(normalize=True).head(10)
    liquidity = frame.groupby("sue_decile")["pre20_median_amount"].median()
    market_cap = frame.groupby("sue_decile")["pit_market_cap"].median()
    return {
        "top_decile_industry_current_labels": {
            str(key): float(value) for key, value in industry.items()
        },
        "top_decile_industry_concentration_top10": float(industry.sum()),
        "median_pre20_traded_amount_by_sue_decile": {
            str(int(key)): float(value) for key, value in liquidity.items()
        },
        "median_pit_market_cap_by_sue_decile": {
            str(int(key)): float(value) for key, value in market_cap.items()
        },
        "pit_market_cap_coverage": float(frame["pit_market_cap"].notna().mean()),
        "industry_caveat": (
            "BOARD_NAME is a current classification, diagnostic-only and not used by the signal"
        ),
    }


def _placebo_gate_passes(mean_ic: float | None) -> bool:
    return mean_ic is not None and math.isfinite(mean_ic) and abs(mean_ic) < 0.03


def evaluate_gates(
    diagnostics: dict[str, Any],
    coverage: dict[str, Any],
    crosscheck: dict[str, Any],
    quality: dict[str, Any] | None,
) -> dict[str, Any]:
    data_gates = {
        "notice_parse_ge_99pct": diagnostics["parsed_notice_fraction"] >= 0.99,
        "notice_crosscheck_ge_95pct": (
            crosscheck["comparable"] >= 8 and crosscheck["match_rate"] >= 0.95
        ),
        "report_coverage_p10_ge_70pct": coverage["report_coverage"]["p10"] >= 0.70,
        "report_coverage_min_ge_70pct": coverage["report_coverage"]["min"] >= 0.70,
        "quality_field_coverage_p10_ge_70pct": (coverage["quality_field_coverage"]["p10"] >= 0.70),
        "quality_field_coverage_min_ge_70pct": (coverage["quality_field_coverage"]["min"] >= 0.70),
        "sue_coverage_p10_ge_70pct": coverage["sue_coverage"]["p10"] >= 0.70,
        "sue_coverage_min_ge_70pct": coverage["sue_coverage"]["min"] >= 0.70,
        "archived_as_filed_values_available": diagnostics["archived_as_filed_values_available"],
    }
    signal_gates: dict[str, bool] = {}
    if quality is not None:
        n20 = quality["horizons"]["N20"]
        n60 = quality["horizons"]["N60"]
        pre20 = quality["pre20_placebo"]
        fold_positive = sum(fold["mean_ic"] > 0 for fold in n20["folds"])
        signal_gates = {
            "at_least_60_valid_months": (
                min(n20["valid_months"], n60["valid_months"]) >= MIN_VALID_MONTHS
            ),
            "n20_mean_ic_ge_003": (n20["hac"]["mean"] or -math.inf) >= 0.03,
            "n20_bootstrap_ci_above_zero": n20["block_bootstrap"]["ci_low"] > 0,
            "n60_same_positive_sign": (n60["hac"]["mean"] or -math.inf) > 0,
            "n20_two_of_three_folds_positive": fold_positive >= 2,
            "n20_q5_minus_q1_positive": (n20["quintiles"]["q5_minus_q1"] or -math.inf) > 0,
            "pre20_placebo_abs_ic_lt_003": _placebo_gate_passes(pre20["hac"]["mean"]),
        }
    data_pass = all(data_gates.values())
    signal_pass = bool(signal_gates) and all(signal_gates.values())
    verdict = (
        "RESEARCH_GO"
        if data_pass and signal_pass
        else ("SIGNAL_NO_GO" if data_pass else "DATA_NO_GO")
    )
    return {
        "data": data_gates,
        "signal": signal_gates,
        "data_pass": data_pass,
        "signal_pass": signal_pass,
        "verdict": verdict,
        "portfolio_backtest_allowed": bool(data_pass and signal_pass),
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


def run(*, force: bool = False, workers: int = 8) -> dict[str, Any]:
    raw = fetch_raw_reports(force=force, workers=workers)
    reports, raw_diagnostics = normalize_reports(raw)
    reports = build_sue(reports)
    universe, schedule = load_universe_schedule()
    coverage_table, coverage = coverage_by_period(reports, universe)
    pit_report_pool = reports[reports["notice_date"].ge(schedule.dates.min())].copy()
    pit_report_pool = attach_pit_membership(pit_report_pool, schedule)
    crosscheck = crosscheck_notice_dates(
        pit_report_pool[pit_report_pool["pit_member"]], force=force
    )

    candidates = pit_report_pool[
        pit_report_pool["fresh_report"]
        & pit_report_pool["sue"].notna()
        & pit_report_pool["pit_member"]
    ].copy()
    prices = pd.read_pickle(PRICE_CACHE)
    priced = attach_pit_size(price_events(candidates, prices))
    market_dates = pd.DatetimeIndex(pd.to_datetime(prices["date"]).drop_duplicates().sort_values())
    n60_cutoff = market_dates[-60]
    n60_missing = priced["ret_60"].isna()
    n60_right_censored = n60_missing & priced["entry_date"].gt(n60_cutoff)
    common = priced.dropna(subset=["ret_1", "ret_20", "ret_60"]).copy()
    unfiltered = analyze_variant(priced)
    quality_sample = priced[priced["quality_pass"]].copy()
    quality = analyze_variant(quality_sample)
    quality_common = analyze_variant(common[common["quality_pass"]].copy())

    gates = evaluate_gates(raw_diagnostics, coverage, crosscheck, quality)
    payload = {
        "study": "A-share Quality + time-series SUE first-look",
        "analysis_date": "2026-07-11",
        "protocol": {
            "actual_report_period": "2014Q1..2025Q4",
            "evaluation_universe": "latest B070 PIT 800-member snapshot at NOTICE_DATE",
            "event_time": (
                "Eastmoney raw NOTICE_DATE; entry is first tradestatus=1 open strictly after notice"
            ),
            "sue": (
                "(discrete quarterly parent net profit - lag-4 profit) / std of prior 8 seasonal "
                "differences; min 6; scale shifted one quarter"
            ),
            "quality": "ROE>0 and operating-cash-flow/share>0 and (gross-margin missing or >0)",
            "primary": "quality-constrained N20 monthly cross-sectional rank-IC",
            "sample_policy": (
                "Each horizon uses its own available labels; the common N1/N20/N60 "
                "sample is reported as a fixed sensitivity."
            ),
            "confirmation": "N60; N1 short-horizon control; pre20 leakage placebo",
            "inference": (
                "Newey-West lag 3 plus circular 6-observed-cohort block bootstrap, 5000 draws"
            ),
            "no_parameter_sweep": True,
        },
        "inputs": {
            "raw_cache": str(RAW_CACHE.relative_to(REPO_ROOT)),
            "raw_cache_sha256": _sha256(RAW_CACHE),
            "price_cache": str(PRICE_CACHE.relative_to(REPO_ROOT)),
            "price_cache_sha256": _sha256(PRICE_CACHE),
            "size_data": str(SIZE_PATH.relative_to(REPO_ROOT)),
            "size_data_sha256": _sha256(SIZE_PATH),
            "universe": str(UNIVERSE_PATH.relative_to(REPO_ROOT)),
            "universe_sha256": _sha256(UNIVERSE_PATH),
            "script_sha256": _sha256(Path(__file__)),
        },
        "data_reality": {
            **raw_diagnostics,
            "coverage": coverage,
            "coverage_by_period": coverage_table.to_dict("records"),
            "notice_crosscheck": crosscheck,
            "historical_consensus": (
                "unavailable: stock_profit_forecast_em is current-only and has no "
                "observation timestamp"
            ),
            "revision_blocker": (
                "NOTICE_DATE is PIT-crosschecked, but the free endpoint has no "
                "archived as-filed report versions. Current historical values may "
                "reflect later corrections, so formal PIT SUE is unavailable."
            ),
        },
        "sample": {
            "sue_candidates_before_pit": int(
                len(reports[reports["fresh_report"] & reports["sue"].notna()])
            ),
            "pit_candidates": int(len(candidates)),
            "priced_events": int(len(priced)),
            "n60_missing": int(n60_missing.sum()),
            "n60_right_censored": int(n60_right_censored.sum()),
            "n60_path_ended_or_missing": int((n60_missing & ~n60_right_censored).sum()),
            "n60_complete_entry_cutoff": n60_cutoff,
            "common_complete_horizon_events": int(len(common)),
            "quality_events": int(len(quality_sample)),
            "common_quality_events": int(common["quality_pass"].sum()),
            "quality_fraction": (float(len(quality_sample) / len(priced)) if len(priced) else None),
        },
        "variants": {
            "unfiltered_sue_control": unfiltered,
            "quality_sue_primary": quality,
            "quality_sue_common_horizon_sensitivity": quality_common,
        },
        "exposures": exposure_diagnostics(quality_sample),
        "gates": gates,
        "interpretation_limits": [
            (
                "Signal first-look only: no portfolio construction, costs, capacity, "
                "or capital simulation."
            ),
            (
                "Free source has no archived as-filed value snapshots; all signal "
                "statistics are degraded diagnostics and cannot authorize a "
                "portfolio backtest."
            ),
            "B070 PIT universe is a liquid 800-name subset, not full A-share coverage.",
            (
                "B076 monthly market cap is used only as a lagged exposure diagnostic, "
                "not as a signal input."
            ),
            (
                "Historical ST status is unavailable; the limit-up diagnostic uses "
                "normal-board 10%/20% bands."
            ),
            (
                "Current industry labels and current security names are diagnostics "
                "only and are not signal inputs."
            ),
        ],
    }
    return _jsonable(payload)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Refetch external report data.")
    parser.add_argument("--workers", type=int, default=8, help="Bounded Eastmoney page workers.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run(force=args.force, workers=args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"out": str(args.out), "verdict": payload["gates"]["verdict"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
