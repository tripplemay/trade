#!/usr/bin/env python
"""B113 F003 verifier for the partial_rebalance A/B artifact.

Evaluator-owned, zero product imports: validates the frozen artifact schema,
recomputes deltas/annualized turnover ratios from the JSON payload, checks H7
no-verdict generator boundary, and applies the pre-registered B113 thresholds.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ARTIFACT = Path("docs/research/B113-F002-partial-rebalance-ab.json")
REPORT = Path("docs/research/B113-F002-partial-rebalance-ab.md")

EXPECTED_KEYS = {
    "pure_momentum__100000",
    "pure_momentum__1000000",
    "quality_momentum__100000",
    "quality_momentum__1000000",
}
EXPECTED_WINDOW = {"start": "2019-04-01", "end": "2026-07-31"}
EXPECTED_SPLIT_DATE = "2024-05-22"
EXPECTED_TRADING_DAYS = 1780
CAPITAL_VERDICT_LABEL = {
    100000: "capacity",
    1000000: "mechanism",
}
FORBIDDEN_GENERATOR_VERDICT_WORDS = (
    "NO-GO",
    "NOGO",
    "INCONCLUSIVE",
    "值得投入",
    "有 edge",
    "有edge",
    "建议投入",
    "应当继续",
    "结论是",
)
FORBIDDEN_GO_WORD = "GO"


def _fail(message: str) -> None:
    raise AssertionError(message)


def _assert_close(name: str, actual: float, expected: float, tol: float = 1e-9) -> None:
    if not math.isclose(actual, expected, rel_tol=tol, abs_tol=tol):
        _fail(f"{name}: actual={actual!r} expected={expected!r}")


def _segment_delta_pp(v0: dict[str, Any], v1: dict[str, Any], segment: str, field: str) -> float:
    return (float(v1["segments"][segment][field]) - float(v0["segments"][segment][field])) * 100.0


def _assert_no_generator_verdict_language() -> None:
    for path in (ARTIFACT, REPORT):
        text = path.read_text(encoding="utf-8")
        for word in FORBIDDEN_GENERATOR_VERDICT_WORDS:
            if word in text:
                _fail(f"{path} contains generator-side verdict language: {word}")
        # A bare GO is forbidden, but substrings inside ordinary words are not.
        for token in text.replace("|", " ").replace("(", " ").replace(")", " ").split():
            if token.strip("`*_，。；:：,.") == FORBIDDEN_GO_WORD:
                _fail(f"{path} contains bare generator-side verdict token: GO")


def verify() -> dict[str, dict[str, str]]:
    _assert_no_generator_verdict_language()
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    if payload["frozen_window"]["start"] != EXPECTED_WINDOW["start"]:
        _fail("frozen start mismatch")
    if payload["frozen_window"]["end"] != EXPECTED_WINDOW["end"]:
        _fail("frozen end mismatch")
    if "防御闸关闭" not in payload["ab_caliber"]:
        _fail("ab_caliber does not state defense gate is off")
    if "B112" not in payload["input_coverage"]:
        _fail("input_coverage does not state B112 data-chain reuse")

    thresholds = payload["criterion_thresholds"]
    if thresholds["main_oos_delta_cagr_min_pp"] != 1.0:
        _fail("main threshold mismatch")
    if thresholds["secondary_oos_delta_maxdd_min_pp"] != -2.0:
        _fail("drawdown threshold mismatch")
    if thresholds["secondary_annual_turnover_ratio_max"] != 3.0:
        _fail("turnover threshold mismatch")

    comparisons = payload["comparisons"]
    if set(comparisons) != EXPECTED_KEYS:
        _fail(f"comparison keys mismatch: {sorted(comparisons)}")

    verdicts: dict[str, dict[str, str]] = {}
    for key in sorted(comparisons):
        comp = comparisons[key]
        mode, capital_text = key.rsplit("__", 1)
        capital = int(capital_text)
        v0 = comp["v0"]
        v1 = comp["v1"]

        if v0["mode"] != mode or v1["mode"] != mode:
            _fail(f"{key}: mode mismatch")
        if int(v0["capital"]) != capital or int(v1["capital"]) != capital:
            _fail(f"{key}: capital mismatch")
        if v0["variant"] != "v0_full_band" or v1["variant"] != "v1_partial":
            _fail(f"{key}: variant mismatch")
        if v0["split_date"] != EXPECTED_SPLIT_DATE or v1["split_date"] != EXPECTED_SPLIT_DATE:
            _fail(f"{key}: split date mismatch")
        if v0["trading_days"] != EXPECTED_TRADING_DAYS or v1["trading_days"] != EXPECTED_TRADING_DAYS:
            _fail(f"{key}: trading days mismatch")

        for arm_name, arm in (("v0", v0), ("v1", v1)):
            recomputed_annual = float(arm["total_turnover"]) / (float(arm["trading_days"]) / 252.0)
            _assert_close(f"{key}.{arm_name}.annual_turnover", float(arm["annual_turnover"]), recomputed_annual)

        recomputed_ratio = float(v1["annual_turnover"]) / float(v0["annual_turnover"])
        _assert_close(f"{key}.annual_turnover_ratio", float(comp["annual_turnover_ratio"]), recomputed_ratio)

        for segment in ("full", "oos"):
            expected_cagr = _segment_delta_pp(v0, v1, segment, "annualized_return")
            expected_mdd = _segment_delta_pp(v0, v1, segment, "max_drawdown")
            expected_sharpe = (
                float(v1["segments"][segment]["sharpe_ratio"])
                - float(v0["segments"][segment]["sharpe_ratio"])
            )
            _assert_close(
                f"{key}.{segment}.delta_cagr_pp",
                float(comp["deltas"][segment]["delta_cagr_pp"]),
                expected_cagr,
            )
            _assert_close(
                f"{key}.{segment}.delta_max_drawdown_pp",
                float(comp["deltas"][segment]["delta_max_drawdown_pp"]),
                expected_mdd,
            )
            _assert_close(
                f"{key}.{segment}.delta_sharpe",
                float(comp["deltas"][segment]["delta_sharpe"]),
                expected_sharpe,
            )

        oos = comp["deltas"]["oos"]
        passes = {
            "cagr": float(oos["delta_cagr_pp"]) >= thresholds["main_oos_delta_cagr_min_pp"],
            "maxdd": float(oos["delta_max_drawdown_pp"]) >= thresholds["secondary_oos_delta_maxdd_min_pp"],
            "turnover": float(comp["annual_turnover_ratio"]) <= thresholds["secondary_annual_turnover_ratio_max"],
        }
        verdict = "GO" if all(passes.values()) else "NO-GO"
        verdicts.setdefault(mode, {})[CAPITAL_VERDICT_LABEL[capital]] = verdict
        print(
            f"{key}: {CAPITAL_VERDICT_LABEL[capital]} {verdict} "
            f"(ΔCAGR={float(oos['delta_cagr_pp']):+.6f}pp, "
            f"ΔMaxDD={float(oos['delta_max_drawdown_pp']):+.6f}pp, "
            f"turnover_ratio={float(comp['annual_turnover_ratio']):.6f}, "
            f"passes={passes})"
        )

    return verdicts


def main() -> int:
    try:
        verdicts = verify()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    expected = {
        "pure_momentum": {"capacity": "NO-GO", "mechanism": "NO-GO"},
        "quality_momentum": {"capacity": "GO", "mechanism": "NO-GO"},
    }
    if verdicts != expected:
        print(f"FAIL: verdict mismatch: {verdicts!r} != {expected!r}", file=sys.stderr)
        return 1
    print("PASS: B113 F003 artifact checks and adjudication match pre-registered criteria")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
