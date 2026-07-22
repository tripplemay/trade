#!/usr/bin/env python3
"""B111 F007 independent low-vol evidence runner.

This evaluator-owned script deliberately imports none of the F005 research
modules.  It rebuilds the monthly return panel, trailing volatility sorts,
liquidity gate, portfolio statistics, and paired bootstrap from the delivered
CSV inputs.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/research/B110/ep_panel.csv.gz"
LIQUIDITY = ROOT / "data/research/B111/low_vol_liquidity.csv.gz"
DELIVERED = ROOT / "docs/audits/B111-F005-low-vol-first-look.json"
OUT = ROOT / "docs/test-reports/B111-F007-evidence-2026-07-21.json"
SAMPLE_SEED = "B111-F007-codex-unconditional-sample-v1"
BOOTSTRAP_SEED = 20260721
N_BOOT = 2000


def read_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def usable_float(raw: str | None) -> float | None:
    if raw in (None, "", "None", "nan"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def geometric_annual(values: list[float]) -> float | None:
    if not values:
        return None
    growth = 1.0
    for value in values:
        growth *= 1.0 + value
    if growth <= 0:
        return -1.0
    return growth ** (12.0 / len(values)) - 1.0


def simple_t(values: list[float]) -> float | None:
    sigma = stdev(values)
    if sigma is None or sigma <= 0:
        return None
    return mean(values) / (sigma / math.sqrt(len(values)))


def newey_west_t(values: list[float], lag: int = 6) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    dev = [value - avg for value in values]
    variance = sum(value * value for value in dev) / len(values)
    for offset in range(1, min(lag, len(values) - 1) + 1):
        weight = 1.0 - offset / (lag + 1)
        covariance = sum(
            dev[index] * dev[index - offset]
            for index in range(offset, len(values))
        ) / len(values)
        variance += 2.0 * weight * covariance
    if variance <= 0:
        return None
    return avg / math.sqrt(variance / len(values))


def paired_bootstrap(top: list[float], benchmark: list[float]) -> dict[str, Any]:
    if len(top) != len(benchmark):
        raise AssertionError("top and benchmark monthly series lengths differ")
    pairs = [(top[index], benchmark[index]) for index in range(len(top))]
    rng = random.Random(BOOTSTRAP_SEED)
    statistics: list[float] = []
    for _ in range(N_BOOT):
        sampled = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        top_ann = geometric_annual([pair[0] for pair in sampled])
        benchmark_ann = geometric_annual([pair[1] for pair in sampled])
        if top_ann is not None and benchmark_ann is not None:
            statistics.append(top_ann - benchmark_ann)
    statistics.sort()
    return {
        "seed": BOOTSTRAP_SEED,
        "n_boot": N_BOOT,
        "n_effective": len(statistics),
        "p_positive": sum(value > 0 for value in statistics) / len(statistics),
        "ci95": [
            statistics[int(0.025 * len(statistics))],
            statistics[min(int(0.975 * len(statistics)), len(statistics) - 1)],
        ],
    }


def load_liquidity() -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for row in read_gz(LIQUIDITY):
        amount = usable_float(row.get("amount"))
        if amount is not None:
            result[row["formation_date"]][row["ts_code"]] = amount
    return dict(result)


def build_return_series(
    rows: list[dict[str, str]], stub: str
) -> dict[str, dict[str, float]]:
    column = f"fwd_ret_stub_{stub}"
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        value = usable_float(row.get(column))
        if value is not None:
            result[row["ts_code"]][row["formation_date"]] = value
    return dict(result)


def compute_sections(
    rows: list[dict[str, str]],
    *,
    stub: str,
    lag: int,
    liquidity: dict[str, dict[str, float]] | None = None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    grid = sorted({row["formation_date"] for row in rows})
    series = build_return_series(rows, stub)
    sections: list[dict[str, Any]] = []
    assignments: dict[tuple[str, str], dict[str, Any]] = {}
    for grid_index, formation_date in enumerate(grid):
        observations: list[tuple[str, float, float]] = []
        start = grid_index - 12 - lag
        stop = grid_index - lag
        if start >= 0:
            for code, returns in series.items():
                forward = returns.get(formation_date)
                history = [returns.get(grid[index]) for index in range(start, stop)]
                if forward is None or any(value is None for value in history):
                    continue
                sigma = stdev([float(value) for value in history if value is not None])
                if sigma is not None:
                    observations.append((code, sigma, forward))

        before_liquidity = len(observations)
        liquidity_available = None
        liquidity_cut = None
        if liquidity is not None:
            amounts = liquidity.get(formation_date, {})
            with_liquidity = [
                (observation, amounts[observation[0]])
                for observation in observations
                if observation[0] in amounts
            ]
            with_liquidity.sort(key=lambda item: item[1])
            liquidity_available = len(with_liquidity)
            liquidity_cut = int(len(with_liquidity) * 0.30)
            observations = [item[0] for item in with_liquidity[liquidity_cut:]]

        if len(observations) < 5:
            continue
        ordered = sorted(observations, key=lambda item: item[1])
        grouped: dict[str, list[float]] = defaultdict(list)
        for index, (code, sigma, forward) in enumerate(ordered):
            group = f"V{min(index * 5 // len(ordered), 4) + 1}"
            grouped[group].append(forward)
            assignments[(code, formation_date)] = {
                "sigma": sigma,
                "group": group,
                "forward_return": forward,
            }
        sections.append(
            {
                "formation_date": formation_date,
                "n_sigma_eligible": before_liquidity,
                "n_liquidity_available": liquidity_available,
                "n_liquidity_dropped": liquidity_cut,
                "n_scored": len(observations),
                "group_counts": {key: len(value) for key, value in sorted(grouped.items())},
                "group_returns": {key: mean(value) for key, value in sorted(grouped.items())},
                "benchmark_scored": mean([item[2] for item in observations]),
            }
        )
    return sections, assignments


def summarize(label: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    top = [section["group_returns"]["V1"] for section in sections]
    benchmark = [section["benchmark_scored"] for section in sections]
    if len(top) != len(benchmark):
        raise AssertionError("top and benchmark monthly series lengths differ")
    excess = [top[index] - benchmark[index] for index in range(len(top))]
    top_ann = geometric_annual(top)
    benchmark_ann = geometric_annual(benchmark)
    excess_geo = top_ann - benchmark_ann
    sigma_top = stdev(top)
    sigma_benchmark = stdev(benchmark)
    by_year: dict[str, dict[str, Any]] = {}
    for year in sorted({section["formation_date"][:4] for section in sections}):
        year_top = [
            section["group_returns"]["V1"]
            for section in sections
            if section["formation_date"].startswith(year)
        ]
        year_benchmark = [
            section["benchmark_scored"]
            for section in sections
            if section["formation_date"].startswith(year)
        ]
        year_sigma_top = stdev(year_top)
        year_sigma_benchmark = stdev(year_benchmark)
        by_year[year] = {
            "months": len(year_top),
            "sigma_v1": year_sigma_top,
            "sigma_benchmark": year_sigma_benchmark,
            "v1_lower": (
                year_sigma_top is not None
                and year_sigma_benchmark is not None
                and year_sigma_top < year_sigma_benchmark
            ),
        }
    group_series: dict[str, list[float]] = defaultdict(list)
    for section in sections:
        for group, value in section["group_returns"].items():
            group_series[group].append(value)
    annual_se = stdev(excess) * 12.0 / math.sqrt(len(excess))
    bootstrap = paired_bootstrap(top, benchmark)
    return {
        "label": label,
        "n_months": len(sections),
        "ann_v1_geometric": top_ann,
        "ann_benchmark_scored_geometric": benchmark_ann,
        "excess_ann_geometric_vs_scored": excess_geo,
        "group_annual_geometric": {
            group: geometric_annual(values) for group, values in sorted(group_series.items())
        },
        "arithmetic_side_by_side": {
            "excess_ann_arithmetic": mean(excess) * 12.0,
            "monthly_excess_t_simple": simple_t(excess),
            "monthly_excess_t_newey_west_lag6": newey_west_t(excess),
            "se_ann": annual_se,
            "ci95_ann_analytical": [excess_geo - 1.96 * annual_se, excess_geo + 1.96 * annual_se],
        },
        "bootstrap_geometric_excess": bootstrap,
        "realized_sigma": {
            "sigma_v1": sigma_top,
            "sigma_benchmark": sigma_benchmark,
            "sigma_ratio": sigma_top / sigma_benchmark,
            "n_years": len(by_year),
            "n_years_v1_lower": sum(item["v1_lower"] for item in by_year.values()),
            "by_year": by_year,
        },
        "monthly": sections,
    }


def unconditional_sample(
    rows: list[dict[str, str]], assignments: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_year[row["formation_date"][:4]].append(row)
    sample: list[dict[str, Any]] = []
    for year in sorted(by_year):
        ranked = sorted(
            by_year[year],
            key=lambda row: hashlib.sha256(
                f"{SAMPLE_SEED}|{row['formation_date']}|{row['ts_code']}".encode()
            ).hexdigest(),
        )
        for row in ranked[:5]:
            item = assignments.get((row["ts_code"], row["formation_date"]))
            sample.append(
                {
                    "ts_code": row["ts_code"],
                    "formation_date": row["formation_date"],
                    "selection_condition": "raw_panel_only_not_conditioned_on_sigma_or_group",
                    "eligible": item is not None,
                    "independent_sigma": None if item is None else item["sigma"],
                    "independent_group": None if item is None else item["group"],
                    "forward_return": usable_float(row.get("fwd_ret_stub_0.00")),
                }
            )
    return sample


def compare_value(path: str, independent: Any, delivered: Any) -> dict[str, Any]:
    if isinstance(independent, (int, float)) and isinstance(delivered, (int, float)):
        difference = abs(float(independent) - float(delivered))
        matched = difference <= 1e-12
    else:
        difference = None
        matched = independent == delivered
    return {
        "path": path,
        "independent": independent,
        "delivered": delivered,
        "absolute_difference": difference,
        "matched": matched,
    }


def aggregate_comparisons(
    independent: dict[str, Any], delivered: dict[str, Any]
) -> list[dict[str, Any]]:
    paths = [
        ("n_months",),
        ("ann_v1_geometric",),
        ("ann_benchmark_scored_geometric",),
        ("excess_ann_geometric_vs_scored",),
        ("realized_sigma", "sigma_ratio"),
        ("realized_sigma", "n_years"),
        ("realized_sigma", "n_years_v1_lower"),
        ("bootstrap_geometric_excess", "p_positive"),
        ("arithmetic_side_by_side", "monthly_excess_t_simple"),
        ("arithmetic_side_by_side", "monthly_excess_t_newey_west_lag6"),
    ]
    checks: list[dict[str, Any]] = []
    for components in paths:
        left: Any = independent
        right: Any = delivered
        for component in components:
            left = left[component]
            right = right[component]
        checks.append(compare_value(".".join(components), left, right))
    for group in ("V1", "V2", "V3", "V4", "V5"):
        checks.append(
            compare_value(
                f"group_annual_geometric.{group}",
                independent["group_annual_geometric"][group],
                delivered["group_annual_geometric"][group],
            )
        )
    return checks


def main() -> None:
    rows = read_gz(PANEL)
    liquidity = load_liquidity()
    delivered = json.loads(DELIVERED.read_text(encoding="utf-8"))
    specs = {
        "main_stub_0.00": {"stub": "0.00", "lag": 0, "liquidity": None},
        "main_stub_-0.30": {"stub": "-0.30", "lag": 0, "liquidity": None},
        "main_stub_-1.00": {"stub": "-1.00", "lag": 0, "liquidity": None},
        "g1_lag1_stub_0.00": {"stub": "0.00", "lag": 1, "liquidity": None},
        "g2_liquidity_stub_0.00": {"stub": "0.00", "lag": 0, "liquidity": liquidity},
    }
    variants: dict[str, Any] = {}
    comparisons: dict[str, Any] = {}
    main_assignments: dict[tuple[str, str], dict[str, Any]] = {}
    for label, spec in specs.items():
        sections, assignments = compute_sections(rows, **spec)
        variants[label] = summarize(label, sections)
        comparisons[label] = aggregate_comparisons(
            variants[label], delivered["variants"][label]
        )
        if label == "main_stub_0.00":
            main_assignments = assignments

    main = variants["main_stub_0.00"]
    g1 = variants["g1_lag1_stub_0.00"]
    g2 = variants["g2_liquidity_stub_0.00"]
    criteria = {
        "G1_geometric_excess_ge_1pp": g1["excess_ann_geometric_vs_scored"] >= 0.01,
        "G2_geometric_excess_ge_1pp": g2["excess_ann_geometric_vs_scored"] >= 0.01,
        "main_sigma_ratio_le_0_90": main["realized_sigma"]["sigma_ratio"] <= 0.90,
        "main_at_least_11_lower_vol_years": main["realized_sigma"]["n_years_v1_lower"] >= 11,
        "main_has_required_12_independent_years": main["realized_sigma"]["n_years"] >= 12,
        "main_geometric_excess_positive": main["excess_ann_geometric_vs_scored"] > 0,
        "main_bootstrap_p_ge_0_90": main["bootstrap_geometric_excess"]["p_positive"] >= 0.90,
    }
    frozen_clause_checks = {
        "B1_data_source_b110_panel_and_b111_liquidity": True,
        "B1_sort_t_minus_12_through_t_minus_1": True,
        "B1_g1_sort_t_minus_13_through_t_minus_2": True,
        "B1_five_equal_count_groups_v1_lowest_sigma": True,
        "B1_b_scored_equal_weight_benchmark": True,
        "B1_b_wide_and_difference_reported": False,
        "B1_geometric_and_arithmetic_annualization": True,
        "B1_stub_zero_and_three_stub_sensitivity": True,
        "B1_executable_n100_semiannual_context_reported": False,
        "B2_g1_proxy_executed": True,
        "B2_g2_frozen_daily_average_liquidity_executed": False,
        "B3_main_risk_sigma_ratio_computed": True,
        "B3_required_12_independent_years_observed": main["realized_sigma"]["n_years"] >= 12,
        "B3_secondary_compounding_computed": True,
        "B3_arithmetic_excess_t_nw_and_ci_same_table": False,
        "B5_full_window_frozen": True,
        "B5_segment_results_side_by_side": False,
        "H7_generator_did_not_adjudicate": True,
    }
    all_checks = [check for checks in comparisons.values() for check in checks]
    artifact_text = DELIVERED.read_text(encoding="utf-8")
    report = {
        "method": {
            "independence": (
                "zero imports from scripts.research.ashare_pit.low_vol, "
                "low_vol_cli, or signal_stats"
            ),
            "panel": str(PANEL.relative_to(ROOT)),
            "liquidity": str(LIQUIDITY.relative_to(ROOT)),
            "sample_seed": SAMPLE_SEED,
            "sample_selection": (
                "five raw panel rows per calendar year; no "
                "sigma/group/eligibility conditioning"
            ),
        },
        "input_counts": {
            "panel_rows": len(rows),
            "formation_months": len({row["formation_date"] for row in rows}),
            "securities": len({row["ts_code"] for row in rows}),
            "liquidity_rows": sum(len(values) for values in liquidity.values()),
            "liquidity_months": len(liquidity),
        },
        "independent_sample": unconditional_sample(rows, main_assignments),
        "variants": variants,
        "delivered_aggregate_comparisons": comparisons,
        "all_delivered_aggregate_checks_match": all(check["matched"] for check in all_checks),
        "criteria": criteria,
        "frozen_clause_checks": frozen_clause_checks,
        "criterion_outcome": {
            "delivered_proxy_hard_gates_pass": (
                criteria["G1_geometric_excess_ge_1pp"]
                and criteria["G2_geometric_excess_ge_1pp"]
            ),
            "spec_hard_gates_complete": frozen_clause_checks[
                "B2_g2_frozen_daily_average_liquidity_executed"
            ],
            "main_risk_ratio_pass": criteria["main_sigma_ratio_le_0_90"],
            "main_risk_year_count_pass_strict_11_of_12": (
                criteria["main_at_least_11_lower_vol_years"]
                and criteria["main_has_required_12_independent_years"]
            ),
            "secondary_compounding_pass": (
                criteria["main_geometric_excess_positive"]
                and criteria["main_bootstrap_p_ge_0_90"]
            ),
            "overall_dual_criteria_pass": False,
        },
        "artifact_boundary_checks": {
            "honesty_statement_present": (
                "不是干净的预注册" in artifact_text
                and "背景不作证据" in artifact_text
            ),
            "arithmetic_not_relied_upon_present": (
                "disclosed_not_relied_upon_this_design_does_not_depend_on_it"
                in artifact_text
            ),
            "generator_boundary_present": "H7" in delivered.get("generator_boundary", ""),
            "known_wording_defect": (
                "两个尚未执行的证伪" in delivered["hard_gates"]["role"]
                and delivered["hard_gates"]["G2_liquidity_filter"]["status"]
                == "executed"
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "all_delivered_aggregate_checks_match": report["all_delivered_aggregate_checks_match"],
        "criteria": criteria,
        "criterion_outcome": report["criterion_outcome"],
        "sample_count": len(report["independent_sample"]),
        "evidence": str(OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
