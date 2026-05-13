import json
from pathlib import Path
from typing import Any

from trade.config.defaults import default_fixture_workflow_config
from trade.data.loader import load_fixture_prices
from trade.workflow import run_fixture_workflow


def test_fixture_workflow_generates_json_and_markdown_reports(tmp_path: Path) -> None:
    artifacts = run_fixture_workflow(tmp_path, run_id="workflow-e2e")
    report = artifacts.report
    execution = report["execution"]  # type: ignore[index]
    metrics = report["metrics"]  # type: ignore[index]

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert report["data"]["data_snapshot_id"]  # type: ignore[index]
    assert report["data"]["quality_flags"]  # type: ignore[index]
    assert report["data"]["research_limitations"]  # type: ignore[index]
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
    assert report["research_limitations"]["limitations"]  # type: ignore[index]
    assert "not_point_in_time_production_data" in report["research_limitations"]["limitations"]  # type: ignore[index]


def test_fixture_workflow_report_is_deterministic_except_run_metadata(tmp_path: Path) -> None:
    first = run_fixture_workflow(tmp_path / "first", run_id="same-run").report
    second = run_fixture_workflow(tmp_path / "second", run_id="same-run").report

    assert _stable_report(first) == _stable_report(second)


def test_workflow_uses_explicit_snapshot_without_changing_default(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot_dir = tmp_path / "data" / "public-cache"
    snapshot_dir.mkdir(parents=True)
    snapshot_path = snapshot_dir / "provider-prices.json"
    fixture = load_fixture_prices()
    snapshot_path.write_text(
        json.dumps(
            {
                "source": "manual-public-data-import",
                "adjusted_price_policy": "public_best_effort_adjusted_close",
                "records": [
                    {
                        "date": record.date.isoformat(),
                        "symbol": record.symbol,
                        "open": record.open,
                        "close": record.close,
                        "adjusted_close": record.adjusted_close,
                        "volume": record.volume,
                    }
                    for record in fixture.records
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = snapshot_dir / "provider-prices-manifest.json"
    manifest_path.write_text(
        json.dumps({"snapshot_id": "public:provider:abc123"}),
        encoding="utf-8",
    )
    config = default_fixture_workflow_config()
    snapshot_config = type(config)(
        environment=config.environment,
        strategy_budget=config.strategy_budget,
        strategy_parameters=config.strategy_parameters,
        backtest_parameters=config.backtest_parameters,
        snapshot_path=Path("data/public-cache/provider-prices.json"),
    )

    explicit = run_fixture_workflow(
        tmp_path / "explicit", config=snapshot_config, run_id="explicit"
    )
    default = run_fixture_workflow(tmp_path / "default", run_id="default")

    assert explicit.report["data"]["data_snapshot_id"].startswith("snapshot:")  # type: ignore[index]
    assert explicit.report["data"]["snapshot_kind"] == "imported_public_research_snapshot"  # type: ignore[index]
    assert explicit.report["data"]["snapshot_manifest"] == {  # type: ignore[index]
        "path": "data/public-cache/provider-prices-manifest.json",
        "snapshot_id": "public:provider:abc123",
    }
    assert "imported_snapshot_data" in explicit.report["data"]["research_limitations"]  # type: ignore[index]
    assert "not-live-trading-ready" in explicit.report["data"]["research_limitations"]  # type: ignore[index]
    assert default.report["data"]["data_snapshot_id"].startswith("fixture:")  # type: ignore[index]
    assert default.report["data"]["snapshot_kind"] == "committed_fixture"  # type: ignore[index]
    assert default.report["data"]["snapshot_manifest"] is None  # type: ignore[index]


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
