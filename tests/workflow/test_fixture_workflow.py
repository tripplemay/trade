from pathlib import Path
from typing import Any

from trade.workflow import run_fixture_workflow


def test_fixture_workflow_generates_json_and_markdown_reports(tmp_path: Path) -> None:
    artifacts = run_fixture_workflow(tmp_path, run_id="workflow-e2e")
    report = artifacts.report
    execution = report["execution"]  # type: ignore[index]
    metrics = report["metrics"]  # type: ignore[index]

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert report["data"]["data_snapshot_id"]  # type: ignore[index]
    assert report["parameters"]["parameter_hash"]  # type: ignore[index]
    assert execution["rebalance_count"] == 3
    assert len(execution["rebalance_trace"]) == 3
    assert execution["signal_price_field"] == "close"
    assert execution["execution_price_field"] == "open"
    assert execution["missing_t_plus_1_open_policy"] == "flag_and_fallback_to_signal_close"
    assert execution["missing_t_plus_1_open_flags"] == ()
    assert {item["signal_date"] for item in execution["rebalance_trace"]} == {
        "2024-09-30",
        "2024-10-31",
        "2024-11-29",
    }
    assert {item["execution_date"] for item in execution["rebalance_trace"]} == {
        "2024-10-31",
        "2024-11-29",
        "2024-12-31",
    }
    assert execution["execution_assumption"] in {
        "t_plus_1_open",
        "fallback_to_signal_close_due_to_missing_t_plus_1_open",
    }
    assert len(metrics["monthly_returns"]) == 3
    assert metrics["annualized_volatility"] != 0.0
    assert metrics["Sharpe"] != 0.0
    assert metrics["equity_curve"] == execution["equity_curve"]
    assert report["risk"]["warning_flags"] is not None  # type: ignore[index]


def test_fixture_workflow_report_is_deterministic_except_run_metadata(tmp_path: Path) -> None:
    first = run_fixture_workflow(tmp_path / "first", run_id="same-run").report
    second = run_fixture_workflow(tmp_path / "second", run_id="same-run").report

    assert _stable_report(first) == _stable_report(second)


def _stable_report(report: dict[str, object]) -> dict[str, object]:
    stable: dict[str, object] = dict(report)
    run = dict(_section(stable, "run"))
    run.pop("timestamp", None)
    stable["run"] = run
    return stable


def _section(report: dict[str, object], key: str) -> dict[str, Any]:
    value = report[key]
    if not isinstance(value, dict):
        raise AssertionError(f"{key} section must be a dict")
    return value
