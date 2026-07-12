"""Data-readiness audit for a pure E/P enhancement inside H30269.

This evaluator-owned runner deliberately stops before signal returns or portfolio
construction.  It checks whether the repository can reproduce official H30269
historical membership/weights and point-in-time, as-filed earnings-to-price data
without survivorship, revision, industry, size, or execution lookahead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DATE = "2026-07-12"
INDEX_CODE = "H30269"
TR_INDEX_CODE = "H20269"
INITIAL_CAPITAL_CNY = 2_100_000.0

FUNDAMENTALS_PATH = (
    REPO_ROOT / "data/research/b068/snapshots/fundamentals/unified/fundamentals.csv"
)
UNIVERSE_PATH = (
    REPO_ROOT / "data/research/b070/snapshots/universe/cn_pit_universe.csv"
)
CONTROL_PATH = (
    REPO_ROOT
    / "data/research/b070/snapshots/universe/cn_pit_universe_current_control.csv"
)
PRICES_PATH = REPO_ROOT / "data/research/b070/snapshots/prices/unified/prices_daily.csv"
RAW_REPORTS_PATH = REPO_ROOT / "data/research/codex_quality_sue/raw_reports.csv.gz"
NOTICE_CROSSCHECK_PATH = (
    REPO_ROOT / "data/research/codex_quality_sue/notice_crosscheck_v2.json"
)
SIZE_PATH = REPO_ROOT / "data/research/b076/cn_size.csv"
UNIVERSE_BUILD_PATH = REPO_ROOT / "data/research/b070/f002_universe_build.json"
PRICE_INDEX_PATH = REPO_ROOT / "data/research/b082/index_h30269.csv"
TR_INDEX_PATH = REPO_ROOT / "data/research/b082/index_h20269.csv"
CN_FUNDAMENTALS_SOURCE = (
    REPO_ROOT / "workbench/backend/workbench_api/data_refresh/cn_fundamentals.py"
)

CSI_TOP10_URL = (
    "https://www.csindex.com.cn/csindex-home/index/weight/top10new/H30269"
)
CSI_SAMPLE_DATE_URL = (
    "https://www.csindex.com.cn/csindex-home/"
    "indexInfo/index-sample-information-trade-date-new"
)
CSI_MATERIAL_URL = (
    "https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data"
)
CSI_INDEX_DATA_PAGE = "https://www.csindex.com.cn/#/dataService/indexData"
CSI_VENDOR_PAGE = "https://www.csindex.com.cn/#/dataService/vendor"
CSI_DISCLAIMER_PAGE = "https://www.csindex.com.cn/#/disclaimer"
CNINFO_SEARCH_PAGE = (
    "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search"
)
CNINFO_ANNOUNCEMENT_API = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_COMMERCIAL_API = "http://webapi.cninfo.com.cn/"

DEFAULT_OUT = (
    REPO_ROOT
    / "docs/test-reports/ashare-dividend-ep-data-readiness-2026-07-12.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def discover_h30269_component_files(root: Path = REPO_ROOT / "data") -> list[str]:
    markers = ("cons", "weight", "member", "sample", "component")
    matches = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and INDEX_CODE.lower() in path.name.lower()
        and any(marker in path.name.lower() for marker in markers)
    ]
    labels: list[str] = []
    for path in matches:
        try:
            labels.append(str(path.relative_to(REPO_ROOT)))
        except ValueError:
            labels.append(str(path.relative_to(root)))
    return sorted(labels)


def parse_csi_top10(body: dict[str, Any], expected_code: str = INDEX_CODE) -> dict[str, Any]:
    data = body.get("data")
    if body.get("success") is not True or not isinstance(data, dict):
        raise ValueError("CSI top-10 response failed")
    rows = data.get("weightList")
    if not isinstance(rows, list) or len(rows) != 10:
        raise ValueError("CSI top-10 response must contain ten rows")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("indexCode")) != expected_code:
            raise ValueError("CSI top-10 index code mismatch")
        normalized.append(
            {
                "security_code": str(row["securityCode"]),
                "trade_date": str(row["tradeDate"]),
                "weight": float(row["weight"]),
            }
        )
    return {
        "update_date": str(data["updateDate"]),
        "rows": normalized,
        "canonical_data_sha256": canonical_json_hash(data),
    }


def request_validated(
    session: Any,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 45.0,
    attempts: int = 3,
    validator: Any | None = None,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            valid = validator(response) if validator else bool(response.content.strip())
            if not valid:
                raise ValueError(f"invalid or empty response from {url}")
            return response
        except Exception as exc:  # noqa: BLE001 - bounded external-source retry
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(
        f"request failed validation after {attempts} attempts: {url}"
    ) from last_error


def summarize_official_sheet(
    frame: pd.DataFrame, *, include_weight: bool
) -> dict[str, Any]:
    required = {"日期Date", "指数代码 Index Code", "成份券代码Constituent Code"}
    if include_weight:
        required.add("权重(%)weight")
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"CSI official sheet missing columns: {sorted(missing)}")
    codes = set(frame["指数代码 Index Code"].astype(str))
    if codes != {INDEX_CODE} or len(frame) != 50:
        raise ValueError(
            f"unexpected CSI official sheet identity: codes={codes}, rows={len(frame)}"
        )
    dates = pd.to_datetime(frame["日期Date"].astype(str), format="%Y%m%d", errors="coerce")
    if dates.isna().any() or dates.nunique() != 1:
        raise ValueError("CSI official sheet must have one valid as-of date")
    result: dict[str, Any] = {
        "rows": int(len(frame)),
        "as_of_date": dates.iloc[0].date().isoformat(),
        "distinct_constituents": int(frame["成份券代码Constituent Code"].nunique()),
    }
    if include_weight:
        weights = pd.to_numeric(frame["权重(%)weight"], errors="coerce")
        if weights.isna().any() or bool((weights <= 0).any()):
            raise ValueError("CSI official weight sheet contains invalid weights")
        result["weight_sum_pct"] = float(weights.sum())
    return result


def fetch_csi_public_probe(
    *, timeout: float = 45.0, session: Any = requests
) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.csindex.com.cn/"}
    current_response = request_validated(
        session, CSI_TOP10_URL, headers=headers, timeout=timeout
    )
    historical_response = request_validated(
        session,
        CSI_TOP10_URL,
        params={"tradeDate": "20141231"},
        headers=headers,
        timeout=timeout,
    )
    sample_date_response = request_validated(
        session,
        CSI_SAMPLE_DATE_URL,
        headers=headers,
        timeout=timeout,
        validator=lambda response: (
            len(response.text.strip()) == 8 and response.text.strip().isdigit()
        ),
    )
    material_response = request_validated(
        session,
        CSI_MATERIAL_URL,
        params={"fileLang": 2, "indexCode": INDEX_CODE},
        headers=headers,
        timeout=timeout,
    )
    material_body = material_response.json()
    material_data = material_body.get("data")
    if material_body.get("success") is not True or not isinstance(material_data, dict):
        raise ValueError("CSI material response failed")
    constituent_files = material_data.get("样本列表")
    weight_files = material_data.get("样本权重")
    if not isinstance(constituent_files, list) or len(constituent_files) != 1:
        raise ValueError("CSI material response has no unique constituent file")
    if not isinstance(weight_files, list) or len(weight_files) != 1:
        raise ValueError("CSI material response has no unique weight file")
    constituent_url = str(constituent_files[0]["filePath"])
    weight_url = str(weight_files[0]["filePath"])
    constituent_response = request_validated(
        session, constituent_url, timeout=timeout
    )
    weight_response = request_validated(session, weight_url, timeout=timeout)
    constituents = summarize_official_sheet(
        pd.read_excel(BytesIO(constituent_response.content)), include_weight=False
    )
    weights = summarize_official_sheet(
        pd.read_excel(BytesIO(weight_response.content)), include_weight=True
    )
    constituents |= {
        "url": constituent_url,
        "sha256": hashlib.sha256(constituent_response.content).hexdigest(),
        "last_modified": constituent_response.headers.get("Last-Modified"),
    }
    weights |= {
        "url": weight_url,
        "sha256": hashlib.sha256(weight_response.content).hexdigest(),
        "last_modified": weight_response.headers.get("Last-Modified"),
    }
    current = parse_csi_top10(current_response.json())
    historical = parse_csi_top10(historical_response.json())
    sample_date = sample_date_response.text.strip()
    if len(sample_date) != 8 or not sample_date.isdigit():
        raise ValueError(f"unexpected CSI sample date: {sample_date!r}")
    return {
        "current_top10": current,
        "historical_parameter_probe": historical,
        "requested_historical_trade_date": "2014-12-31",
        "historical_parameter_ignored": (
            current["canonical_data_sha256"] == historical["canonical_data_sha256"]
        ),
        "current_sample_information_date": pd.to_datetime(
            sample_date, format="%Y%m%d"
        ).date().isoformat(),
        "current_full_constituents": constituents,
        "latest_month_end_full_weights": weights,
        "material_response_sha256": canonical_json_hash(material_data),
        "interpretation": (
            "CSI publicly exposes the current full constituent list, latest month-end "
            "full weights and current top ten. The fixed file URLs roll forward, while "
            "supplying a past tradeDate returns the identical current top-ten payload; "
            "none of these endpoints supplies the 2013+ point-in-time archive."
        ),
        "urls": {
            "top10": CSI_TOP10_URL,
            "sample_information_date": CSI_SAMPLE_DATE_URL,
            "materials": CSI_MATERIAL_URL,
        },
    }


def summarize_fundamentals(frame: pd.DataFrame) -> dict[str, Any]:
    required = {
        "report_date",
        "ticker",
        "fiscal_quarter",
        "fiscal_quarter_end",
        "pe",
        "earnings_yield",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"fundamentals missing columns: {sorted(missing)}")
    data = frame.copy()
    data["report_date"] = pd.to_datetime(data["report_date"])
    data["pe"] = pd.to_numeric(data["pe"], errors="coerce")
    data["earnings_yield"] = pd.to_numeric(data["earnings_yield"], errors="coerce")
    comparable = data.dropna(subset=["pe", "earnings_yield"]).loc[
        lambda values: values["pe"].ne(0)
    ].copy()
    comparable["ep_to_inverse_pe_ratio"] = (
        comparable["earnings_yield"] * comparable["pe"]
    )
    comparable["quarter"] = comparable["fiscal_quarter"].str.extract(r"(Q[1-4])$")
    median_ratio = {
        str(quarter): float(group["ep_to_inverse_pe_ratio"].median())
        for quarter, group in comparable.groupby("quarter", sort=True)
    }
    sign_mismatches = int(
        (
            np.sign(comparable["earnings_yield"])
            != np.sign(1.0 / comparable["pe"])
        ).sum()
    )
    duplicate_mask = data.duplicated(["ticker", "report_date"], keep=False)
    return {
        "rows": int(len(data)),
        "tickers": int(data["ticker"].nunique()),
        "report_dates": int(data["report_date"].nunique()),
        "first_report_date": data["report_date"].min().date().isoformat(),
        "last_report_date": data["report_date"].max().date().isoformat(),
        "report_month_days": sorted(set(data["report_date"].dt.strftime("%m-%d"))),
        "duplicate_ticker_report_date_rows": int(duplicate_mask.sum()),
        "duplicate_ticker_report_date_keys": int(
            data.groupby(["ticker", "report_date"]).size().gt(1).sum()
        ),
        "earnings_yield_missing_fraction": float(data["earnings_yield"].isna().mean()),
        "ep_vs_inverse_pe_comparable_rows": int(len(comparable)),
        "ep_to_inverse_pe_median_ratio_by_quarter": median_ratio,
        "ep_vs_inverse_pe_sign_mismatches": sign_mismatches,
        "actual_announcement_date_column_present": (
            "actual_announcement_date" in data.columns
        ),
        "as_reported_version_column_present": "as_reported_version" in data.columns,
        "parent_net_profit_column_present": "parent_net_profit" in data.columns,
        "total_market_cap_column_present": "total_market_cap" in data.columns,
        "semantics": (
            "The producer maps report_date to statutory deadlines and computes "
            "earnings_yield as cumulative basic EPS divided by a nearby price. It is "
            "not four as-filed single-quarter parent-profit values over total market cap."
        ),
    }


def visible_ep_coverage(
    universe: pd.DataFrame, fundamentals: pd.DataFrame
) -> dict[str, Any]:
    members = universe.copy()
    members["as_of_date"] = pd.to_datetime(members["as_of_date"])
    fund = fundamentals.copy()
    fund["report_date"] = pd.to_datetime(fund["report_date"])
    fund = fund.dropna(subset=["earnings_yield"])
    union = set(members["ticker"].astype(str))
    covered_union = union & set(fund["ticker"].astype(str))
    rows: list[dict[str, Any]] = []
    for as_of, block in members.groupby("as_of_date", sort=True):
        names = set(block["ticker"].astype(str))
        visible = set(fund.loc[fund["report_date"] <= as_of, "ticker"].astype(str))
        count = len(names & visible)
        rows.append(
            {
                "as_of_date": as_of.date().isoformat(),
                "members": len(names),
                "covered": count,
                "coverage": count / len(names) if names else 0.0,
            }
        )
    values = [row["coverage"] for row in rows]
    return {
        "union_tickers": len(union),
        "covered_union_tickers": len(covered_union),
        "union_coverage": len(covered_union) / len(union) if union else 0.0,
        "per_date_min": min(values) if values else 0.0,
        "per_date_median": float(np.median(values)) if values else 0.0,
        "per_date_max": max(values) if values else 0.0,
        "per_date": rows,
    }


def summarize_universe(
    universe: pd.DataFrame, control: pd.DataFrame, fundamentals: pd.DataFrame
) -> dict[str, Any]:
    data = universe.copy()
    data["as_of_date"] = pd.to_datetime(data["as_of_date"])
    union = set(data["ticker"].astype(str))
    current = set(control["ticker"].astype(str))
    non_current = union - current
    fund_names = set(fundamentals["ticker"].astype(str))
    counts = data.groupby("as_of_date").size()
    return {
        "rows": int(len(data)),
        "rebalance_dates": int(data["as_of_date"].nunique()),
        "first_rebalance": data["as_of_date"].min().date().isoformat(),
        "last_rebalance": data["as_of_date"].max().date().isoformat(),
        "union_tickers": len(union),
        "members_per_date_min": int(counts.min()),
        "members_per_date_max": int(counts.max()),
        "current_control_tickers": len(current),
        "non_current_tickers": len(non_current),
        "non_current_with_b068_fundamentals": len(non_current & fund_names),
        "placeholder_columns_zero_fraction": {
            column: float(data[column].eq(0).mean())
            for column in ("market_cap", "avg_turnover", "composite_score")
        },
        "definition": (
            "Quarterly point-in-time union of CSI 300, CSI 500 and SSE 50; it is "
            "not H30269 membership and contains no official H30269 weights."
        ),
    }


def raw_report_coverage(
    reports: pd.DataFrame, universe: pd.DataFrame
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = reports.copy()
    data["REPORTDATE"] = pd.to_datetime(data["REPORTDATE"])
    data["NOTICE_DATE"] = pd.to_datetime(data["NOTICE_DATE"])
    notice_lag = (data["NOTICE_DATE"] - data["REPORTDATE"]).dt.days
    data = data.loc[
        data["SECUCODE"].astype(str).str.match(r"^\d{6}\.(SH|SZ)$", na=False)
        & notice_lag.between(0, 180)
    ]
    members = universe.copy()
    members["as_of_date"] = pd.to_datetime(members["as_of_date"])
    rows: list[dict[str, Any]] = []
    for as_of, block in members.groupby("as_of_date", sort=True):
        available = set(data.loc[data["REPORTDATE"].eq(as_of), "SECUCODE"].astype(str))
        names = set(block["ticker"].astype(str))
        count = len(names & available)
        rows.append(
            {
                "report_period": as_of.date().isoformat(),
                "members": len(names),
                "covered": count,
                "coverage": count / len(names) if names else 0.0,
            }
        )
    max_report_period = data["REPORTDATE"].max()
    eligible = [
        row
        for row in rows
        if pd.Timestamp(row["report_period"]) <= max_report_period
    ]
    values = [row["coverage"] for row in eligible]
    return rows, {
        "periods": len(eligible),
        "min": min(values) if values else 0.0,
        "median": float(np.median(values)) if values else 0.0,
        "max": max(values) if values else 0.0,
        "latest_available_report_period": max_report_period.date().isoformat(),
        "later_unavailable_universe_periods": [
            row["report_period"] for row in rows if row not in eligible
        ],
    }


def summarize_raw_reports(
    reports: pd.DataFrame,
    universe: pd.DataFrame,
    notice_crosscheck: dict[str, Any],
) -> dict[str, Any]:
    data = reports.copy()
    for column in ("REPORTDATE", "NOTICE_DATE", "UPDATE_DATE"):
        data[column] = pd.to_datetime(data[column])
    update_lag = (data["UPDATE_DATE"] - data["NOTICE_DATE"]).dt.days.dropna()
    notice_lag = (data["NOTICE_DATE"] - data["REPORTDATE"]).dt.days
    fresh_update_lag = update_lag.loc[notice_lag.between(0, 180)]
    coverage_rows, coverage_summary = raw_report_coverage(data, universe)
    return {
        "rows": int(len(data)),
        "tickers": int(data["SECUCODE"].nunique()),
        "first_report_period": data["REPORTDATE"].min().date().isoformat(),
        "last_report_period": data["REPORTDATE"].max().date().isoformat(),
        "first_notice_date": data["NOTICE_DATE"].min().date().isoformat(),
        "last_notice_date": data["NOTICE_DATE"].max().date().isoformat(),
        "parent_net_profit_missing_fraction": float(
            data["PARENT_NETPROFIT"].isna().mean()
        ),
        "notice_crosscheck": notice_crosscheck,
        "fresh_update_lag_days": {
            "median": float(fresh_update_lag.median()),
            "p90": float(fresh_update_lag.quantile(0.90)),
            "after_120d_fraction": float(fresh_update_lag.gt(120).mean()),
            "after_365d_fraction": float(fresh_update_lag.gt(365).mean()),
        },
        "b070_report_coverage": coverage_summary,
        "b070_report_coverage_by_period": coverage_rows,
        "archived_as_filed_values_available": False,
        "revision_blocker": (
            "NOTICE_DATE is independently cross-checked, but the cache stores one "
            "current historical value per ticker-period. Later corrections are not "
            "versioned, so current values cannot be assigned to the original notice date."
        ),
    }


def summarize_prices(prices: pd.DataFrame) -> dict[str, Any]:
    data = prices.copy()
    data["date"] = pd.to_datetime(data["date"])
    global_end = data["date"].max()
    final_dates = data.groupby("ticker")["date"].max()
    halted = data["tradestatus"].eq(0)
    return {
        "rows": int(len(data)),
        "tickers": int(data["ticker"].nunique()),
        "first_date": data["date"].min().date().isoformat(),
        "last_date": global_end.date().isoformat(),
        "halted_rows": int(halted.sum()),
        "tickers_with_halts": int(data.loc[halted, "ticker"].nunique()),
        "right_censored_tickers": int(final_dates.lt(global_end).sum()),
        "adj_close_equals_close_fraction": float(
            np.isclose(data["adj_close"], data["close"], equal_nan=True).mean()
        ),
        "corporate_action_fields_present": any(
            column in data.columns
            for column in ("adjust_factor", "cash_dividend", "split_factor", "total_shares")
        ),
    }


def summarize_size(size: pd.DataFrame) -> dict[str, Any]:
    data = size.copy()
    data["data_date"] = pd.to_datetime(data["data_date"])
    return {
        "rows": int(len(data)),
        "tickers": int(data["ticker"].nunique()),
        "first_date": data["data_date"].min().date().isoformat(),
        "last_date": data["data_date"].max().date().isoformat(),
        "field": "circulating market capitalization inferred from turnover",
        "standard_ep_total_market_cap_available": False,
    }


def assess_h30269_history(component_files: list[str]) -> dict[str, Any]:
    return {
        "candidate_files": component_files,
        "complete_2013_2026": False,
        "validated_effective_dates": 0,
        "all_dates_have_50_constituents": False,
        "all_dates_have_weights_summing_to_100pct": False,
        "temporary_adjustments_covered": False,
        "reason": (
            "No versioned H30269 archive is present. A future archive must be parsed "
            "and validated across every effective date before this gate can pass."
        ),
    }


def evaluate_data_gates(
    *,
    history_validation: dict[str, Any],
    fundamentals: dict[str, Any],
    h30269_ep_coverage_min: float | None,
    raw_reports: dict[str, Any],
    prices: dict[str, Any],
    size: dict[str, Any],
    pit_industry_available: bool,
    all_inputs_reproducible: bool,
) -> dict[str, Any]:
    crosscheck = raw_reports["notice_crosscheck"]
    gates = {
        "official_h30269_history_members_weights_2013_2026": history_validation[
            "complete_2013_2026"
        ],
        "actual_notice_dates_crosscheck_at_least_95pct": (
            crosscheck.get("comparable", 0) > 0
            and crosscheck.get("match_rate", 0.0) >= 0.95
        ),
        "archived_as_filed_parent_profit_versions_available": raw_reports[
            "archived_as_filed_values_available"
        ],
        "standard_ttm_parent_profit_over_total_market_cap_available": (
            fundamentals["parent_net_profit_column_present"]
            and fundamentals["total_market_cap_column_present"]
            and size["standard_ep_total_market_cap_available"]
        ),
        "h30269_pit_ep_coverage_each_rebalance_at_least_95pct": (
            h30269_ep_coverage_min is not None and h30269_ep_coverage_min >= 0.95
        ),
        "pit_industry_for_each_h30269_rebalance_available": pit_industry_available,
        "execution_and_corporate_actions_cover_primary_window": (
            prices["first_date"] <= "2013-12-31"
            and prices["corporate_action_fields_present"]
        ),
        "all_required_inputs_reproducible_from_fresh_clone": all_inputs_reproducible,
    }
    all_pass = all(gates.values())
    return {
        "gates": gates,
        "all_pass": all_pass,
        "verdict": "DATA_GO" if all_pass else "DATA_NO_GO",
        "portfolio_backtest_allowed": all_pass,
    }


def run(*, timeout: float = 60.0) -> dict[str, Any]:
    required_paths = [
        FUNDAMENTALS_PATH,
        UNIVERSE_PATH,
        CONTROL_PATH,
        PRICES_PATH,
        RAW_REPORTS_PATH,
        NOTICE_CROSSCHECK_PATH,
        SIZE_PATH,
        UNIVERSE_BUILD_PATH,
        PRICE_INDEX_PATH,
        TR_INDEX_PATH,
        CN_FUNDAMENTALS_SOURCE,
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required local audit inputs missing: {missing}")

    official_probe = fetch_csi_public_probe(timeout=timeout)
    fundamentals_frame = pd.read_csv(FUNDAMENTALS_PATH, dtype={"ticker": str})
    universe_frame = pd.read_csv(UNIVERSE_PATH, dtype={"ticker": str})
    control_frame = pd.read_csv(CONTROL_PATH, dtype={"ticker": str})
    raw_reports_frame = pd.read_csv(RAW_REPORTS_PATH, low_memory=False)
    notice_crosscheck = json.loads(NOTICE_CROSSCHECK_PATH.read_text(encoding="utf-8"))
    prices_frame = pd.read_csv(
        PRICES_PATH,
        usecols=["date", "ticker", "close", "adj_close", "tradestatus"],
        dtype={"ticker": str},
    )
    size_frame = pd.read_csv(SIZE_PATH, dtype={"ticker": str})
    fundamentals = summarize_fundamentals(fundamentals_frame)
    coverage = visible_ep_coverage(universe_frame, fundamentals_frame)
    universe = summarize_universe(universe_frame, control_frame, fundamentals_frame)
    raw_reports = summarize_raw_reports(
        raw_reports_frame, universe_frame, notice_crosscheck
    )
    prices = summarize_prices(prices_frame)
    size = summarize_size(size_frame)
    component_files = discover_h30269_component_files()
    history_validation = assess_h30269_history(component_files)
    ignored = {
        str(path.relative_to(REPO_ROOT)): git_ignored(path)
        for path in required_paths
        if str(path.relative_to(REPO_ROOT)).startswith("data/")
    }
    all_inputs_reproducible = not any(ignored.values())
    gate_result = evaluate_data_gates(
        history_validation=history_validation,
        fundamentals=fundamentals,
        h30269_ep_coverage_min=None,
        raw_reports=raw_reports,
        prices=prices,
        size=size,
        pit_industry_available=False,
        all_inputs_reproducible=all_inputs_reproducible,
    )

    index_price = pd.read_csv(PRICE_INDEX_PATH)
    index_tr = pd.read_csv(TR_INDEX_PATH)
    runner_path = Path(__file__).resolve()
    return {
        "research_id": "ashare_dividend_ep_data_readiness_2026_07_12",
        "run_date": RUN_DATE,
        "role": "evaluator_independent_strategy_research",
        "capital_cny": INITIAL_CAPITAL_CNY,
        "verdict": gate_result["verdict"],
        "returns_calculated": False,
        "hypothesis": (
            "Inside the official H30269 dividend-low-volatility membership, higher "
            "pure point-in-time earnings-to-price improves future compound return."
        ),
        "frozen_trial": {
            "primary_window": "2013-12-31..2026-06-30",
            "backcast_only_window": "2005-12-30..2013-12-18",
            "universe": (
                "Official effective H30269 historical constituents and weights at each "
                "annual review; current-member backfill and B070 substitution forbidden."
            ),
            "signal": (
                "Four latest publicly visible as-filed single-quarter parent net profits "
                "divided by signal-date total market capitalization."
            ),
            "construction": (
                "Within each PIT CSI level-1 industry, pair adjacent names by total market "
                "cap and transfer 50% of the lower-E/P name's baseline weight to the higher-"
                "E/P name, subject to the official 15% cap; industry weights remain exact."
            ),
            "execution": (
                "Signal after official rebalance effectiveness; next tradeable open, 100-"
                "share lots, no leverage, historical fees/taxes, dividends, halts, limits, "
                "delistings and corporate actions; each order <=1% ADV60."
            ),
            "return_priority_gates_after_data_go": {
                "post_publication_months": 120,
                "net_cagr_delta": 0.02,
                "sharpe_delta": 0.15,
                "max_drawdown_deterioration_limit": 0.03,
                "positive_chronological_folds": "at least 3 of 4",
                "newey_west_t": 1.65,
                "block_bootstrap_lower": "above zero",
            },
        },
        "data_gates": gate_result,
        "official_public_source_probe": official_probe,
        "repository_inventory": {
            "h30269_component_files": component_files,
            "h30269_history_validation": history_validation,
            "index_point_series_only": {
                "price_index": {
                    "path": str(PRICE_INDEX_PATH.relative_to(REPO_ROOT)),
                    "rows": int(len(index_price)),
                    "sha256": sha256_file(PRICE_INDEX_PATH),
                },
                "total_return_index": {
                    "path": str(TR_INDEX_PATH.relative_to(REPO_ROOT)),
                    "rows": int(len(index_tr)),
                    "sha256": sha256_file(TR_INDEX_PATH),
                },
            },
            "b068_fundamentals": fundamentals,
            "b068_to_b070_visible_ep_coverage": coverage,
            "b070_universe": universe,
            "actual_notice_report_cache": raw_reports,
            "b070_prices": prices,
            "b076_size": size,
            "gitignored_inputs": ignored,
        },
        "external_source_assessment": {
            "csi": {
                "index_data_page": CSI_INDEX_DATA_PAGE,
                "authorized_vendor_page": CSI_VENDOR_PAGE,
                "disclaimer": CSI_DISCLAIMER_PAGE,
                "assessment": (
                    "CSI provides current full constituents and latest month-end weights at "
                    "rolling fixed URLs. It identifies historical constituent weights, "
                    "corporate actions and index divisors as static data distributed through "
                    "its data-service platform or authorized vendors. Full historical H30269 "
                    "weights require a licensed delivery rather than current-page scraping."
                ),
            },
            "cninfo": {
                "announcement_search": CNINFO_SEARCH_PAGE,
                "public_query_api": CNINFO_ANNOUNCEMENT_API,
                "commercial_api": CNINFO_COMMERCIAL_API,
                "assessment": (
                    "Public announcements preserve IDs, timestamps and PDFs, including "
                    "corrections, but no verified free bulk structured as-filed TTM parent-"
                    "profit feed exists. Large reproducible extraction requires a licensed "
                    "API or a versioned PDF parsing and validation pipeline."
                ),
            },
            "market_cap": (
                "Official exchange OHLCV does not close the denominator: historical total "
                "shares, adjustment factors and cross-exchange delisted coverage are still "
                "required from 2013 onward."
            ),
        },
        "source_evidence": {
            str(path.relative_to(REPO_ROOT)): {
                "sha256": sha256_file(path),
                "gitignored": ignored.get(str(path.relative_to(REPO_ROOT)), False),
            }
            for path in required_paths
        }
        | {"runner_sha256": sha256_file(runner_path)},
        "blocking_requirements": [
            "Licensed H30269 effective historical constituents and weights from 2013 onward.",
            "Versioned as-filed parent net profit with exact first-public timestamps.",
            "PIT total shares/total market cap, industry and adjustment factors from 2013.",
            "Raw executable OHLCV, halts, limits, dividends, corporate actions and delistings.",
            "At least 95% member and E/P coverage at every rebalance, reproducible "
            "from a fresh clone.",
        ],
        "decision": (
            "Do not calculate or report pure E/P strategy returns. Current data would mix "
            "today's/restated financial values, a non-H30269 universe, circulating rather "
            "than total market cap, and a post-2018 execution panel, creating revision, "
            "membership, size and survivorship lookahead."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    report = run(timeout=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "returns_calculated": report["returns_calculated"],
                "out": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
