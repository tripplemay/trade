from datetime import date
from pathlib import Path

from trade.backtest.monthly import run_monthly_backtest, run_multi_monthly_backtest
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
    assert (  # type: ignore[index]
        report["execution"]["missing_t_plus_1_open_policy"]
        == "flag_and_fallback_to_signal_close"
    )
    assert report["execution"]["missing_t_plus_1_open_flags"] == ()  # type: ignore[index]
    assert report["execution"]["rebalance_count"] == 1  # type: ignore[index]
    assert report["risk"]["warning_flags"] == (  # type: ignore[index]
        "position_limit_violation:SPY:1.0000>0.3500",
    )
    assert report["risk"]["unexpected_warning_flags"] == (  # type: ignore[index]
        "position_limit_violation:SPY:1.0000>0.3500",
    )


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


def test_multi_rebalance_report_metrics_are_traceable(tmp_path: Path) -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_multi_monthly_backtest(
        snapshot.records,
        (date(2024, 8, 30), date(2024, 9, 30), date(2024, 10, 31)),
        parameters,
    )
    report = generate_backtest_reports(result, snapshot, tmp_path, run_id="multi-run").report
    metrics = report["metrics"]  # type: ignore[index]

    assert len(metrics["monthly_returns"]) == 3  # type: ignore[index]
    assert set(metrics["yearly_returns"]) == {"2024"}  # type: ignore[index]
    assert metrics["annualized_volatility"] != 0.0  # type: ignore[index]
    assert metrics["Sharpe"] != 0.0  # type: ignore[index]
    assert metrics["turnover"] == result.turnover  # type: ignore[index]
    assert metrics["max_drawdown"] <= 0  # type: ignore[index]
    assert metrics["equity_curve"] == report["execution"]["equity_curve"]  # type: ignore[index]
