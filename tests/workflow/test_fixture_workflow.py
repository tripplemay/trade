from pathlib import Path

from trade.workflow import run_fixture_workflow


def test_fixture_workflow_generates_json_and_markdown_reports(tmp_path: Path) -> None:
    artifacts = run_fixture_workflow(tmp_path, run_id="workflow-e2e")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert artifacts.report["data"]["data_snapshot_id"]  # type: ignore[index]
    assert artifacts.report["parameters"]["parameter_hash"]  # type: ignore[index]
    assert artifacts.report["execution"]["execution_assumption"] in {  # type: ignore[index]
        "t_plus_1_open",
        "fallback_to_signal_close_due_to_missing_t_plus_1_open",
    }
    assert artifacts.report["risk"]["warning_flags"] is not None  # type: ignore[index]
