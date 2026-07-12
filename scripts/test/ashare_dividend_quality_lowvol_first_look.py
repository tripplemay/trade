"""Strict first-look for an A-share dividend-low-volatility quality enhancement.

The frozen candidate is the official CSI Dividend Growth Low Volatility Total
Return Index (H21130), compared with B082's CSI Dividend Low Volatility Total
Return Index (H20269).  The candidate was selected before examining returns
because it adds the closest official quality constraint (stable profit growth)
while preserving continuous dividends and low volatility.

The primary evidence begins at the last trading close in the candidate's
publication month.  History before publication is reported only as a backcast.
No index, window, blend, or parameter search is performed.

This evaluator-owned runner also audits whether the repository can support a
custom constituent-level quality/value enhancement and records material B082
baseline limitations.  It does not modify product strategy code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trade.backtest.cn_dividend_lowvol.engine import simulate_single_asset  # noqa: E402

RUN_DATE = "2026-07-12"
SOURCE_START = "20051230"
EVIDENCE_END = "20260630"
BASE_PRICE_CODE = "H30269"
BASE_TR_CODE = "H20269"
CANDIDATE_PRICE_CODE = "931130"
CANDIDATE_TR_CODE = "H21130"
CANDIDATE_PUBLICATION_DATE = pd.Timestamp("2018-12-04")
INITIAL_CAPITAL_CNY = 2_100_000.0
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_BLOCK_MONTHS = 6
BOOTSTRAP_SEED = 20260712
HAC_LAGS = 3

CSI_PERF_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CSI_META_URL = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info"
CSI_LIST_URL = "https://www.csindex.com.cn/csindex-home/exportExcel/indexAll/CH"

DEFAULT_OUT = (
    REPO_ROOT
    / "docs/test-reports/ashare-dividend-quality-lowvol-first-look-2026-07-12.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def parse_index_records(records: list[dict[str, Any]], expected_code: str) -> pd.Series:
    """Validate official CSI rows and return a unique, positive close series."""

    if not records:
        raise ValueError(f"CSI returned no rows for {expected_code}")
    frame = pd.DataFrame(records)
    required = {"tradeDate", "indexCode", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"CSI rows missing columns: {sorted(missing)}")
    codes = set(frame["indexCode"].dropna().astype(str))
    if codes != {expected_code}:
        raise ValueError(f"unexpected CSI codes for {expected_code}: {sorted(codes)}")
    frame["date"] = pd.to_datetime(frame["tradeDate"], format="%Y%m%d", errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date")
    frame = frame.drop_duplicates("date", keep="last")
    if frame.empty or bool((frame["close"] <= 0).any()):
        raise ValueError(f"nonpositive or empty CSI close series for {expected_code}")
    return frame.set_index("date")["close"].astype(float).rename(expected_code)


def fetch_index_series(
    code: str,
    *,
    start: str = SOURCE_START,
    end: str = EVIDENCE_END,
    timeout: float = 45.0,
    session: Any = requests,
) -> tuple[pd.Series, dict[str, Any]]:
    response = session.get(
        CSI_PERF_URL,
        params={"indexCode": code, "startDate": start, "endDate": end},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("success") is not True or not isinstance(body.get("data"), list):
        raise ValueError(f"CSI performance response failed for {code}: {body.get('msg')}")
    records = body["data"]
    series = parse_index_records(records, code)
    evidence = {
        "url": CSI_PERF_URL,
        "params": {"indexCode": code, "startDate": start, "endDate": end},
        "records": len(records),
        "first": series.index[0].date().isoformat(),
        "last": series.index[-1].date().isoformat(),
        "canonical_data_sha256": canonical_json_hash(records),
    }
    return series, evidence


def fetch_index_metadata(
    code: str, *, timeout: float = 45.0, session: Any = requests
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = f"{CSI_META_URL}/{code}"
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    data = body.get("data")
    if body.get("success") is not True or not isinstance(data, dict):
        raise ValueError(f"CSI metadata response failed for {code}: {body.get('msg')}")
    if str(data.get("indexCode")) != code:
        raise ValueError(f"CSI metadata code mismatch for {code}")
    return data, {"url": url, "canonical_data_sha256": canonical_json_hash(data)}


def parse_tracking_flag(frame: pd.DataFrame, code: str) -> dict[str, Any]:
    required = {"指数代码", "指数简称", "指数全称", "跟踪产品", "发布时间"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"CSI index list missing columns: {sorted(missing)}")
    codes = (
        frame["指数代码"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(6)
    )
    rows = frame.loc[codes == code]
    if len(rows) != 1:
        raise ValueError(f"expected one CSI list row for {code}, found {len(rows)}")
    row = rows.iloc[0]
    raw = str(row["跟踪产品"]).strip()
    if raw not in {"是", "否"}:
        raise ValueError(f"unexpected tracking-product flag for {code}: {raw!r}")
    return {
        "index_code": code,
        "short_name": str(row["指数简称"]),
        "full_name": str(row["指数全称"]),
        "official_tracking_product_flag": raw,
        "has_tracking_product": raw == "是",
        "publication_date": str(row["发布时间"]),
    }


def fetch_tracking_status(
    code: str, *, timeout: float = 60.0, session: Any = requests
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "sorter": {"sortField": "null", "sortOrder": None},
        "pager": {"pageNum": 1, "pageSize": 10},
        "indexFilter": {
            "ifCustomized": None,
            "ifTracked": None,
            "ifWeightCapped": None,
            "indexCompliance": None,
            "hotSpot": None,
            "indexClassify": None,
            "currency": None,
            "region": None,
            "indexSeries": ["1"],
            "undefined": None,
        },
    }
    response = session.post(
        CSI_LIST_URL,
        json=payload,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=timeout,
    )
    response.raise_for_status()
    frame = pd.read_excel(BytesIO(response.content))
    tracking = parse_tracking_flag(frame, code)
    return tracking, {
        "url": CSI_LIST_URL,
        "canonical_tracking_row_sha256": canonical_json_hash(tracking),
        "rows": int(len(frame)),
    }


def max_drawdown(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    if clean.empty:
        return 0.0
    return float((clean / clean.cummax() - 1.0).min())


def performance_metrics(values: pd.Series) -> dict[str, Any]:
    clean = values.dropna().astype(float)
    if len(clean) < 2:
        raise ValueError("performance window needs at least two observations")
    years = (clean.index[-1] - clean.index[0]).days / 365.25
    growth = float(clean.iloc[-1] / clean.iloc[0])
    daily = clean.pct_change().dropna()
    monthly = clean.resample("ME").last().pct_change().dropna()
    daily_std = float(daily.std(ddof=1))
    return {
        "start": clean.index[0].date().isoformat(),
        "end": clean.index[-1].date().isoformat(),
        "daily_observations": int(len(clean)),
        "months": int(len(monthly)),
        "years": float(years),
        "total_return": growth - 1.0,
        "cagr": growth ** (1.0 / years) - 1.0,
        "annualized_volatility": daily_std * math.sqrt(252.0),
        "sharpe_rf0": (
            float(daily.mean()) / daily_std * math.sqrt(252.0) if daily_std > 0 else 0.0
        ),
        "max_drawdown": max_drawdown(clean),
        "worst_month": float(monthly.min()) if len(monthly) else 0.0,
        "ending_value_cny_at_2_1m": INITIAL_CAPITAL_CNY * growth,
    }


def pair_window(
    aligned: pd.DataFrame, start: pd.Timestamp | str, end: pd.Timestamp | str
) -> dict[str, Any]:
    window = aligned.loc[pd.Timestamp(start) : pd.Timestamp(end)].dropna()
    if len(window) < 2:
        raise ValueError(f"empty comparison window {start}..{end}")
    base = performance_metrics(window["baseline"])
    candidate = performance_metrics(window["candidate"])
    return {
        "start": window.index[0].date().isoformat(),
        "end": window.index[-1].date().isoformat(),
        "baseline": base,
        "candidate": candidate,
        "delta": {
            "cagr": candidate["cagr"] - base["cagr"],
            "sharpe_rf0": candidate["sharpe_rf0"] - base["sharpe_rf0"],
            "max_drawdown_improvement": candidate["max_drawdown"] - base["max_drawdown"],
            "ending_value_cny_at_2_1m": (
                candidate["ending_value_cny_at_2_1m"]
                - base["ending_value_cny_at_2_1m"]
            ),
        },
    }


def newey_west_mean(series: pd.Series, lags: int = HAC_LAGS) -> dict[str, Any]:
    values = np.asarray(series.dropna(), dtype=float)
    n = len(values)
    if n < 2:
        return {"n": n, "mean": float(values.mean()) if n else 0.0, "se": None, "t": None}
    mean = float(values.mean())
    demeaned = values - mean
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    long_run = gamma0
    used_lags = min(max(0, lags), n - 1)
    for lag in range(1, used_lags + 1):
        gamma = float(np.dot(demeaned[lag:], demeaned[:-lag]) / n)
        weight = 1.0 - lag / (used_lags + 1.0)
        long_run += 2.0 * weight * gamma
    long_run = max(long_run, 0.0)
    se = math.sqrt(long_run / n)
    return {
        "n": n,
        "lags": used_lags,
        "mean": mean,
        "annualized_mean": mean * 12.0,
        "se": se,
        "t": mean / se if se > 0 else None,
    }


def block_bootstrap_mean_ci(
    series: pd.Series,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    block: int = BOOTSTRAP_BLOCK_MONTHS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    values = np.asarray(series.dropna(), dtype=float)
    n = len(values)
    if n == 0:
        raise ValueError("bootstrap series is empty")
    block = min(max(1, block), n)
    rng = np.random.default_rng(seed)
    means = np.empty(draws, dtype=float)
    blocks_needed = math.ceil(n / block)
    offsets = np.arange(block)
    for draw in range(draws):
        starts = rng.integers(0, n, size=blocks_needed)
        indices = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        means[draw] = float(values[indices].mean()) * 12.0
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "n": n,
        "draws": draws,
        "block_months": block,
        "seed": seed,
        "annualized_lower": float(lower),
        "annualized_upper": float(upper),
    }


def monthly_pair_returns(aligned: pd.DataFrame) -> pd.DataFrame:
    monthly = aligned.resample("ME").last().pct_change().dropna()
    monthly["excess"] = monthly["candidate"] - monthly["baseline"]
    return monthly


def chronological_folds(monthly: pd.DataFrame, k: int = 4) -> list[dict[str, Any]]:
    if len(monthly) < k:
        return []
    folds: list[dict[str, Any]] = []
    for number, indices in enumerate(np.array_split(np.arange(len(monthly)), k), start=1):
        part = monthly.iloc[indices]
        n_months = len(part)
        base_growth = float((1.0 + part["baseline"]).prod())
        candidate_growth = float((1.0 + part["candidate"]).prod())
        base_cagr = base_growth ** (12.0 / n_months) - 1.0
        candidate_cagr = candidate_growth ** (12.0 / n_months) - 1.0
        folds.append(
            {
                "fold": number,
                "start": part.index[0].date().isoformat(),
                "end": part.index[-1].date().isoformat(),
                "months": n_months,
                "baseline_cagr": base_cagr,
                "candidate_cagr": candidate_cagr,
                "cagr_delta": candidate_cagr - base_cagr,
            }
        )
    return folds


def window_diagnostics(
    aligned: pd.DataFrame, start: str, end: str
) -> dict[str, Any]:
    part = aligned.loc[pd.Timestamp(start) : pd.Timestamp(end)].dropna()
    if len(part) < 2:
        return {"start": start, "end": end, "available": False}
    output: dict[str, Any] = {"start": start, "end": end, "available": True}
    for column in ("baseline", "candidate"):
        values = part[column]
        output[column] = {
            "return": float(values.iloc[-1] / values.iloc[0] - 1.0),
            "max_drawdown": max_drawdown(values),
        }
    output["delta"] = {
        "return": output["candidate"]["return"] - output["baseline"]["return"],
        "max_drawdown_improvement": (
            output["candidate"]["max_drawdown"]
            - output["baseline"]["max_drawdown"]
        ),
    }
    return output


def annual_returns(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year, part in monthly.groupby(monthly.index.year):
        base = float((1.0 + part["baseline"]).prod() - 1.0)
        candidate = float((1.0 + part["candidate"]).prod() - 1.0)
        rows.append(
            {
                "year": int(year),
                "months": int(len(part)),
                "baseline": base,
                "candidate": candidate,
                "delta": candidate - base,
            }
        )
    return rows


def evaluate_index_gates(
    post_launch: dict[str, Any],
    inference: dict[str, Any],
    folds: list[dict[str, Any]],
    stress_windows: dict[str, dict[str, Any]],
    *,
    has_tracking_product: bool,
) -> dict[str, Any]:
    delta = post_launch["delta"]
    bootstrap = inference["block_bootstrap_95"]
    hac = inference["newey_west_hac"]
    positive_folds = sum(fold["cagr_delta"] > 0 for fold in folds)
    stress_ok = all(
        not block.get("available", False)
        or block["delta"]["max_drawdown_improvement"] >= -0.02
        for block in stress_windows.values()
    )
    gates = {
        "post_launch_months_at_least_60": post_launch["baseline"]["months"] >= 60,
        "cagr_delta_at_least_2pp": delta["cagr"] >= 0.02,
        "sharpe_delta_at_least_0_15": delta["sharpe_rf0"] >= 0.15,
        "max_drawdown_not_worse": delta["max_drawdown_improvement"] >= 0.0,
        "at_least_3_of_4_positive_folds": positive_folds >= 3,
        "hac_t_at_least_1_65": hac["t"] is not None and hac["t"] >= 1.65,
        "bootstrap_95_lower_above_zero": bootstrap["annualized_lower"] > 0.0,
        "stress_drawdown_not_worse_by_more_than_2pp": stress_ok,
        "official_tracking_product_exists": has_tracking_product,
    }
    return {
        "gates": gates,
        "positive_folds": positive_folds,
        "all_pass": all(gates.values()),
        "verdict": "GO" if all(gates.values()) else "NO_GO",
    }


def derive_overall_verdict(index_gate_result: dict[str, Any]) -> str:
    """The frozen official-index route controls this round's top-level verdict."""

    verdict = index_gate_result.get("verdict")
    if verdict not in {"GO", "NO_GO"}:
        raise ValueError(f"unexpected index gate verdict: {verdict!r}")
    return str(verdict)


