from datetime import date
from pathlib import Path

from trade.backtest.monthly import run_monthly_backtest
from trade.data.loader import load_fixture_prices
from trade.reporting.reports import generate_backtest_reports
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


def test_report_contains_required_json_sections(tmp_path: Path) -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_monthly_backtest(snapshot.records, parameters, signal_date=date(2024, 10, 31))
    artifacts = generate_backtest_reports(result, snapshot, tmp_path, run_id="unit-run")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert set(artifacts.report) == {
        "run",
        "strategy",
        "data",
        "parameters",
        "execution",
        "portfolio",
        "risk",
        "metrics",
        "outputs",
    }


def test_report_records_signal_execution_prices_and_metadata(tmp_path: Path) -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_monthly_backtest(snapshot.records, parameters, signal_date=date(2024, 10, 31))
    report = generate_backtest_reports(result, snapshot, tmp_path, run_id="unit-run").report

    assert report["run"]["run_id"] == "unit-run"  # type: ignore[index]
    assert report["data"]["data_snapshot_id"] == snapshot.data_snapshot_id  # type: ignore[index]
    assert report["parameters"]["parameter_hash"] == result.signal.parameter_hash  # type: ignore[index]
    assert report["execution"]["signal_price_field"] == "close"  # type: ignore[index]
    assert report["execution"]["execution_price_field"] == "open"  # type: ignore[index]
    assert report["execution"]["execution_assumption"] == "t_plus_1_open"  # type: ignore[index]


def test_markdown_report_does_not_claim_paper_or_live_execution(tmp_path: Path) -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_monthly_backtest(snapshot.records, parameters, signal_date=date(2024, 10, 31))
    artifacts = generate_backtest_reports(result, snapshot, tmp_path, run_id="unit-run")

    markdown = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    assert "data snapshot" in markdown
    assert "parameter hash" in markdown
    assert "paper execution" not in markdown
    assert "live execution" not in markdown
