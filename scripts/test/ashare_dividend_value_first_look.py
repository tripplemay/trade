"""Strict first-look for an official A-share dividend-value alternative.

The frozen candidate is the CSI Dividend Value Total Return Index (H20270),
compared with the CSI Dividend Low Volatility Total Return Index (H20269).
H30270 replaces the final one-year low-volatility ranking with a composite
BP/EP/CFP value ranking; it is not a pure E/P enhancement of H30269.

The primary evidence starts at the last trading close in the common
publication month.  Pre-publication history is reported only as a backcast.
This evaluator-owned runner does not modify product strategy code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test import ashare_dividend_quality_lowvol_first_look as common  # noqa: E402

RUN_DATE = "2026-07-12"
SOURCE_START = "20051230"
EVIDENCE_END = "20260630"
BASE_PRICE_CODE = "H30269"
BASE_TR_CODE = "H20269"
CANDIDATE_PRICE_CODE = "H30270"
CANDIDATE_TR_CODE = "H20270"
COMMON_PUBLICATION_DATE = pd.Timestamp("2013-12-19")
TARGET_ETF_CODE = "563700"
TARGET_ETF_SYMBOL = "sh563700"
INITIAL_CAPITAL_CNY = 2_100_000.0
ADV_DAYS = 60

CSI_PRODUCTS_URL = (
    "https://www.csindex.com.cn/csindex-home/index-list/queryByIndexCode"
)
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SSE_FUND_QUERY_URL = "https://query.sse.com.cn/commonSoaQuery.do"
BASE_METHODOLOGY_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/"
    "detail/files/zh_CN/H30269_Index_Methodology_cn.pdf"
)
CANDIDATE_METHODOLOGY_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/"
    "detail/files/zh_CN/1013_H30270_Index_Methodology_cn.pdf"
)
FUND_MANAGER_URL = "https://www.efunds.com.cn/fund/563700.shtml"

DEFAULT_OUT = (
    REPO_ROOT
    / "docs/test-reports/ashare-dividend-value-first-look-2026-07-12.json"
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


def fetch_methodology(
    url: str, *, timeout: float = 60.0, session: Any = requests
) -> dict[str, Any]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.content
    if not payload.startswith(b"%PDF"):
        raise ValueError(f"methodology is not a PDF: {url}")
    return {
        "url": url,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def parse_product_records(
    records: list[dict[str, Any]], index_code: str, product_code: str
) -> dict[str, Any]:
    if not records:
        raise ValueError(f"CSI returned no products for {index_code}")
    matches = [
        row
        for row in records
        if str(row.get("productCode")) == product_code
        and str(row.get("indexCode")) == index_code
        and str(row.get("fundType")) == "ETF"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one ETF {product_code} for {index_code}, found {len(matches)}"
        )
    row = matches[0]
    required = {
        "productCode",
        "fundName",
        "fundType",
        "indexCode",
        "inceptionDate",
        "exchange",
    }
    missing = required - set(row)
    if missing:
        raise ValueError(f"CSI product row missing fields: {sorted(missing)}")
    return {
        "product_code": str(row["productCode"]),
        "fund_name": str(row["fundName"]),
        "fund_type": str(row["fundType"]),
        "index_code": str(row["indexCode"]),
        "inception_date": str(row["inceptionDate"]),
        "exchange": str(row["exchange"]),
        "aum_api_value": str(row.get("aum", "")),
    }


def fetch_official_product(
    index_code: str = CANDIDATE_PRICE_CODE,
    product_code: str = TARGET_ETF_CODE,
    *,
    timeout: float = 60.0,
    session: Any = requests,
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = f"{CSI_PRODUCTS_URL}/{index_code}"
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    records = body.get("data")
    if (
        body.get("success") is not True
        or str(body.get("code")) != "200"
        or not isinstance(records, list)
    ):
        raise ValueError(f"CSI product response failed for {index_code}")
    product = parse_product_records(records, index_code, product_code)
    stable_rows = [
        {
            key: str(row.get(key, ""))
            for key in (
                "productCode",
                "fundName",
                "fundType",
                "indexCode",
                "inceptionDate",
                "exchange",
            )
        }
        for row in records
    ]
    return product, {
        "url": url,
        "product_count": len(records),
        "canonical_stable_rows_sha256": canonical_json_hash(stable_rows),
    }


def parse_sse_listing(body: dict[str, Any], product_code: str) -> dict[str, Any]:
    records = body.get("result")
    if not isinstance(records, list):
        raise ValueError("SSE fund response has no result list")
    matches = [row for row in records if str(row.get("fundCode")) == product_code]
    if len(matches) != 1:
        raise ValueError(
            f"expected one SSE row for {product_code}, found {len(matches)}"
        )
    row = matches[0]
    if str(row.get("INDEX_CODE")) != CANDIDATE_PRICE_CODE:
        raise ValueError(f"SSE index mismatch for {product_code}")
    listing = pd.to_datetime(str(row.get("listingDate")), format="%Y%m%d", errors="coerce")
    if pd.isna(listing):
        raise ValueError(f"invalid SSE listing date for {product_code}")
    return {
        "product_code": str(row["fundCode"]),
        "listing_date": listing.date().isoformat(),
        "index_code": str(row["INDEX_CODE"]),
        "index_name": str(row.get("INDEX_NAME", "")),
        "security_name": str(row.get("secNameFull", "")),
        "fund_company": str(row.get("companyName", "")),
    }


def fetch_sse_listing(
    product_code: str = TARGET_ETF_CODE,
    *,
    timeout: float = 60.0,
    session: Any = requests,
) -> tuple[dict[str, Any], dict[str, Any]]:
    params = {
        "isPagination": "false",
        "sqlId": "FUND_LIST",
        "fundCode": product_code,
        "fundType": "",
    }
    response = session.get(
        SSE_FUND_QUERY_URL,
        params=params,
        headers={"Referer": "https://www.sse.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    listing = parse_sse_listing(body, product_code)
    return listing, {
        "url": SSE_FUND_QUERY_URL,
        "params": params,
        "canonical_listing_sha256": canonical_json_hash(listing),
    }


def parse_tencent_daily(
    body: dict[str, Any], symbol: str, expected_end: str
) -> pd.DataFrame:
    block = body.get("data", {}).get(symbol)
    if not isinstance(block, dict) or not isinstance(block.get("day"), list):
        raise ValueError(f"Tencent returned no raw daily rows for {symbol}")
    rows = block["day"]
    frame = pd.DataFrame(
        rows, columns=["date", "open", "close", "high", "low", "volume_lots"]
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "close", "high", "low", "volume_lots"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna().sort_values("date").drop_duplicates("date", keep="last")
    if len(frame) < ADV_DAYS:
        raise ValueError(f"Tencent returned fewer than {ADV_DAYS} usable rows")
    if frame.iloc[-1]["date"] != pd.Timestamp(expected_end):
        raise ValueError(
            f"Tencent last row {frame.iloc[-1]['date']} != expected {expected_end}"
        )
    numeric = frame[["open", "close", "high", "low", "volume_lots"]]
    if bool((numeric <= 0).any().any()):
        raise ValueError("Tencent daily rows contain nonpositive price or volume")
    return frame.set_index("date")


def fetch_etf_daily(
    symbol: str = TARGET_ETF_SYMBOL,
    *,
    end: str = "2026-06-30",
    timeout: float = 60.0,
    session: Any = requests,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    start = (pd.Timestamp(end) - pd.Timedelta(days=90)).date().isoformat()
    parameter = f"{symbol},day,{start},{end},100,none"
    response = session.get(
        TENCENT_KLINE_URL,
        params={"param": parameter},
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    frame = parse_tencent_daily(body, symbol, end)
    raw_rows = body["data"][symbol]["day"]
    return frame, {
        "url": TENCENT_KLINE_URL,
        "params": {"param": parameter},
        "raw_rows": len(raw_rows),
        "canonical_daily_rows_sha256": canonical_json_hash(raw_rows),
    }


def parse_sse_trade_record(
    body: dict[str, Any], product_code: str, expected_date: pd.Timestamp | str
) -> dict[str, Any]:
    records = body.get("result")
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError(f"SSE returned {len(records) if isinstance(records, list) else 0} rows")
    row = records[0]
    date = pd.to_datetime(str(row.get("TX_DATE")), format="%Y%m%d", errors="coerce")
    expected = pd.Timestamp(expected_date)
    if str(row.get("SEC_CODE")) != product_code or date != expected:
        raise ValueError(f"SSE trade row identity mismatch for {product_code} {expected.date()}")
    amount_cny = pd.to_numeric(row.get("TRADE_AMT"), errors="coerce") * 10_000.0
    volume_shares = pd.to_numeric(row.get("TRADE_VOL"), errors="coerce") * 10_000.0
    close = pd.to_numeric(row.get("CLOSE_PRICE"), errors="coerce")
    if pd.isna(amount_cny) or pd.isna(volume_shares) or pd.isna(close):
        raise ValueError(f"SSE trade row has nonnumeric values for {expected.date()}")
    if amount_cny <= 0 or volume_shares <= 0 or close <= 0:
        raise ValueError(f"SSE trade row has nonpositive values for {expected.date()}")
    return {
        "date": expected.date().isoformat(),
        "close": float(close),
        "volume_shares": float(volume_shares),
        "trade_amount_cny": float(amount_cny),
    }


def fetch_sse_trading(
    dates: pd.DatetimeIndex,
    product_code: str = TARGET_ETF_CODE,
    *,
    timeout: float = 60.0,
    max_workers: int = 8,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if len(dates) != ADV_DAYS:
        raise ValueError(f"expected {ADV_DAYS} trading dates, found {len(dates)}")

    def fetch_one(date: pd.Timestamp) -> dict[str, Any]:
        params = {
            "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C",
            "SEC_CODE": product_code,
            "TX_DATE": date.date().isoformat(),
            "TX_DATE_MON": "",
            "TX_DATE_YEAR": "",
        }
        response = requests.get(
            "https://query.sse.com.cn/commonQuery.do",
            params=params,
            headers={
                "Referer": "https://www.sse.com.cn/",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return parse_sse_trade_record(response.json(), product_code, date)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        rows = list(executor.map(fetch_one, list(dates)))
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").set_index("date")
    if list(frame.index) != list(dates):
        raise ValueError("SSE daily rows do not match frozen trading dates")
    return frame, {
        "url": "https://query.sse.com.cn/commonQuery.do",
        "sql_id": "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C",
        "rows": len(rows),
        "start": frame.index[0].date().isoformat(),
        "end": frame.index[-1].date().isoformat(),
        "canonical_rows_sha256": canonical_json_hash(rows),
        "units": {"TRADE_AMT": "CNY 10,000", "TRADE_VOL": "10,000 shares"},
    }


def product_diagnostics(
    product: dict[str, Any],
    listing: dict[str, Any],
    daily: pd.DataFrame,
    sse_trading: pd.DataFrame,
    evidence_end: str = "2026-06-30",
) -> dict[str, Any]:
    inception = pd.Timestamp(product["inception_date"])
    listing_date = pd.Timestamp(listing["listing_date"])
    end = pd.Timestamp(evidence_end)
    if inception > listing_date or listing_date > end:
        raise ValueError("ETF inception/listing chronology is invalid")
    live_months = (end.year - listing_date.year) * 12 + end.month - listing_date.month
    last = daily.loc[:end].tail(ADV_DAYS).copy()
    if len(last) != ADV_DAYS:
        raise ValueError(f"need exactly {ADV_DAYS} rows for ADV diagnostic")
    official = sse_trading.reindex(last.index)
    if bool(official.isna().any().any()):
        raise ValueError("SSE trading evidence does not cover the frozen ADV window")
    proxy = last["close"] * last["volume_lots"] * 100.0
    official_amount = official["trade_amount_cny"]
    relative_gap = (proxy - official_amount).abs() / official_amount
    adv = float(official_amount.mean())
    return {
        "inception_date": inception.date().isoformat(),
        "listing_date": listing_date.date().isoformat(),
        "evidence_end": end.date().isoformat(),
        "live_full_months": int(live_months),
        "adv_days": ADV_DAYS,
        "adv_start": last.index[0].date().isoformat(),
        "adv_end": last.index[-1].date().isoformat(),
        "adv_cny_sse_official": adv,
        "median_daily_trade_amount_cny_sse_official": float(official_amount.median()),
        "target_capital_cny": INITIAL_CAPITAL_CNY,
        "target_participation_of_adv": INITIAL_CAPITAL_CNY / adv,
        "one_percent_adv_cny": adv * 0.01,
        "tencent_close_volume_crosscheck_max_relative_gap": float(relative_gap.max()),
    }


def evaluate_index_gates(
    post_publication: dict[str, Any],
    inference: dict[str, Any],
    folds: list[dict[str, Any]],
    defense_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = post_publication["delta"]
    hac = inference["newey_west_hac"]
    bootstrap = inference["block_bootstrap_95"]
    positive_folds = sum(fold["cagr_delta"] > 0 for fold in folds)
    defense_ok = all(
        not block.get("available", False)
        or block["delta"]["max_drawdown_improvement"] >= -0.02
        for block in defense_windows.values()
    )
    gates = {
        "post_publication_months_at_least_60": (
            post_publication["baseline"]["months"] >= 60
        ),
        "cagr_delta_at_least_2pp": delta["cagr"] >= 0.02,
        "sharpe_delta_at_least_0_15": delta["sharpe_rf0"] >= 0.15,
        "max_drawdown_deterioration_within_3pp": (
            delta["max_drawdown_improvement"] >= -0.03
        ),
        "at_least_3_of_4_positive_folds": positive_folds >= 3,
        "hac_t_at_least_1_65": hac["t"] is not None and hac["t"] >= 1.65,
        "bootstrap_95_lower_above_zero": bootstrap["annualized_lower"] > 0.0,
        "defense_drawdown_not_worse_by_more_than_2pp": defense_ok,
    }
    all_pass = all(gates.values())
    return {
        "gates": gates,
        "positive_folds": positive_folds,
        "all_pass": all_pass,
        "verdict": "GO" if all_pass else "NO_GO",
    }


def anchored_window_diagnostics(
    aligned: pd.DataFrame, start: str, end: str
) -> dict[str, Any]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    before = aligned.loc[aligned.index < start_ts].dropna().tail(1)
    within = aligned.loc[start_ts:end_ts].dropna()
    if before.empty or within.empty:
        return {"start": start, "end": end, "available": False}
    anchored = pd.concat([before, within])
    output: dict[str, Any] = {
        "start": start,
        "end": end,
        "anchor_date": before.index[-1].date().isoformat(),
        "available": True,
    }
    for column in ("baseline", "candidate"):
        values = anchored[column]
        output[column] = {
            "return": float(values.iloc[-1] / values.iloc[0] - 1.0),
            "max_drawdown": common.max_drawdown(values),
        }
    output["delta"] = {
        "return": output["candidate"]["return"] - output["baseline"]["return"],
        "max_drawdown_improvement": (
            output["candidate"]["max_drawdown"]
            - output["baseline"]["max_drawdown"]
        ),
    }
    return output


def evaluate_implementation_gates(
    product: dict[str, Any], diagnostics: dict[str, Any]
) -> dict[str, Any]:
    gates = {
        "official_target_etf_exists": (
            product["product_code"] == TARGET_ETF_CODE
            and product["fund_type"] == "ETF"
            and product["index_code"] == CANDIDATE_PRICE_CODE
        ),
        "live_product_history_at_least_60_months": (
            diagnostics["live_full_months"] >= 60
        ),
        "target_capital_at_most_1pct_adv": (
            diagnostics["target_participation_of_adv"] <= 0.01
        ),
    }
    all_pass = all(gates.values())
    return {
        "gates": gates,
        "all_pass": all_pass,
        "verdict": "GO" if all_pass else "IMPLEMENTATION_NO_GO",
    }


def derive_overall_verdict(
    index_result: dict[str, Any], implementation_result: dict[str, Any]
) -> str:
    if index_result.get("verdict") not in {"GO", "NO_GO"}:
        raise ValueError("unexpected index verdict")
    if implementation_result.get("verdict") not in {"GO", "IMPLEMENTATION_NO_GO"}:
        raise ValueError("unexpected implementation verdict")
    if index_result["verdict"] == "NO_GO":
        return "NO_GO"
    if implementation_result["verdict"] != "GO":
        return "PAPER_ONLY"
    return "GO"


def run(*, timeout: float = 60.0) -> dict[str, Any]:
    baseline, baseline_source = common.fetch_index_series(
        BASE_TR_CODE, start=SOURCE_START, end=EVIDENCE_END, timeout=timeout
    )
    candidate, candidate_source = common.fetch_index_series(
        CANDIDATE_TR_CODE, start=SOURCE_START, end=EVIDENCE_END, timeout=timeout
    )
    base_meta, base_meta_source = common.fetch_index_metadata(
        BASE_PRICE_CODE, timeout=timeout
    )
    candidate_meta, candidate_meta_source = common.fetch_index_metadata(
        CANDIDATE_PRICE_CODE, timeout=timeout
    )
    base_methodology = fetch_methodology(BASE_METHODOLOGY_URL, timeout=timeout)
    candidate_methodology = fetch_methodology(
        CANDIDATE_METHODOLOGY_URL, timeout=timeout
    )
    product, product_source = fetch_official_product(timeout=timeout)
    listing, listing_source = fetch_sse_listing(timeout=timeout)
    etf_daily, etf_source = fetch_etf_daily(timeout=timeout)
    adv_dates = etf_daily.loc[: pd.Timestamp("2026-06-30")].tail(ADV_DAYS).index
    sse_trading, sse_trading_source = fetch_sse_trading(
        adv_dates, timeout=timeout
    )

    for label, meta in (("baseline", base_meta), ("candidate", candidate_meta)):
        publication = pd.Timestamp(meta["publishDate"])
        if publication != COMMON_PUBLICATION_DATE:
            raise ValueError(
                f"{label} publication date drifted: {publication.date()}"
            )

    aligned = pd.concat(
        [baseline.rename("baseline"), candidate.rename("candidate")], axis=1
    ).dropna()
    aligned = aligned.loc[pd.Timestamp("2005-12-30") : pd.Timestamp("2026-06-30")]
    if aligned.empty:
        raise ValueError("official total-return series have no common history")
    month_end = COMMON_PUBLICATION_DATE + pd.offsets.MonthEnd(0)
    publication_month = aligned.loc[COMMON_PUBLICATION_DATE:month_end]
    if publication_month.empty:
        raise ValueError("no common close in the publication month")
    post_start = publication_month.index[-1]
    pre_end = aligned.index[aligned.index < COMMON_PUBLICATION_DATE][-1]

    backcast = common.pair_window(aligned, aligned.index[0], pre_end)
    post_publication = common.pair_window(aligned, post_start, aligned.index[-1])
    full_history = common.pair_window(aligned, aligned.index[0], aligned.index[-1])
    monthly = common.monthly_pair_returns(aligned.loc[post_start:])
    folds = common.chronological_folds(monthly, 4)
    inference = {
        "paired_months": int(len(monthly)),
        "monthly_win_rate": float((monthly["excess"] > 0).mean()),
        "monthly_return_correlation": float(
            monthly[["baseline", "candidate"]].corr().iloc[0, 1]
        ),
        "annualized_arithmetic_excess_mean": float(monthly["excess"].mean() * 12.0),
        "newey_west_hac": common.newey_west_mean(monthly["excess"], common.HAC_LAGS),
        "block_bootstrap_95": common.block_bootstrap_mean_ci(monthly["excess"]),
    }
    stress_windows = {
        "2022": anchored_window_diagnostics(aligned, "2022-01-01", "2022-12-31"),
        "2024_jan_feb": anchored_window_diagnostics(
            aligned, "2024-01-01", "2024-02-29"
        ),
        "2025_diagnostic_only": anchored_window_diagnostics(
            aligned, "2025-01-01", "2025-12-31"
        ),
    }
    defense_windows = {
        key: stress_windows[key] for key in ("2022", "2024_jan_feb")
    }
    index_result = evaluate_index_gates(
        post_publication, inference, folds, defense_windows
    )
    product_stats = product_diagnostics(product, listing, etf_daily, sse_trading)
    implementation_result = evaluate_implementation_gates(product, product_stats)
    overall = derive_overall_verdict(index_result, implementation_result)
    runner_path = Path(__file__).resolve()
    dependency_path = (
        REPO_ROOT / "scripts/test/ashare_dividend_quality_lowvol_first_look.py"
    )

    return {
        "research_id": "ashare_dividend_value_first_look_2026_07_12",
        "run_date": RUN_DATE,
        "role": "evaluator_independent_strategy_research",
        "capital_cny": INITIAL_CAPITAL_CNY,
        "overall_verdict": overall,
        "index_verdict": index_result["verdict"],
        "implementation_verdict": implementation_result["verdict"],
        "hypothesis": (
            "Within the same high-and-sustainable-dividend preselection, replacing "
            "the final low-volatility rank with the official BP/EP/CFP composite "
            "value rank materially improves return without unacceptable defense loss."
        ),
        "attribution_boundary": (
            "H30270 is a multi-value alternative that replaces, rather than adds to, "
            "H30269's low-vol selector. This is not a pure E/P test."
        ),
        "preobservation_provenance": {
            "status": "DIALOGUE_FROZEN_NOT_PRISTINE_REPOSITORY_PREREGISTRATION",
            "detail": (
                "The candidate pair was frozen before relative metrics were computed in "
                "this trial. Earlier reconnaissance had touched code availability and "
                "first/last values, so the repository cannot prove pristine preregistration. "
                "The runner performs no candidate enumeration, argmax, or parameter search."
            ),
        },
        "frozen_design": {
            "baseline_price_index": BASE_PRICE_CODE,
            "baseline_total_return_index": BASE_TR_CODE,
            "candidate_price_index": CANDIDATE_PRICE_CODE,
            "candidate_total_return_index": CANDIDATE_TR_CODE,
            "common_publication_date": COMMON_PUBLICATION_DATE.date().isoformat(),
            "primary_start_rule": "last common trading close in publication month",
            "primary_start": post_start.date().isoformat(),
            "evidence_end": "2026-06-30",
            "no_search": [
                "no alternate-index scan",
                "no window optimization",
                "no blend-weight optimization",
                "no timing-rule modification",
            ],
        },
        "methodology": {
            "shared": (
                "CSI All Share universe; three consecutive annual cash dividends; "
                "size/liquidity filters; payout and DPS-growth sustainability filters; "
                "top 75 by three-year average after-tax dividend yield; dividend-yield "
                "weighting; annual December review."
            ),
            "baseline_final_selection": "50 lowest by one-year volatility",
            "candidate_final_selection": "50 highest by composite BP, EP and CFP rank",
            "unknowns": (
                "The public methodology does not state the exact composite weights, "
                "normalization, or whether E excludes non-recurring items."
            ),
            "baseline_pdf": base_methodology,
            "candidate_pdf": candidate_methodology,
        },
        "results": {
            "pre_publication_backcast": backcast,
            "post_publication_primary": post_publication,
            "full_history_mixed": full_history,
            "inference": inference,
            "chronological_folds": folds,
            "annual_returns": common.annual_returns(monthly),
            "stress_windows": stress_windows,
        },
        "index_gates": index_result,
        "product_layer": {
            "official_product": product,
            "official_sse_listing": listing,
            "fund_manager_url": FUND_MANAGER_URL,
            "diagnostics": product_stats,
            "gates": implementation_result,
            "interpretation": (
                "The ETF exists, but its live history is under 60 months and CNY 2.1m "
                "is far above the frozen 1% ADV limit. Index scaling is not an "
                "execution backtest."
            ),
        },
        "source_evidence": {
            "baseline_total_return": baseline_source,
            "candidate_total_return": candidate_source,
            "baseline_metadata": base_meta_source,
            "candidate_metadata": candidate_meta_source,
            "official_products": product_source,
            "official_sse_listing": listing_source,
            "etf_daily_market": etf_source,
            "official_sse_daily_trading": sse_trading_source,
            "runner_sha256": sha256_file(runner_path),
            "common_helper_sha256": sha256_file(dependency_path),
        },
        "limitations": [
            "Official index values are frictionless and allow fractional scaling.",
            "No constituent history is available to isolate BP, EP and CFP contributions.",
            "Official ADV measures traded value but does not model spread, premium, impact, "
            "lot rounding, fees, taxes, limit states or creation/redemption mechanics.",
            "The ETF has too little live history for an implementation performance study.",
        ],
        "decision": (
            "Do not replace B082's dividend-low-volatility exposure with H30270/H20270. "
            "The frozen official value alternative does not improve post-publication return "
            "or Sharpe, lacks statistical support, and fails both live-history and target-"
            "capital liquidity gates."
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
    print(json.dumps({
        "overall_verdict": report["overall_verdict"],
        "index_verdict": report["index_verdict"],
        "implementation_verdict": report["implementation_verdict"],
        "out": str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
