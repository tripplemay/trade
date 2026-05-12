"""Fixture-first Python workflow entrypoint."""

from __future__ import annotations

from pathlib import Path

from trade.backtest.monthly import run_monthly_backtest
from trade.config.defaults import WorkflowConfig, default_fixture_workflow_config
from trade.data.loader import load_fixture_prices
from trade.reporting.reports import ReportArtifacts, generate_backtest_reports


def run_fixture_workflow(
    output_dir: Path, config: WorkflowConfig | None = None, run_id: str | None = None
) -> ReportArtifacts:
    """Run fixture data through signal, backtest, risk/report layers without live dependencies."""

    workflow_config = config or default_fixture_workflow_config()
    if workflow_config.environment not in {"local", "ci"}:
        raise ValueError("fixture workflow only allows local or ci environments")
    snapshot = load_fixture_prices()
    trading_dates = tuple(sorted({record.date for record in snapshot.records}))
    signal_date = trading_dates[-2]
    result = run_monthly_backtest(
        snapshot.records,
        workflow_config.strategy_parameters,
        workflow_config.backtest_parameters,
        signal_date=signal_date,
    )
    return generate_backtest_reports(result, snapshot, output_dir, run_id=run_id)
