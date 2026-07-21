#!/usr/bin/env python3
"""B110 F004 independent evidence runner.

This script deliberately does not import the B110 TTM or signal-statistics
calculation modules.  It reads the raw cached income pages and the delivered
panel, then independently re-resolves a self-selected sample and recomputes
the monthly leg arithmetic.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/research/B110"
PANEL = CACHE / "ep_panel.csv.gz"
FUNNEL = ROOT / "docs/audits/B110-F002-monthly-funnel.csv"
OUT = ROOT / "docs/test-reports/B110-F004-evidence-2026-07-21.json"
SEED = "B110-F004-codex-independent-sample-v1"
QUARTER_ENDS = ("0331", "0630", "0930", "1231")


def read_gz_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def decimal(value: str) -> Decimal:
    return Decimal(value)


def load_income(report_type: str) -> dict[str, dict[str, list[dict[str, str]]]]:
    result: dict[str, dict[str, list[dict[str, str]]]] = {}
    for path in sorted(CACHE.glob(f"income_rt{report_type}_*.csv.gz")):
        period = path.name.split("_")[-1].removesuffix(".csv.gz")
        rows = read_gz_csv(path)
        by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row.get("report_type", "").strip() == report_type:
                by_code[row["ts_code"]].append(row)
        result[period] = dict(by_code)
    return result


def as_of(rows: list[dict[str, str]], formation_date: str) -> dict[str, str] | None:
    visible = [row for row in rows if row.get("f_ann_date", "") <= formation_date]
    if not visible:
        return None
    latest = max(row["f_ann_date"] for row in visible)
    winners = [row for row in visible if row["f_ann_date"] == latest]
    values = {row.get("n_income_attr_p", "") for row in winners}
    if len(values) != 1:
        raise AssertionError(f"ambiguous as-of value at {formation_date}: {latest}")
    return winners[0]


def prior_period(period: str) -> str | None:
    year, suffix = int(period[:4]), period[4:]
    if suffix == "0331":
        return None
    index = QUARTER_ENDS.index(suffix)
    return f"{year:04d}{QUARTER_ENDS[index - 1]}"


def window(anchor: str) -> list[tuple[str, int]]:
    year, suffix = int(anchor[:4]), anchor[4:]
    index = QUARTER_ENDS.index(suffix)
    result: list[tuple[str, int]] = []
    for offset in range(4):
        q = index - offset
        y = year
        while q < 0:
            q += 4
            y -= 1
        result.append((f"{y:04d}{QUARTER_ENDS[q]}", q + 1))
    return result


def cumulative_periods(anchor: str) -> list[str]:
    needed: set[str] = set()
    for period, _ in window(anchor):
        needed.add(period)
        previous = prior_period(period)
        if previous:
            needed.add(previous)
    return sorted(needed)


def independent_ttm(
    code: str,
    formation: str,
    anchor: str,
    cumulative: dict[str, dict[str, list[dict[str, str]]]],
    direct: dict[str, dict[str, list[dict[str, str]]]],
) -> dict[str, object]:
    values: dict[str, Decimal] = {}
    selected_dates: dict[str, str] = {}
    direct_matches = 0
    direct_breaks = 0
    components: list[dict[str, object]] = []
    for period in cumulative_periods(anchor):
        row = as_of(cumulative.get(period, {}).get(code, []), formation)
        if row is None:
            raise AssertionError(f"missing raw cumulative {code} {period} @ {formation}")
        values[period] = decimal(row["n_income_attr_p"])
        selected_dates[period] = row["f_ann_date"]

    path_a = Decimal(0)
    for period, quarter in window(anchor):
        current = values[period]
        previous_period = prior_period(period)
        previous = values[previous_period] if previous_period else Decimal(0)
        value = current - previous
        path_a += value
        direct_row = as_of(direct.get(period, {}).get(code, []), formation)
        direct_value = None if direct_row is None else decimal(direct_row["n_income_attr_p"])
        status = "UNAVAILABLE"
        if direct_value is not None:
            tolerance = abs(direct_value) * Decimal("0.001") + Decimal("1000")
            status = "MATCH" if abs(value - direct_value) <= tolerance else "BREAK"
            direct_matches += status == "MATCH"
            direct_breaks += status == "BREAK"
        components.append(
            {
                "role": f"SQ{quarter}",
                "period": period,
                "value": str(value),
                "cumulative_f_ann_date": selected_dates[period],
                "direct_value": None if direct_value is None else str(direct_value),
                "direct_status": status,
            }
        )

    index = QUARTER_ENDS.index(anchor[4:])
    year = int(anchor[:4])
    if index == 3:
        path_b = values[anchor]
    else:
        prior_fy = f"{year - 1:04d}1231"
        prior_ytd = f"{year - 1:04d}{QUARTER_ENDS[index]}"
        path_b = values[prior_fy] + values[anchor] - values[prior_ytd]
    if path_a != path_b:
        raise AssertionError(f"equivalence mismatch {code} {formation}: {path_a} != {path_b}")
    return {
        "ts_code": code,
        "formation_date": formation,
        "anchor_end_date": anchor,
        "components": components,
        "path_a_ttm_cny": str(path_a),
        "path_b_equivalence_cny": str(path_b),
        "n_direct_match": direct_matches,
        "n_direct_break": direct_breaks,
    }


def choose_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    eligible = [row for row in rows if row.get("ep") not in ("", "nan", "None")]
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in eligible:
        by_year[row["formation_date"][:4]].append(row)
    selected: list[dict[str, str]] = []
    for year in sorted(by_year):
        ranked = sorted(
            by_year[year],
            key=lambda row: hashlib.sha256(
                f"{SEED}|{row['ts_code']}|{row['formation_date']}".encode()
            ).hexdigest(),
        )
        negative = next((row for row in ranked if decimal(row["ep"]) < 0), None)
        picks = ([negative] if negative else []) + [row for row in ranked if row is not negative]
        selected.extend(picks[:5])
    if len(selected) < 50:
        raise AssertionError(f"self-selected sample too small: {len(selected)}")
    return selected


def geometric(values: list[Decimal]) -> float:
    growth = Decimal(1)
    for value in values:
        growth *= Decimal(1) + value
    return float(growth ** (Decimal(12) / Decimal(len(values))) - Decimal(1))


def leg_recompute(rows: list[dict[str, str]]) -> dict[str, object]:
    monthly: list[dict[str, Decimal]] = []
    for formation in sorted({row["formation_date"] for row in rows}):
        scored = [
            row
            for row in rows
            if row["formation_date"] == formation
            and row.get("ep") not in ("", "nan", "None")
            and row.get("fwd_ret_stub_0.00") not in ("", "nan", "None")
        ]
        scored.sort(key=lambda row: decimal(row["ep"]), reverse=True)
        if len(scored) < 5:
            continue
        groups: dict[str, list[Decimal]] = defaultdict(list)
        for index, row in enumerate(scored):
            bucket = min(index * 5 // len(scored), 4)
            groups[f"Q{5 - bucket}"].append(decimal(row["fwd_ret_stub_0.00"]))
        def mean(values: list[Decimal]) -> Decimal:
            return sum(values, Decimal(0)) / Decimal(len(values))

        benchmark = mean([decimal(row["fwd_ret_stub_0.00"]) for row in scored])
        top, bottom = mean(groups["Q5"]), mean(groups["Q1"])
        monthly.append(
            {
                "formation_date": Decimal(formation),
                "top": top,
                "benchmark": benchmark,
                "bottom": bottom,
                "long": top - benchmark,
                "short": benchmark - bottom,
                "spread": top - bottom,
            }
        )
    if len(monthly) != 144:
        raise AssertionError(f"expected 144 leg months, got {len(monthly)}")
    def mean(key: str) -> Decimal:
        return sum((item[key] for item in monthly), Decimal(0)) / Decimal(len(monthly))

    long_ann, short_ann = float(mean("long") * 12), float(mean("short") * 12)
    spread_ann = float(mean("spread") * 12)
    max_residual = max(
        abs(float(item["spread"] - item["long"] - item["short"])) for item in monthly
    )
    top_ann = geometric([item["top"] for item in monthly])
    benchmark_ann = geometric([item["benchmark"] for item in monthly])
    return {
        "n_months": len(monthly),
        "a_long_ann": long_ann,
        "a_short_ann": short_ann,
        "long_short_ann_arithmetic": spread_ann,
        "monthly_identity_max_residual": max_residual,
        "ann_top_geometric": top_ann,
        "ann_benchmark_scored_geometric": benchmark_ann,
        "excess_ann_geometric_vs_scored": top_ann - benchmark_ann,
    }


def funnel_verify() -> dict[str, object]:
    with FUNNEL.open(encoding="utf-8", newline="") as handle:
        funnel = list(csv.DictReader(handle))
    if len(funnel) != 144:
        raise AssertionError(f"expected 144 funnel rows, got {len(funnel)}")
    if [int(row["formation_seq"]) for row in funnel] != list(range(1, 145)):
        raise AssertionError("formation sequence is not 1..144")
    if funnel[0]["formation_date"] != "20130131" or funnel[-1]["formation_date"] != "20241231":
        raise AssertionError("formation date endpoints changed")
    for row in funnel:
        panel_rows = int(row["panel_rows"])
        ttm_resolved = int(row["ttm_resolved"])
        with_ep = int(row["n_with_ep"])
        usable = int(row["usable"])
        # The implementation's priority is numerator -> denominator -> return.
        # This stage decomposition counts each row once without importing it.
        closed = (
            (panel_rows - ttm_resolved)
            + (ttm_resolved - with_ep)
            + (with_ep - usable)
            + usable
        )
        if closed != panel_rows:
            raise AssertionError(f"funnel does not close at {row['formation_date']}")
    coverage = [Decimal(row["joint_coverage_c1"]) for row in funnel]
    return {
        "months": len(funnel),
        "formation_seq": "1..144",
        "first_formation_date": funnel[0]["formation_date"],
        "last_formation_date": funnel[-1]["formation_date"],
        "min_joint_coverage": str(min(coverage)),
        "median_joint_coverage": str(sorted(coverage)[len(coverage) // 2]),
        "min_negative_ttm_count": min(int(row["n_neg_ttm"]) for row in funnel),
        "period_not_fetched_total": sum(int(row["ttm_period_not_fetched"]) for row in funnel),
        "malformed_security_rows_total": sum(
            int(row["d_security_row_malformed"]) for row in funnel
        ),
    }


def main() -> None:
    panel_rows = read_gz_csv(PANEL)
    cumulative = load_income("1")
    direct = load_income("2")
    sample = choose_sample(panel_rows)
    checks = [
        independent_ttm(
            row["ts_code"],
            row["formation_date"],
            row["anchor_end_date"],
            cumulative,
            direct,
        )
        for row in sample
    ]
    funnel = funnel_verify()
    panel_by_key = {(row["ts_code"], row["formation_date"]): row for row in panel_rows}
    for check in checks:
        panel = panel_by_key[(check["ts_code"], check["formation_date"])]
        if check["path_a_ttm_cny"] != panel["ttm_cny"]:
            raise AssertionError(
                f"panel mismatch {check['ts_code']} {check['formation_date']}: "
                f"{check['path_a_ttm_cny']} != {panel['ttm_cny']}"
            )
        ep = decimal(check["path_a_ttm_cny"]) / decimal(panel["total_mv_cny"])
        if ep != decimal(panel["ep"]):
            raise AssertionError(f"E/P mismatch {check['ts_code']} {check['formation_date']}")
    leg = leg_recompute(panel_rows)
    report = {
        "seed": SEED,
        "sample_count": len(checks),
        "sample_year_counts": {
            year: sum(check["formation_date"].startswith(year) for check in checks)
            for year in sorted({check["formation_date"][:4] for check in checks})
        },
        "direct_match_count": sum(check["n_direct_match"] for check in checks),
        "direct_break_count": sum(check["n_direct_break"] for check in checks),
        "funnel": funnel,
        "checks": checks,
        "leg_recompute_main_stub_0.00": leg,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "checks"},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"evidence={OUT}")


if __name__ == "__main__":
    main()
