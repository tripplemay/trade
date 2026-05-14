from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import DataSnapshot, PriceBar
from trade.strategies.regime_adaptive.backtest import (
    RegimeAdaptiveBacktestResult,
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.reports import (
    STRESS_GATE_PASS,
    STRESS_GATE_SKIPPED,
    STRESS_WINDOW_2020,
    STRESS_WINDOW_2022,
    generate_regime_adaptive_reports,
)


def _bars(symbol: str, prices: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
    return [
        PriceBar(
            date=start + timedelta(days=index),
            symbol=symbol,
            open=price * 0.999,
            close=price,
            adjusted_close=price,
            volume=1_000,
        )
        for index, price in enumerate(prices)
    ]


def _rising(length: int, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + step * index for index in range(length)]


def _build_records(length: int = 120) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.0)))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.1 + 0.02 * index)))
    return tuple(rows)


def _make_snapshot(records: tuple[PriceBar, ...]) -> DataSnapshot:
    dates = tuple(sorted({record.date for record in records}))
    symbols = tuple(sorted({record.symbol for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-regime-adaptive-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:regime-adaptive",
        checksum="r" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=symbols,
        trading_calendar_gaps=(),
        manifest_path=None,
        manifest_snapshot_id=None,
    )


def _short_config() -> object:
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def _backtest() -> tuple[tuple[PriceBar, ...], DataSnapshot, RegimeAdaptiveBacktestResult]:
    config = _short_config()
    records = _build_records(120)
    snapshot = _make_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        config,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )
    return records, snapshot, result


def test_generate_regime_adaptive_reports_writes_json_and_markdown(tmp_path: Path) -> None:
    _, snapshot, result = _backtest()

    artifacts = generate_regime_adaptive_reports(result, snapshot, tmp_path, run_id="ra-1")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()


def test_generate_regime_adaptive_reports_payload_contains_required_sections(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-2"
    ).report

    assert set(payload) >= {
        "run",
        "strategy",
        "data",
        "parameters",
        "execution",
        "portfolio",
        "metrics",
        "account_risk",
        "baselines",
        "stress_validation",
        "research_limitations",
    }


def test_generate_regime_adaptive_reports_records_per_period_regime_and_gating_history(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-3"
    ).report

    rebalance_trace = payload["execution"]["rebalance_trace"]
    assert len(rebalance_trace) == len(result.rebalance_results)
    for period_payload in rebalance_trace:
        assert "regime" in period_payload
        assert "gating" in period_payload
        assert period_payload["regime"]["regime"] in {"NORMAL", "BEAR", "CRISIS"}


def test_generate_regime_adaptive_reports_includes_calculated_60_40_baseline(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-4"
    ).report

    baselines = payload["baselines"]
    assert baselines["static_60_40"]["label"] == "static_60_40_etf_defensive_quarterly_rebalance"
    assert baselines["static_60_40"]["weights"] == {"SPY": 0.6, "AGG": 0.4}
    assert baselines["static_60_40"]["ending_value"] > 0


def test_generate_regime_adaptive_reports_includes_b006_b010_baseline_placeholders(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-5"
    ).report

    baselines = payload["baselines"]
    assert "global_etf_momentum" in baselines
    assert "risk_parity" in baselines
    assert baselines["global_etf_momentum"]["status"] in {"computed", "skipped"}
    assert baselines["risk_parity"]["status"] in {"computed", "skipped"}


def test_generate_regime_adaptive_reports_stress_gates_skip_without_snapshot(
    tmp_path: Path,
) -> None:
    """Stress validation must report 'skipped' when fixture data does not cover stress windows."""

    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-6"
    ).report

    stress = payload["stress_validation"]
    assert STRESS_WINDOW_2020 in stress
    assert STRESS_WINDOW_2022 in stress
    assert stress[STRESS_WINDOW_2020]["status"] == STRESS_GATE_SKIPPED
    assert stress[STRESS_WINDOW_2022]["status"] == STRESS_GATE_SKIPPED


def test_generate_regime_adaptive_reports_does_not_claim_paper_or_live_execution(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    artifacts = generate_regime_adaptive_reports(result, snapshot, tmp_path, run_id="ra-7")

    json_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    for phrase in ("paper execution", "live execution", "broker fill"):
        assert phrase not in json_text
        assert phrase not in markdown_text


def test_generate_regime_adaptive_reports_includes_research_only_disclaimer(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-8"
    ).report

    limitations = payload["research_limitations"]["limitations"]
    assert any("research-only" in entry.lower() for entry in limitations)


def test_generate_regime_adaptive_reports_metrics_include_aggregated_performance(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-9"
    ).report

    metrics = payload["metrics"]
    for key in (
        "CAGR",
        "annualized_volatility",
        "Sharpe",
        "max_drawdown",
        "turnover",
        "transaction_costs",
        "tolerance_band_statistics",
    ):
        assert key in metrics
    assert isinstance(payload["execution"]["equity_curve"], list)
    assert len(payload["execution"]["equity_curve"]) >= 2


def test_generate_regime_adaptive_reports_records_snapshot_references(
    tmp_path: Path,
) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-10"
    ).report

    assert payload["data"]["data_snapshot_id"] == snapshot.data_snapshot_id
    assert payload["data"]["checksum"] == snapshot.checksum


def test_generate_regime_adaptive_reports_account_risk_payload(tmp_path: Path) -> None:
    _, snapshot, result = _backtest()
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="ra-11"
    ).report

    account_risk = payload["account_risk"]
    assert account_risk["drawdown_threshold"] == pytest.approx(0.15)
    assert "kill_switch_active" in account_risk
    assert "human_review_required" in account_risk


def test_generate_regime_adaptive_reports_stress_validation_pass_when_drawdown_below_threshold(
    tmp_path: Path,
) -> None:
    """A backtest whose result equity curve fully covers a stress window must run the gate."""

    config = _short_config()
    records = _build_records(400)  # > 2020-02-01 stress window length
    snapshot = _make_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 5, 9), date(2024, 6, 28), date(2024, 8, 17)),
        config,
    )
    payload = generate_regime_adaptive_reports(
        result,
        snapshot,
        tmp_path,
        run_id="ra-stress",
        stress_windows=(
            (date(2024, 3, 25), date(2024, 8, 15), "rising_market_window"),
        ),
    ).report

    assert "rising_market_window" in payload["stress_validation"]
    rising_window = payload["stress_validation"]["rising_market_window"]
    assert rising_window["status"] == STRESS_GATE_PASS
    assert rising_window["max_drawdown"] >= -0.15
