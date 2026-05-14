"""B015 activation-policy comparison report (Markdown + JSON sidecar).

Turns an :class:`ActivationPolicyComparisonResult` plus a cross-strategy baseline dict
into the research-only deliverable described in B015 F004:

- 3-policy metrics table (annualized return / volatility / Sharpe / max drawdown /
  turnover / L1 firing rate / ending value).
- Per-policy 2020 + 2022 stress-window verdict.
- Cross-strategy baselines (B006 momentum, B010 risk parity, static 60/40) reused from
  B014's comparison sidecar when available.
- Narrative comparing only_non_normal / only_crisis against always_on with respect to
  the absolute-return gap versus static 60/40.
- Research-only disclaimer and explicit `real_data_status` flag noting whether the
  underlying comparison ran against the B014 yfinance snapshot or skipped it.

The artifact is research-only and never authorizes any paper or production order flow.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from trade.strategies.regime_adaptive.activation_policy_comparison import (
    COMPARISON_STATUS_SKIPPED,
    ActivationPolicyComparisonResult,
    PolicyComparisonRow,
)
from trade.strategies.regime_adaptive.config import POLICY_ALWAYS_ON

DEFAULT_B014_COMPARISON_PATH: Path = Path(
    "docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json"
)

NARRATIVE_GAP_SHRUNK = "shrunk"
NARRATIVE_GAP_UNCHANGED = "unchanged"
NARRATIVE_GAP_WIDENED = "widened"
NARRATIVE_REAL_DATA_SKIPPED = "real_data_skipped"
NARRATIVE_REAL_DATA_RAN = "real_data_ran"

RESEARCH_ONLY_DISCLAIMER = (
    "research-only B015 activation-policy comparison; never authorizes paper or "
    "production order flow."
)
RESEARCH_LIMITATIONS_DEFAULT: tuple[str, ...] = (
    RESEARCH_ONLY_DISCLAIMER,
    "no_paper_or_production_order_flow_authorized",
    "fixture_or_research_snapshot_only",
    "stress_gates_require_real_historical_snapshot_to_meaningfully_compare",
    "B013 strategy code unchanged in B015; activation policy is an opt-in config knob",
)

DEFAULT_GAP_TOLERANCE_DOLLARS = 100.0

BASELINE_REQUIRED_KEYS: tuple[str, ...] = ("global_etf_momentum", "risk_parity", "static_60_40")


@dataclass(frozen=True, slots=True)
class ActivationPolicyReportArtifacts:
    run_id: str
    json_path: Path
    markdown_path: Path
    payload: dict[str, object]


def build_activation_policy_report_payload(
    comparison: ActivationPolicyComparisonResult,
    *,
    baseline_strategies: Mapping[str, Mapping[str, object]],
    run_id: str,
    report_date: date,
) -> dict[str, object]:
    """Build the JSON-safe report payload for the B015 activation-policy comparison."""

    policy_rows = [_serialize_policy_row(row) for row in comparison.policy_rows]
    real_data = _real_data_block(comparison)
    baselines = {key: dict(baseline_strategies.get(key, {})) for key in BASELINE_REQUIRED_KEYS}
    narrative = _build_narrative_block(comparison, baseline_strategies)
    return {
        "run": {
            "run_id": run_id,
            "report_date": report_date.isoformat(),
            "batch": "B015",
            "description": (
                "Comparative backtest of B013 regime-adaptive strategy under three "
                "regime_activation_policy values: always_on (baseline), only_non_normal, "
                "only_crisis. B013 strategy code is unchanged; only the activation policy "
                "config knob varies between rows."
            ),
        },
        "real_data_status": real_data,
        "activation_policy_comparison": {
            "starting_capital": comparison.starting_capital,
            "stress_windows": [
                {
                    "key": key,
                    "window_start": start.isoformat(),
                    "window_end": end.isoformat(),
                }
                for start, end, key in comparison.stress_windows
            ],
            "policy_rows": policy_rows,
        },
        "baselines": baselines,
        "narrative": narrative,
        "research_limitations": {
            "limitations": list(RESEARCH_LIMITATIONS_DEFAULT),
            "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        },
    }


def render_activation_policy_markdown(payload: Mapping[str, object]) -> str:
    """Render the JSON payload into the B015 markdown report."""

    run = cast(dict[str, Any], _section(payload, "run"))
    real_data = cast(dict[str, Any], _section(payload, "real_data_status"))
    comparison_block = cast(dict[str, Any], _section(payload, "activation_policy_comparison"))
    baselines = cast(dict[str, Any], _section(payload, "baselines"))
    narrative = cast(dict[str, Any], _section(payload, "narrative"))
    limitations = cast(dict[str, Any], _section(payload, "research_limitations"))

    policy_rows: list[dict[str, Any]] = list(comparison_block.get("policy_rows", []))
    stress_windows: list[dict[str, Any]] = list(comparison_block.get("stress_windows", []))
    stress_keys = [str(window["key"]) for window in stress_windows]

    lines: list[str] = []
    lines.append(f"# {run['run_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Batch: {run['batch']}")
    lines.append(f"- Report date: {run['report_date']}")
    lines.append(f"- Description: {run['description']}")
    lines.append("")
    lines.append("## Real-Data Status")
    lines.append(f"- Status: {real_data['status']}")
    if real_data.get("manifest_id"):
        lines.append(f"- Snapshot manifest id: {real_data['manifest_id']}")
    if real_data.get("date_range"):
        lines.append(f"- Snapshot date range: {real_data['date_range']}")
    if real_data.get("reason"):
        lines.append(f"- Reason: {real_data['reason']}")
    lines.append("")
    lines.append("## Per-Policy Metrics (B013 regime-adaptive)")
    header = (
        "| policy | annualized_return | annualized_volatility | sharpe | max_drawdown | "
        "turnover | L1 firing rate | ending_value |"
    )
    separator = "|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(separator)
    for row in policy_rows:
        lines.append(
            "| {policy} | {ann_return:.6f} | {ann_vol:.6f} | {sharpe:.6f} | "
            "{max_dd:.6f} | {turnover:.6f} | {l1:.6f} | {ending:.2f} |".format(
                policy=row["policy"],
                ann_return=row["annualized_return"],
                ann_vol=row["annualized_volatility"],
                sharpe=row["sharpe"],
                max_dd=row["max_drawdown"],
                turnover=row["turnover"],
                l1=row["l1_firing_rate"],
                ending=row["ending_value"],
            )
        )
    lines.append("")

    lines.append("## Stress Window Verdict Per Policy")
    if stress_keys:
        header_stress = (
            "| policy | "
            + " | ".join(f"{key} status / max_dd" for key in stress_keys)
            + " |"
        )
        separator_stress = "|---|" + "|".join(["---"] * len(stress_keys)) + "|"
        lines.append(header_stress)
        lines.append(separator_stress)
        for row in policy_rows:
            cells = [str(row["policy"])]
            for key in stress_keys:
                status = row["stress_window_status"].get(key, "n/a")
                value = row["stress_window_max_drawdowns"].get(key)
                cell = f"{status} / {value:.6f}" if isinstance(value, (int, float)) else status
                cells.append(cell)
            lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Cross-Strategy Baselines (reused from B014 sidecar where available)")
    for key in BASELINE_REQUIRED_KEYS:
        raw_baseline = baselines.get(key)
        baseline: dict[str, Any] = raw_baseline if isinstance(raw_baseline, dict) else {}
        ending = baseline.get("ending_value")
        max_dd = baseline.get("max_drawdown")
        lines.append(
            f"- {key}: ending_value={ending}, max_drawdown={max_dd}"
        )
    lines.append("")

    lines.append("## Narrative — Activation Policy vs 60/40 Absolute-Return Gap")
    lines.append(f"- Status: {narrative.get('status')}")
    if narrative.get("status") == NARRATIVE_REAL_DATA_RAN:
        always_on_gap = narrative.get("always_on_gap")
        lines.append(f"- always_on absolute-return gap vs static_60_40: {always_on_gap}")
        for alt_key in ("only_non_normal", "only_crisis"):
            section = narrative.get(alt_key)
            if isinstance(section, dict):
                lines.append(
                    f"- {alt_key}: verdict={section.get('verdict')}, "
                    f"gap_vs_60_40={section.get('gap')}, "
                    f"delta_from_always_on={section.get('delta_from_always_on')}"
                )
    else:
        lines.append(f"- Note: {narrative.get('note')}")
    lines.append("")

    lines.append("## Research Limitations")
    for limitation in limitations.get("limitations", []):
        lines.append(f"- {limitation}")
    lines.append("")
    lines.append(f"_Disclaimer: {limitations['disclaimer']}_")
    lines.append("")

    return "\n".join(lines)


def build_gap_narrative(
    *,
    always_on_ending: float,
    only_non_normal_ending: float,
    only_crisis_ending: float,
    baseline_60_40_ending: float,
    tolerance_dollars: float = DEFAULT_GAP_TOLERANCE_DOLLARS,
) -> dict[str, object]:
    always_on_gap = baseline_60_40_ending - always_on_ending
    return {
        "status": NARRATIVE_REAL_DATA_RAN,
        "always_on_ending": always_on_ending,
        "baseline_60_40_ending": baseline_60_40_ending,
        "always_on_gap": always_on_gap,
        "tolerance_dollars": tolerance_dollars,
        "only_non_normal": _gap_block(
            "only_non_normal",
            ending=only_non_normal_ending,
            always_on_ending=always_on_ending,
            baseline_60_40_ending=baseline_60_40_ending,
            tolerance_dollars=tolerance_dollars,
        ),
        "only_crisis": _gap_block(
            "only_crisis",
            ending=only_crisis_ending,
            always_on_ending=always_on_ending,
            baseline_60_40_ending=baseline_60_40_ending,
            tolerance_dollars=tolerance_dollars,
        ),
    }


def _gap_block(
    policy: str,
    *,
    ending: float,
    always_on_ending: float,
    baseline_60_40_ending: float,
    tolerance_dollars: float,
) -> dict[str, object]:
    alt_gap = baseline_60_40_ending - ending
    always_on_gap = baseline_60_40_ending - always_on_ending
    delta = always_on_gap - alt_gap  # positive means alternative is closer to 60/40
    if abs(delta) <= tolerance_dollars:
        verdict = NARRATIVE_GAP_UNCHANGED
    elif delta > 0:
        verdict = NARRATIVE_GAP_SHRUNK
    else:
        verdict = NARRATIVE_GAP_WIDENED
    return {
        "policy": policy,
        "ending": ending,
        "gap": alt_gap,
        "delta_from_always_on": delta,
        "verdict": verdict,
    }


def load_b014_comparison_baselines(path: Path) -> dict[str, dict[str, object]]:
    """Return per-strategy metrics from B014's cross-strategy comparison sidecar."""

    if not path.is_file():
        raise FileNotFoundError(f"B014 comparison sidecar not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    strategies = payload.get("comparison", {}).get("strategies", {})
    if not isinstance(strategies, dict):
        raise ValueError(f"B014 sidecar comparison.strategies missing or malformed: {path}")
    baselines: dict[str, dict[str, object]] = {}
    static_60_40_baseline = payload.get("baselines", {}).get("static_60_40", {})
    for key in BASELINE_REQUIRED_KEYS:
        source = strategies.get(key, {})
        if key == "static_60_40" and isinstance(static_60_40_baseline, dict):
            # B014 separates ending_value into baselines.static_60_40; merge into one block.
            merged = {**static_60_40_baseline, **source}
        else:
            merged = dict(source)
        baselines[key] = merged
    return baselines


def generate_activation_policy_report(
    comparison: ActivationPolicyComparisonResult,
    *,
    baseline_strategies: Mapping[str, Mapping[str, object]],
    output_dir: Path,
    run_id: str,
    report_date: date,
) -> ActivationPolicyReportArtifacts:
    """Build the payload and emit ``<run_id>.md`` + ``<run_id>.json`` under ``output_dir``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_activation_policy_report_payload(
        comparison,
        baseline_strategies=baseline_strategies,
        run_id=run_id,
        report_date=report_date,
    )
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_activation_policy_markdown(payload), encoding="utf-8")
    return ActivationPolicyReportArtifacts(
        run_id=run_id,
        json_path=json_path,
        markdown_path=markdown_path,
        payload=payload,
    )


def _serialize_policy_row(row: PolicyComparisonRow) -> dict[str, object]:
    return {
        "policy": row.policy,
        "annualized_return": row.annualized_return,
        "annualized_volatility": row.annualized_volatility,
        "sharpe": row.sharpe,
        "max_drawdown": row.max_drawdown,
        "turnover": row.turnover,
        "rebalance_count": row.rebalance_count,
        "regime_distribution": dict(row.regime_distribution),
        "l1_firing_rate": row.l1_firing_rate,
        "stress_window_max_drawdowns": dict(row.stress_window_max_drawdowns),
        "stress_window_status": dict(row.stress_window_status),
        "ending_value": row.ending_value,
        "cost_amount": row.cost_amount,
    }


def _real_data_block(comparison: ActivationPolicyComparisonResult) -> dict[str, object]:
    block: dict[str, object] = {
        "status": comparison.snapshot_status,
        "reason": comparison.snapshot_reason,
        "manifest_id": comparison.snapshot_manifest_id,
    }
    if comparison.snapshot_date_range is not None:
        start, end = comparison.snapshot_date_range
        block["date_range"] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    return block


def _build_narrative_block(
    comparison: ActivationPolicyComparisonResult,
    baseline_strategies: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if comparison.snapshot_status == COMPARISON_STATUS_SKIPPED:
        return {
            "status": NARRATIVE_REAL_DATA_SKIPPED,
            "note": (
                "Real B014 yfinance snapshot was not present; only the in-memory comparison "
                "ran. Re-run with the snapshot manifest available to populate the real-data "
                "narrative."
            ),
        }
    static_baseline = baseline_strategies.get("static_60_40", {}) or {}
    baseline_ending = _coerce_float(static_baseline.get("ending_value"))
    by_policy = {row.policy: row.ending_value for row in comparison.policy_rows}
    always_on_ending = by_policy.get(POLICY_ALWAYS_ON)
    only_non_normal_ending = by_policy.get("only_non_normal")
    only_crisis_ending = by_policy.get("only_crisis")
    if any(
        value is None
        for value in (
            baseline_ending,
            always_on_ending,
            only_non_normal_ending,
            only_crisis_ending,
        )
    ):
        return {
            "status": NARRATIVE_REAL_DATA_SKIPPED,
            "note": (
                "Could not compute the 60/40 gap narrative because one or more required "
                "ending values were missing from the comparison or baselines."
            ),
        }
    # mypy: at this point all four values are non-None thanks to the guard above.
    assert always_on_ending is not None
    assert only_non_normal_ending is not None
    assert only_crisis_ending is not None
    assert baseline_ending is not None
    return build_gap_narrative(
        always_on_ending=always_on_ending,
        only_non_normal_ending=only_non_normal_ending,
        only_crisis_ending=only_crisis_ending,
        baseline_60_40_ending=baseline_ending,
    )


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _section(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"report section {key} must be a Mapping; got {type(value).__name__}")
    return value
