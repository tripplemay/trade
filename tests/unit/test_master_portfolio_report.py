import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    MasterPortfolioBacktestResult,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import DataSnapshot, PriceBar
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    MasterPortfolioParameters,
    MasterSleeveConfig,
)
from trade.reporting.master_portfolio import generate_master_portfolio_reports
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow
from trade.strategies.risk_parity import RiskParityParameters

Q1_END = date(2024, 3, 31)
Q2_END = date(2024, 6, 30)
Q3_END = date(2024, 9, 30)
MULTI_QUARTER_DAYS = 275


def _synthetic_daily_universe(
    symbols: tuple[str, ...], observations: int
) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for symbol_index, symbol in enumerate(symbols):
        price = 100.0 + symbol_index * 10.0
        for index in range(observations):
            if index:
                price *= 1.0 + (0.003 * (symbol_index + 1) if index % 2 else -0.002)
            records.append(
                PriceBar(
                    date=start + timedelta(days=index),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
    return tuple(records)


def _make_snapshot(records: tuple[PriceBar, ...]) -> DataSnapshot:
    dates = tuple(sorted({record.date for record in records}))
    symbols = tuple(sorted({record.symbol for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-master-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:master-unit",
        checksum="m" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=symbols,
        trading_calendar_gaps=(),
        manifest_path=None,
        manifest_snapshot_id=None,
    )


def _short_momentum_params() -> MomentumParameters:
    return MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )


def _short_risk_parity_params() -> RiskParityParameters:
    return RiskParityParameters(
        universe=("SPY", "VEA", "AGG", "GLD", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.5,
    )


def _run_default_master_backtest() -> tuple[
    tuple[PriceBar, ...], DataSnapshot, MasterPortfolioBacktestResult
]:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)
    snapshot = _make_snapshot(records)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0
        ),
    )
    return records, snapshot, result


def test_master_portfolio_report_writes_json_and_markdown(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()

    artifacts = generate_master_portfolio_reports(result, snapshot, tmp_path, run_id="master-1")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()


def test_master_portfolio_report_contains_required_sections(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()

    artifacts = generate_master_portfolio_reports(result, snapshot, tmp_path, run_id="master-1")
    report = artifacts.report

    assert set(report) >= {
        "run",
        "strategy",
        "data",
        "parameters",
        "execution",
        "portfolio",
        "metrics",
        "account_risk",
        "baseline",
        "research_limitations",
    }


def test_master_portfolio_report_records_per_child_contributions(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-2"
    ).report

    rebalance_trace = report["execution"]["rebalance_trace"]  # type: ignore[index]
    assert len(rebalance_trace) == len(result.rebalance_results)
    for period_payload in rebalance_trace:
        sleeve_contributions = period_payload["sleeve_contributions"]
        assert len(sleeve_contributions) == 4
        sleeve_ids = {contribution["sleeve_id"] for contribution in sleeve_contributions}
        assert sleeve_ids == {
            "momentum",
            "risk_parity",
            "satellite_us_quality",
            "satellite_hk_china",
        }


def test_master_portfolio_report_records_planning_vs_effective_weights(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-3"
    ).report

    planning_weights = report["parameters"]["planning_weights"]  # type: ignore[index]
    assert planning_weights == {
        "momentum": 0.40,
        "risk_parity": 0.30,
        "satellite_us_quality": 0.20,
        "satellite_hk_china": 0.10,
    }

    first_period = report["execution"]["rebalance_trace"][0]  # type: ignore[index]
    assert "effective_weights" in first_period


def test_master_portfolio_report_contains_calculated_60_40_baseline(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-4"
    ).report

    baseline = report["baseline"]  # type: ignore[index]
    assert baseline["label"] == "static_60_40_etf_defensive_quarterly_rebalance"
    assert "BL-B010-S2" in baseline["followups_absorbed"]
    assert baseline["weights"] == {"SPY": 0.6, "AGG": 0.4}
    assert baseline["ending_value"] > 0
    assert isinstance(baseline["equity_curve"], list)
    assert len(baseline["equity_curve"]) >= 2


def test_master_portfolio_report_does_not_claim_paper_or_live_execution(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    artifacts = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-5"
    )

    json_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    for phrase in ("paper execution", "live execution", "broker fill"):
        assert phrase not in json_text
        assert phrase not in markdown_text


def test_master_portfolio_report_exposes_account_risk_state_in_payload(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-6"
    ).report

    account_risk = report["account_risk"]  # type: ignore[index]
    assert account_risk["kill_switch_active"] is False
    assert account_risk["kill_switch_triggered_at"] is None
    assert account_risk["kill_switch_trigger_drawdown"] is None
    assert account_risk["human_review_required"] is False
    assert account_risk["drawdown_threshold"] == pytest.approx(0.15)
    assert "high_water_mark" in account_risk


def test_master_portfolio_report_exposes_kill_switch_state_when_active(tmp_path: Path) -> None:
    """When the kill-switch fires during the backtest, the report must surface it."""
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for index in range(MULTI_QUARTER_DAYS):
        if index <= 90:
            base = 100.0 + 0.05 * index
        elif index <= 180:
            base = 104.5 - 0.32 * (index - 90)
        else:
            base = 75.7
        spy = base + (0.1 if index % 2 else -0.1)
        records.append(
            PriceBar(start + timedelta(days=index), "SPY", spy * 0.999, spy, spy, 1000)
        )
        sgov = 100.0 + (0.001 if index % 2 else -0.001)
        records.append(
            PriceBar(start + timedelta(days=index), "SGOV", sgov, sgov, sgov, 1000)
        )
    crash_records = tuple(records)
    snapshot = _make_snapshot(crash_records)
    custom_master = MasterPortfolioParameters(
        sleeves=(
            MasterSleeveConfig(
                sleeve_id="rp",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="risk_parity_vol_target",
                planning_weight=1.0,
                role_label="core",
            ),
        ),
        defensive_asset="SGOV",
    )
    result = run_master_portfolio_quarterly_backtest(
        crash_records,
        (Q1_END, Q2_END, Q3_END),
        master_parameters=custom_master,
        child_parameters=MasterChildStrategyParameters(
            risk_parity=RiskParityParameters(
                universe=("SPY", "SGOV"),
                volatility_lookback=60,
                defensive_asset="SGOV",
                target_volatility=2.0,
            )
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=0.0, slippage_bps=0.0
        ),
    )
    artifacts = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="killed"
    )
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))

    account_risk = payload["account_risk"]
    assert account_risk["kill_switch_active"] is True
    assert account_risk["human_review_required"] is True
    assert account_risk["kill_switch_triggered_at"] is not None
    assert account_risk["kill_switch_trigger_drawdown"] is not None
    assert account_risk["kill_switch_trigger_drawdown"] <= -0.15
    assert isinstance(payload["account_risk"]["events"], list)
    assert any(event["event_kind"] == "triggered" for event in payload["account_risk"]["events"])


def test_master_portfolio_report_includes_research_limitations(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-7"
    ).report

    research_limitations = report["research_limitations"]  # type: ignore[index]
    assert "limitations" in research_limitations
    assert isinstance(research_limitations["limitations"], list)
    assert any("research-only" in entry.lower() for entry in research_limitations["limitations"])


def test_master_portfolio_report_metrics_include_aggregated_performance(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-8"
    ).report

    metrics = report["metrics"]  # type: ignore[index]
    for key in (
        "CAGR",
        "annualized_volatility",
        "Sharpe",
        "max_drawdown",
        "turnover",
        "transaction_costs",
    ):
        assert key in metrics
    assert isinstance(report["execution"]["equity_curve"], list)  # type: ignore[index]
    assert len(report["execution"]["equity_curve"]) >= 2  # type: ignore[index]


def test_master_portfolio_report_records_snapshot_references(tmp_path: Path) -> None:
    _, snapshot, result = _run_default_master_backtest()
    report = generate_master_portfolio_reports(
        result, snapshot, tmp_path, run_id="master-9"
    ).report

    data = report["data"]  # type: ignore[index]
    assert data["data_snapshot_id"] == snapshot.data_snapshot_id
    assert data["checksum"] == snapshot.checksum
