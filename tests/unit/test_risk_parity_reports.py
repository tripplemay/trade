import json
from datetime import date, timedelta
from pathlib import Path

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import DataSnapshot, PriceBar
from trade.reporting.risk_parity import generate_risk_parity_reports
from trade.strategies.risk_parity import RiskParityParameters


def test_risk_parity_report_contains_metrics_weights_costs_and_limitations(tmp_path: Path) -> None:
    snapshot = _snapshot()
    result = run_risk_parity_monthly_backtest(
        snapshot.records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
        ),
        BacktestParameters(cost_bps=1.0, slippage_bps=2.0),
    )

    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="risk-parity")
    report = artifacts.report

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert report["strategy"]["strategy_id"] == "risk_parity_vol_target"  # type: ignore[index]
    assert report["metrics"]["annualized_volatility"] >= 0  # type: ignore[index]
    assert report["metrics"]["target_volatility"] == 0.08  # type: ignore[index]
    assert report["metrics"]["transaction_costs"] > 0  # type: ignore[index]
    assert (  # type: ignore[index]
        report["metrics"]["baseline_comparison"]["label"]
        == "static_equal_weight_multi_asset_placeholder"
    )
    assert len(report["execution"]["weight_history"]) == 2  # type: ignore[index]
    assert report["data"]["data_snapshot_id"] == snapshot.data_snapshot_id  # type: ignore[index]
    assert "not_point_in_time_production_data" in report["research_limitations"]["limitations"]  # type: ignore[index]


def test_risk_parity_markdown_report_exposes_research_sections(tmp_path: Path) -> None:
    snapshot = _snapshot()
    result = run_risk_parity_monthly_backtest(
        snapshot.records,
        (date(2024, 3, 10),),
        RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
        ),
    )

    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="risk-parity")
    markdown = artifacts.markdown_path.read_text(encoding="utf-8").lower()
    json_report = json.loads(artifacts.json_path.read_text(encoding="utf-8"))

    assert "risk parity report" in markdown
    assert "weight history" in markdown
    assert "baseline comparison" in markdown
    assert "research limitations" in markdown
    assert "paper execution" not in markdown
    assert json_report["strategy"]["no_leverage"] is True


def _snapshot() -> DataSnapshot:
    records = _multi_asset_history(("SPY", "AGG", "SGOV"), 90)
    dates = tuple(sorted({record.date for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-risk-parity-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:risk-parity-unit",
        checksum="b" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=("AGG", "SGOV", "SPY"),
        trading_calendar_gaps=(),
    )


def _multi_asset_history(symbols: tuple[str, ...], observations: int) -> tuple[PriceBar, ...]:
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