def summarize_component_coverage(
    universe: pd.DataFrame, fundamentals: pd.DataFrame
) -> dict[str, Any]:
    universe = universe.copy()
    fundamentals = fundamentals.copy()
    universe["as_of_date"] = pd.to_datetime(universe["as_of_date"])
    fundamentals["report_date"] = pd.to_datetime(fundamentals["report_date"])
    union = set(universe["ticker"].astype(str))
    fund_names = set(fundamentals["ticker"].astype(str))
    per_date: list[dict[str, Any]] = []
    for as_of, block in universe.groupby("as_of_date", sort=True):
        members = set(block["ticker"].astype(str))
        visible = set(
            fundamentals.loc[fundamentals["report_date"] <= as_of, "ticker"].astype(str)
        )
        covered = len(members & visible)
        per_date.append(
            {
                "as_of_date": as_of.date().isoformat(),
                "members": len(members),
                "covered": covered,
                "coverage": covered / len(members) if members else 0.0,
            }
        )
    coverage_values = [row["coverage"] for row in per_date]
    return {
        "universe_rows": int(len(universe)),
        "universe_dates": int(universe["as_of_date"].nunique()),
        "universe_distinct_tickers": len(union),
        "fundamental_rows": int(len(fundamentals)),
        "fundamental_distinct_tickers": len(fund_names),
        "intersection_tickers": len(union & fund_names),
        "union_ticker_coverage": len(union & fund_names) / len(union) if union else 0.0,
        "per_date_coverage_min": min(coverage_values) if coverage_values else 0.0,
        "per_date_coverage_max": max(coverage_values) if coverage_values else 0.0,
        "per_date": per_date,
    }


