"""F004 — B015 comparative report tests.

Covers the payload schema, markdown rendering, the B014 cross-strategy baseline loader,
and the report writer that emits docs/test-reports/B015-* artifacts. The artifact is
research-only and never authorizes any paper or production order flow.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from trade.strategies.regime_adaptive.activation_policy_comparison import (
    COMPARISON_STATUS_RAN,
    COMPARISON_STATUS_SKIPPED,
    ActivationPolicyComparisonResult,
    PolicyComparisonRow,
)
from trade.strategies.regime_adaptive.activation_policy_report import (
    DEFAULT_B014_COMPARISON_PATH,
    NARRATIVE_GAP_SHRUNK,
    NARRATIVE_GAP_UNCHANGED,
    NARRATIVE_GAP_WIDENED,
    NARRATIVE_REAL_DATA_SKIPPED,
    build_activation_policy_report_payload,
    build_gap_narrative,
    generate_activation_policy_report,
    load_b014_comparison_baselines,
    render_activation_policy_markdown,
)
from trade.strategies.regime_adaptive.config import (
    POLICY_ALWAYS_ON,
    POLICY_ONLY_CRISIS,
    POLICY_ONLY_NON_NORMAL,
)


def _row(
    policy: str,
    *,
    ann_return: float = 0.08,
    max_dd: float = -0.04,
    ending_value: float = 110_000.0,
    l1_firing_rate: float = 1.0,
    stress_2020: float = -0.05,
    stress_2022: float = -0.02,
    stress_2020_status: str = "pass",
    stress_2022_status: str = "pass",
) -> PolicyComparisonRow:
    return PolicyComparisonRow(
        policy=policy,
        annualized_return=ann_return,
        annualized_volatility=0.12,
        sharpe=ann_return / 0.12,
        max_drawdown=max_dd,
        turnover=12.0,
        rebalance_count=24,
        regime_distribution={"NORMAL": 20, "BEAR": 3, "CRISIS": 1},
        l1_firing_rate=l1_firing_rate,
        stress_window_max_drawdowns={
            "2020_q1_q4": stress_2020,
            "2022_full_year": stress_2022,
        },
        stress_window_status={
            "2020_q1_q4": stress_2020_status,
            "2022_full_year": stress_2022_status,
        },
        ending_value=ending_value,
        cost_amount=120.0,
    )


def _comparison(snapshot_status: str = COMPARISON_STATUS_RAN) -> ActivationPolicyComparisonResult:
    is_ran = snapshot_status == COMPARISON_STATUS_RAN
    return ActivationPolicyComparisonResult(
        snapshot_status=snapshot_status,
        snapshot_reason=None if is_ran else "manifest absent",
        snapshot_manifest_id="regime-adaptive:fake-id" if is_ran else None,
        snapshot_date_range=(date(2022, 7, 1), date(2024, 6, 30)) if is_ran else None,
        starting_capital=100_000.0,
        stress_windows=(
            (date(2020, 2, 1), date(2020, 12, 31), "2020_q1_q4"),
            (date(2022, 1, 1), date(2022, 12, 31), "2022_full_year"),
        ),
        policy_rows=(
            _row(POLICY_ALWAYS_ON, ending_value=125_000.0),
            _row(POLICY_ONLY_NON_NORMAL, ending_value=140_000.0, l1_firing_rate=0.3),
            _row(POLICY_ONLY_CRISIS, ending_value=155_000.0, l1_firing_rate=0.1),
        ),
    )


def _baselines() -> dict[str, dict[str, object]]:
    return {
        "global_etf_momentum": {
            "ending_value": 100_963.19,
            "max_drawdown": -0.0306,
            "CAGR": 0.0037,
        },
        "risk_parity": {
            "ending_value": 104_500.0,
            "max_drawdown": -0.0084,
            "CAGR": 0.020,
        },
        "static_60_40": {
            "ending_value": 158_978.38,
            "max_drawdown": -0.1966,
            "CAGR": 0.184,
        },
    }


def test_build_activation_policy_report_payload_includes_three_policy_rows() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-regime-adaptive-activation-policy-comparison-2026-05-14",
        report_date=date(2026, 5, 14),
    )

    policy_table = payload["activation_policy_comparison"]
    assert isinstance(policy_table, dict)
    rows = policy_table["policy_rows"]
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert {row["policy"] for row in rows} == {
        POLICY_ALWAYS_ON,
        POLICY_ONLY_NON_NORMAL,
        POLICY_ONLY_CRISIS,
    }


def test_build_activation_policy_report_payload_carries_baseline_rows() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    baselines = payload["baselines"]
    assert "global_etf_momentum" in baselines
    assert "risk_parity" in baselines
    assert "static_60_40" in baselines


def test_build_activation_policy_report_payload_stress_verdict_per_policy_present() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    rows = payload["activation_policy_comparison"]["policy_rows"]
    for row in rows:
        assert "stress_window_status" in row
        assert "2020_q1_q4" in row["stress_window_status"]
        assert "2022_full_year" in row["stress_window_status"]


def test_build_activation_policy_report_payload_marks_real_data_skipped_when_skipped() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(snapshot_status=COMPARISON_STATUS_SKIPPED),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    real_data = payload["real_data_status"]
    assert real_data["status"] == COMPARISON_STATUS_SKIPPED
    assert real_data["reason"] is not None


def test_build_activation_policy_report_payload_research_only_disclaimer_present() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    limitations = payload["research_limitations"]
    assert "research-only" in limitations["disclaimer"].lower()


def test_build_gap_narrative_reports_shrunk_when_alternative_closer_to_baseline() -> None:
    payload = build_gap_narrative(
        always_on_ending=125_000.0,
        only_non_normal_ending=140_000.0,
        only_crisis_ending=155_000.0,
        baseline_60_40_ending=160_000.0,
    )

    assert payload["only_non_normal"]["verdict"] == NARRATIVE_GAP_SHRUNK
    assert payload["only_crisis"]["verdict"] == NARRATIVE_GAP_SHRUNK
    assert payload["always_on_gap"] == pytest.approx(160_000.0 - 125_000.0)


def test_build_gap_narrative_reports_widened_when_alternative_further_from_baseline() -> None:
    payload = build_gap_narrative(
        always_on_ending=125_000.0,
        only_non_normal_ending=110_000.0,
        only_crisis_ending=100_000.0,
        baseline_60_40_ending=160_000.0,
    )

    assert payload["only_non_normal"]["verdict"] == NARRATIVE_GAP_WIDENED
    assert payload["only_crisis"]["verdict"] == NARRATIVE_GAP_WIDENED


def test_build_gap_narrative_reports_unchanged_when_difference_within_tolerance() -> None:
    payload = build_gap_narrative(
        always_on_ending=125_000.0,
        only_non_normal_ending=125_050.0,
        only_crisis_ending=124_950.0,
        baseline_60_40_ending=160_000.0,
        tolerance_dollars=200.0,
    )

    assert payload["only_non_normal"]["verdict"] == NARRATIVE_GAP_UNCHANGED
    assert payload["only_crisis"]["verdict"] == NARRATIVE_GAP_UNCHANGED


def test_payload_uses_skipped_narrative_when_real_data_absent() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(snapshot_status=COMPARISON_STATUS_SKIPPED),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    narrative = payload["narrative"]
    assert narrative["status"] == NARRATIVE_REAL_DATA_SKIPPED


def test_render_activation_policy_markdown_contains_policy_table_and_baselines() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    rendered = render_activation_policy_markdown(payload)

    assert "B015" in rendered
    assert "regime_activation_policy" in rendered.lower() or "activation policy" in rendered.lower()
    assert "always_on" in rendered
    assert "only_non_normal" in rendered
    assert "only_crisis" in rendered
    assert "static_60_40" in rendered
    assert "global_etf_momentum" in rendered
    assert "risk_parity" in rendered
    assert "research-only" in rendered.lower()


def test_render_activation_policy_markdown_includes_l1_firing_rate_per_policy() -> None:
    payload = build_activation_policy_report_payload(
        _comparison(),
        baseline_strategies=_baselines(),
        run_id="B015-run",
        report_date=date(2026, 5, 14),
    )

    rendered = render_activation_policy_markdown(payload)

    assert "L1 firing rate" in rendered or "l1_firing_rate" in rendered.lower()


def test_generate_activation_policy_report_writes_md_and_json(tmp_path: Path) -> None:
    artifacts = generate_activation_policy_report(
        _comparison(),
        baseline_strategies=_baselines(),
        output_dir=tmp_path,
        run_id="B015-test-2026-05-14",
        report_date=date(2026, 5, 14),
    )

    assert artifacts.markdown_path.is_file()
    assert artifacts.json_path.is_file()
    assert artifacts.markdown_path.name == "B015-test-2026-05-14.md"
    assert artifacts.json_path.name == "B015-test-2026-05-14.json"

    loaded = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert (
        loaded["run"]["run_id"] == "B015-test-2026-05-14"
    )


def test_load_b014_comparison_baselines_extracts_three_baseline_strategies() -> None:
    if not DEFAULT_B014_COMPARISON_PATH.is_file():
        pytest.skip("B014 cross-strategy comparison sidecar not present")

    baselines = load_b014_comparison_baselines(DEFAULT_B014_COMPARISON_PATH)

    assert "global_etf_momentum" in baselines
    assert "risk_parity" in baselines
    assert "static_60_40" in baselines
    for key in ("global_etf_momentum", "risk_parity", "static_60_40"):
        assert "ending_value" in baselines[key]
        assert "max_drawdown" in baselines[key]


def test_load_b014_comparison_baselines_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_b014_comparison_baselines(tmp_path / "missing.json")