def audit_component_data(root: Path = REPO_ROOT) -> dict[str, Any]:
    universe_path = root / "data/research/b070/snapshots/universe/cn_pit_universe.csv"
    fundamentals_path = (
        root / "data/research/b068/snapshots/fundamentals/unified/fundamentals.csv"
    )
    build_path = root / "data/research/b070/f002_universe_build.json"
    universe = pd.read_csv(universe_path)
    fundamentals = pd.read_csv(fundamentals_path)
    coverage = summarize_component_coverage(universe, fundamentals)
    build = json.loads(build_path.read_text(encoding="utf-8"))
    report_dates = pd.to_datetime(fundamentals["report_date"])
    duplicate_report_rows = int(
        fundamentals.duplicated(["ticker", "report_date"], keep=False).sum()
    )
    component_candidates = [
        str(path.relative_to(root))
        for path in (root / "data").rglob("*")
        if path.is_file()
        and "h30269" in path.name.lower()
        and any(token in path.name.lower() for token in ("cons", "weight", "member"))
    ]
    fields = {
        column: {
            "present": column in fundamentals.columns,
            "missing_fraction": (
                float(fundamentals[column].isna().mean())
                if column in fundamentals.columns
                else None
            ),
        }
        for column in (
            "roe",
            "gross_margin",
            "fcf_yield",
            "debt_to_assets",
            "pe",
            "pb",
            "ev_ebitda",
            "earnings_yield",
            "industry",
            "ttm_dividend_yield",
            "actual_announcement_date",
            "as_reported_version",
        )
    }
    gates = {
        "historical_h30269_components_and_weights_present": bool(component_candidates),
        "minimum_visible_fundamental_coverage_at_least_90pct": (
            coverage["per_date_coverage_min"] >= 0.90
        ),
        "industry_field_present": fields["industry"]["present"],
        "individual_dividend_field_present": fields["ttm_dividend_yield"]["present"],
        "actual_announcement_date_present": fields["actual_announcement_date"]["present"],
    }
    return {
        "route": "custom constituent-level quality/value enhancement",
        "coverage": coverage,
        "b070_build": {
            "rebalance_count": build["rebalance_count"],
            "current_member_count": build["current_member_count"],
            "union_ever_members": build["union_ever_members"],
            "non_current_members": build["non_current_members"],
        },
        "fundamental_report_date_month_days": sorted(
            set(report_dates.dt.strftime("%m-%d"))
        ),
        "duplicate_ticker_report_date_rows": duplicate_report_rows,
        "fields": fields,
        "historical_h30269_component_files": component_candidates,
        "gates": gates,
        "verdict": "GO" if all(gates.values()) else "DATA_NO_GO",
        "reason": (
            "B070 is a different broad-index universe; B068 fundamentals cover only a "
            "current-survivor subset and the repository has no historical H30269 members."
        ),
    }


def tier_weights(spread: pd.Series) -> pd.Series:
    values = pd.Series(0.25, index=spread.index, dtype=float)
    values.loc[spread >= 1.5] = 0.50
    values.loc[spread >= 2.5] = 1.00
    return values


def _cagr(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    years = (clean.index[-1] - clean.index[0]).days / 365.25
    return float((clean.iloc[-1] / clean.iloc[0]) ** (1.0 / years) - 1.0)


def audit_b082_baseline(root: Path = REPO_ROOT) -> dict[str, Any]:
    data_root = root / "data/research/b082"

    def load(name: str, column: str) -> pd.Series:
        frame = pd.read_csv(data_root / f"{name}.csv", parse_dates=["date"])
        return (
            frame.set_index("date")[column]
            .astype(float)
            .sort_index()
            .loc[lambda values: ~values.index.duplicated(keep="last")]
        )

    tr = load("index_h20269", "close")
    pr = load("index_h30269", "close")
    y10 = load("cn_10y_yield", "yield")
    etf = load("etf_512890", "close")
    legacy_json = json.loads(
        (data_root / "backtest_results.json").read_text(encoding="utf-8")
    )

    common = tr.index.intersection(pr.index)
    trc = tr.reindex(common)
    prc = pr.reindex(common)
    tr_growth = trc / trc.shift(252)
    pr_growth = prc / prc.shift(252)
    additive = ((tr_growth - 1.0) - (pr_growth - 1.0)).dropna() * 100.0
    relative = (tr_growth / pr_growth - 1.0).dropna() * 100.0
    add_y10 = y10.reindex(additive.index.union(y10.index)).ffill().reindex(additive.index)
    rel_y10 = y10.reindex(relative.index.union(y10.index)).ffill().reindex(relative.index)
    add_spread = (additive - add_y10).dropna().resample("ME").last().dropna()
    rel_spread = (relative - rel_y10).dropna().resample("ME").last().dropna()
    comparable_months = add_spread.index.intersection(rel_spread.index)
    add_tiers = tier_weights(add_spread.reindex(comparable_months))
    rel_tiers = tier_weights(rel_spread.reindex(comparable_months))
    first_signal = add_tiers.index[0]
    first_exec_position = tr.index.searchsorted(first_signal, side="right")
    first_execution = tr.index[first_exec_position]

    legacy_strategy = simulate_single_asset(tr, add_tiers, cost_model=None).equity
    strategy_common = legacy_strategy.loc[first_execution:]
    hold_common = tr.loc[first_execution:]
    official_base = tr.loc[pd.Timestamp("2005-12-30") :]

    diagnostic_dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    closes = pd.Series([10.0, 12.0, 12.0], index=diagnostic_dates)
    opens = pd.Series([10.0, 10.0, 12.0], index=diagnostic_dates)
    targets = pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    open_result = simulate_single_asset(
        closes, targets, initial_capital=1000.0, cost_model=None, exec_prices=opens
    )
    expected_open_execution_ending = 1200.0

    etf_monthly = etf.resample("ME").last().pct_change().dropna()
    worst_etf_month = etf_monthly.idxmin()
    tier_changes = int((add_tiers != rel_tiers).sum())
    legacy_primary = legacy_json["primary_index_tr"]
    issues = {
        "B082-AUDIT-1": {
            "severity": "high",
            "finding": "reported buy-and-hold waits through the signal warm-up",
            "legacy_reported_cagr": legacy_primary["buy_hold"]["cagr"],
            "official_base_date_buy_hold_cagr": _cagr(official_base),
            "common_execution_start_buy_hold_cagr": _cagr(hold_common),
            "common_execution_start_strategy_cagr": _cagr(strategy_common),
        },
        "B082-AUDIT-2": {
            "severity": "high",
            "finding": "ETF open execution loses the open-to-close P&L and can create leverage",
            "observed_ending_value": float(open_result.equity.iloc[-1]),
            "expected_ending_value": expected_open_execution_ending,
            "observed_execution_day_weight": float(open_result.weights.iloc[1]),
            "pass": math.isclose(
                float(open_result.equity.iloc[-1]), expected_open_execution_ending
            )
            and float(open_result.weights.iloc[1]) <= 1.0 + 1e-12,
        },
        "B082-AUDIT-3": {
            "severity": "medium",
            "finding": "additive TR-minus-PR is a material approximation to relative growth",
            "latest_additive_dividend_yield_pct": float(additive.iloc[-1]),
            "latest_relative_dividend_yield_pct": float(relative.iloc[-1]),
            "comparable_months": int(len(comparable_months)),
            "different_tier_months": tier_changes,
            "different_tier_fraction": tier_changes / len(comparable_months),
        },
        "B082-AUDIT-4": {
            "severity": "high",
            "finding": "unadjusted ETF series contains a corporate-action-like collapse",
            "worst_month": worst_etf_month.date().isoformat(),
            "worst_month_return": float(etf_monthly.loc[worst_etf_month]),
        },
    }
    return {
        "verdict": "BASELINE_NOT_EXECUTION_GRADE",
        "first_signal_date": first_signal.date().isoformat(),
        "first_execution_date": first_execution.date().isoformat(),
        "artifact_first_date": tr.index[0].date().isoformat(),
        "official_base_date": "2005-12-30",
        "legacy_report_window": legacy_primary.get("window"),
        "issues": issues,
        "rule_boundary": (
            "The frozen B082 additive spread and 25/50/100 tiers remain the legacy control. "
            "Changing the dividend-yield formula is a separate timing hypothesis."
        ),
    }


def local_source_hashes(root: Path = REPO_ROOT) -> dict[str, str]:
    paths = [
        "data/research/b068/snapshots/fundamentals/unified/fundamentals.csv",
        "data/research/b070/snapshots/universe/cn_pit_universe.csv",
        "data/research/b070/f002_universe_build.json",
        "data/research/b082/index_h20269.csv",
        "data/research/b082/index_h30269.csv",
        "data/research/b082/cn_10y_yield.csv",
        "data/research/b082/etf_512890.csv",
        "data/research/b082/backtest_results.json",
        "trade/strategies/cn_dividend_lowvol/signal.py",
        "trade/backtest/cn_dividend_lowvol/engine.py",
        "scripts/research/b082_dividend_lowvol_backtest.py",
    ]
    return {relative: sha256_file(root / relative) for relative in paths}


def run(*, timeout: float = 60.0) -> dict[str, Any]:
    baseline, baseline_source = fetch_index_series(BASE_TR_CODE, timeout=timeout)
    candidate, candidate_source = fetch_index_series(CANDIDATE_TR_CODE, timeout=timeout)
    base_meta, base_meta_source = fetch_index_metadata(BASE_PRICE_CODE, timeout=timeout)
    candidate_meta, candidate_meta_source = fetch_index_metadata(
        CANDIDATE_PRICE_CODE, timeout=timeout
    )
    tracking, tracking_source = fetch_tracking_status(
        CANDIDATE_PRICE_CODE, timeout=timeout
    )

    aligned = pd.concat(
        [baseline.rename("baseline"), candidate.rename("candidate")], axis=1
    ).dropna()
    aligned = aligned.loc[pd.Timestamp("2005-12-30") : pd.Timestamp("2026-06-30")]
    if aligned.empty:
        raise ValueError("official total-return series have no common history")
    publication = pd.Timestamp(candidate_meta["publishDate"])
    if publication != CANDIDATE_PUBLICATION_DATE:
        raise ValueError(
            f"candidate publication date drifted: {publication.date()} "
            f"!= {CANDIDATE_PUBLICATION_DATE.date()}"
        )
    publication_month_end = publication + pd.offsets.MonthEnd(0)
    post_start_candidates = aligned.loc[publication:publication_month_end]
    if post_start_candidates.empty:
        raise ValueError("candidate has no close in its publication month")
    post_start = post_start_candidates.index[-1]
    pre_end = aligned.index[aligned.index < publication][-1]

    backcast = pair_window(aligned, aligned.index[0], pre_end)
    post_launch = pair_window(aligned, post_start, aligned.index[-1])
    full = pair_window(aligned, aligned.index[0], aligned.index[-1])
    post_frame = aligned.loc[post_start:]
    monthly = monthly_pair_returns(post_frame)
    folds = chronological_folds(monthly, 4)
    inference = {
        "paired_months": int(len(monthly)),
        "monthly_win_rate": float((monthly["excess"] > 0).mean()),
        "monthly_return_correlation": float(
            monthly[["baseline", "candidate"]].corr().iloc[0, 1]
        ),
        "annualized_arithmetic_excess_mean": float(monthly["excess"].mean() * 12.0),
        "newey_west_hac": newey_west_mean(monthly["excess"], HAC_LAGS),
        "block_bootstrap_95": block_bootstrap_mean_ci(monthly["excess"]),
    }
    stress_windows = {
        "2022": window_diagnostics(aligned, "2022-01-01", "2022-12-31"),
        "2024_jan_feb": window_diagnostics(aligned, "2024-01-01", "2024-02-29"),
        "2025": window_diagnostics(aligned, "2025-01-01", "2025-12-31"),
    }
    gate_result = evaluate_index_gates(
        post_launch,
        inference,
        folds,
        stress_windows,
        has_tracking_product=tracking["has_tracking_product"],
    )
    component_data = audit_component_data()
    baseline_audit = audit_b082_baseline()
    overall_verdict = derive_overall_verdict(gate_result)
    runner_path = Path(__file__).resolve()
    return {
        "research_id": "ashare_dividend_quality_lowvol_first_look_2026_07_12",
        "run_date": RUN_DATE,
        "role": "evaluator_independent_strategy_research",
        "research_only": True,
        "no_broker_no_execution": True,
        "target_capital_cny": INITIAL_CAPITAL_CNY,
        "frozen_hypothesis": {
            "baseline": {
                "price_index_code": BASE_PRICE_CODE,
                "total_return_index_code": BASE_TR_CODE,
                "name": base_meta["indexFullNameCn"],
                "publication_date": base_meta["publishDate"],
                "adjustment_frequency": base_meta["adjFreqEn"],
                "description": base_meta["indexEnDesc"],
            },
            "candidate": {
                "price_index_code": CANDIDATE_PRICE_CODE,
                "total_return_index_code": CANDIDATE_TR_CODE,
                "name": candidate_meta["indexFullNameCn"],
                "publication_date": candidate_meta["publishDate"],
                "adjustment_frequency": candidate_meta["adjFreqEn"],
                "description": candidate_meta["indexEnDesc"],
                "theory": (
                    "Continuous dividends plus stable profit growth filters dividend traps; "
                    "low volatility retains the defensive mandate."
                ),
            },
            "selection_timing": (
                "conversation-level freeze before the first candidate-return fetch; "
                "the repository has no independently timestamped preregistration artifact"
            ),
            "parameter_search": False,
            "primary_window": (
                "last trading close in publication month through 2026-06-30"
            ),
            "prepublication_history_role": "backcast_only",
            "return_priority_gate": "post-launch CAGR delta >= 2 percentage points",
        },
        "official_sources": {
            BASE_TR_CODE: baseline_source,
            CANDIDATE_TR_CODE: candidate_source,
            BASE_PRICE_CODE: base_meta_source,
            CANDIDATE_PRICE_CODE: candidate_meta_source,
            "tracking_status": tracking_source,
        },
        "tracking_product": tracking,
        "official_index_comparison": {
            "common_start": aligned.index[0].date().isoformat(),
            "common_end": aligned.index[-1].date().isoformat(),
            "common_daily_observations": int(len(aligned)),
            "prepublication_backcast": backcast,
            "post_launch_primary": post_launch,
            "full_history_context": full,
            "backcast_to_post_launch_cagr_delta_decay": (
                post_launch["delta"]["cagr"] - backcast["delta"]["cagr"]
            ),
            "paired_monthly_inference": inference,
            "chronological_folds": folds,
            "annual_returns_post_launch": annual_returns(monthly),
            "stress_windows": stress_windows,
            "gates": gate_result,
            "verdict": gate_result["verdict"],
        },
        "custom_component_route": component_data,
        "legacy_b082_baseline_audit": baseline_audit,
        "overall_verdict": overall_verdict,
        "decision": (
            "Do not replace or augment B082 with the frozen dividend-growth low-vol "
            "candidate. Its post-launch return edge is absent, its drawdown is worse, "
            "and the official index currently has no tracking product. A bespoke Q/V "
            "route is DATA_NO_GO with the repository's current PIT coverage."
        ),
        "next_required_work": (
            "Before any constituent-level Q/V strategy, acquire historical H30269 "
            "members/weights, actual announcement-date as-reported fundamentals, industry, "
            "individual dividends, and raw plus total-return execution data. Separately, "
            "B082's warm-up baseline and ETF open execution require generator remediation."
        ),
        "next_hypothesis_not_tested": {
            "status": "preregistration_candidate_only",
            "name": "H30269 constituent-level earnings-to-price value enhancement",
            "rationale": (
                "H30269 already contains dividend continuity, payout, dividend-growth, and "
                "low-volatility quality screens. Direct A-share evidence is stronger for "
                "earnings-to-price than for another overlapping profitability composite."
            ),
            "boundary": (
                "This is a separate future trial after the component-data gate passes. It "
                "must not be selected as a winner inside the already-observed 931130 trial."
            ),
        },
        "limitations": [
            "Official index histories before publication are vendor backcasts, not live OOS.",
            "Index total returns are frictionless and cannot establish 2.1m execution capacity.",
            (
                "The frozen candidate has no official tracking product; "
                "no ETF cost ledger is possible."
            ),
            "All post-launch observations are historical and have now been inspected.",
        ],
        "source_hashes": {
            "runner_sha256": sha256_file(runner_path),
            "local_files": local_source_hashes(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    result = run(timeout=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    primary = result["official_index_comparison"]["post_launch_primary"]
    print(
        json.dumps(
            {
                "overall_verdict": result["overall_verdict"],
                "candidate_verdict": result["official_index_comparison"]["verdict"],
                "component_route": result["custom_component_route"]["verdict"],
                "post_launch_cagr_delta": primary["delta"]["cagr"],
                "post_launch_sharpe_delta": primary["delta"]["sharpe_rf0"],
                "post_launch_maxdd_improvement": primary["delta"][
                    "max_drawdown_improvement"
                ],
                "out": str(args.out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
