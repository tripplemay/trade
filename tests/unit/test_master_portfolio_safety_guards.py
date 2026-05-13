"""Safety regression coverage for the B011 Master Portfolio research path."""

from __future__ import annotations

import ast
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import DataSnapshot, PriceBar
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    MasterPortfolioParameters,
    MasterSleeveConfig,
    default_master_portfolio_parameters,
)
from trade.reporting.master_portfolio import generate_master_portfolio_reports
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow
from trade.strategies.risk_parity import RiskParityParameters

Q1_END = date(2024, 3, 31)
Q2_END = date(2024, 6, 30)
Q3_END = date(2024, 9, 30)
SINGLE_QUARTER_DAYS = 92
MULTI_QUARTER_DAYS = 275

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_MODULE_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "trade" / "portfolio" / "master.py",
    PROJECT_ROOT / "trade" / "backtest" / "master_portfolio.py",
    PROJECT_ROOT / "trade" / "reporting" / "master_portfolio.py",
)

FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES: frozenset[str] = frozenset(
    {
        "alpaca",
        "boto3",
        "google.cloud",
        "http.client",
        "ibapi",
        "polygon",
        "requests",
        "socket",
        "urllib.request",
        "websocket",
        "yfinance",
    }
)

FORBIDDEN_FRONTEND_OR_DASHBOARD_MODULES: frozenset[str] = frozenset(
    {
        "dash",
        "django",
        "fastapi",
        "flask",
        "gradio",
        "panel",
        "starlette",
        "streamlit",
    }
)

FORBIDDEN_BROKER_AI_PUBLIC_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "trade.ai",
        "trade.brokers",
        "trade.data.public_import",
    }
)

FORBIDDEN_TRADE_TERMS_IN_REPORT: tuple[str, ...] = (
    "broker fill",
    "live execution",
    "paper broker",
    "paper execution",
    "place_order",
    "submit_order",
)


def _module_imports(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


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


def _wrap_snapshot(records: tuple[PriceBar, ...]) -> DataSnapshot:
    dates = tuple(sorted({record.date for record in records}))
    symbols = tuple(sorted({record.symbol for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-master-portfolio-safety-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:master-portfolio-safety",
        checksum="d" * 64,
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


def test_master_modules_do_not_import_network_or_credential_clients() -> None:
    for module_path in MASTER_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES
        assert leaks == set(), (
            f"{module_path} imports forbidden network/credential modules: {leaks}"
        )


def test_master_modules_do_not_import_brokers_ai_or_public_import_paths() -> None:
    for module_path in MASTER_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_BROKER_AI_PUBLIC_IMPORT_MODULES
        assert leaks == set(), (
            f"{module_path} must not import broker/AI/public-import paths: {leaks}"
        )


def test_master_modules_do_not_import_frontend_or_dashboard_dependencies() -> None:
    for module_path in MASTER_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_FRONTEND_OR_DASHBOARD_MODULES
        assert leaks == set(), (
            f"{module_path} must not pull in frontend/dashboard frameworks: {leaks}"
        )


def test_master_portfolio_runs_offline_without_env_or_secrets(monkeypatch: Any) -> None:
    for env_name in (
        "API_KEY",
        "BROKER_API_KEY",
        "IBKR_API_KEY",
        "LIVE_TRADING_AUTHORIZATION",
        "OPENAI_API_KEY",
        "POLYGON_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)

    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )

    assert result.ending_value > 0
    assert result.parameters.max_exposure <= 1.0


def test_master_portfolio_pipeline_does_not_modify_committed_fixtures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in master portfolio safety guard")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    fixtures_dir = PROJECT_ROOT / "trade" / "data" / "fixtures"
    fixtures_before = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())

    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)
    snapshot = _wrap_snapshot(records)
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
    artifacts = generate_master_portfolio_reports(result, snapshot, tmp_path, run_id="offline")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()

    fixtures_after = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())
    assert fixtures_after == fixtures_before, (
        "master portfolio pipeline must not write generated market data into committed fixtures"
    )


def test_master_portfolio_reports_do_not_claim_paper_or_live_execution(
    tmp_path: Path,
) -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)
    snapshot = _wrap_snapshot(records)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )
    artifacts = generate_master_portfolio_reports(result, snapshot, tmp_path, run_id="phrasing")

    json_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    for phrase in FORBIDDEN_TRADE_TERMS_IN_REPORT:
        assert phrase not in json_text, f"forbidden phrase {phrase!r} appeared in JSON report"
        assert phrase not in markdown_text, (
            f"forbidden phrase {phrase!r} appeared in Markdown report"
        )


def test_master_portfolio_default_parameters_avoid_broker_or_live_language() -> None:
    parameters = default_master_portfolio_parameters()
    parameter_repr = repr(parameters).lower()
    for phrase in ("broker", "paper", "live", "place_order", "submit_order"):
        assert phrase not in parameter_repr, (
            f"default parameters expose forbidden phrase {phrase!r}: {parameter_repr}"
        )


def test_master_portfolio_rejects_leverage_via_validation() -> None:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)
    leveraged = MasterPortfolioParameters(max_exposure=1.25)
    with pytest.raises(Exception, match="leverage"):
        run_master_portfolio_quarterly_backtest(
            records,
            (Q1_END,),
            master_parameters=leveraged,
        )


def test_master_portfolio_pipeline_does_not_invoke_public_import_stub(
    tmp_path: Path, monkeypatch: Any
) -> None:
    called = False

    def _flag_call() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("trade.data.public_import.import_public_data_stub", _flag_call)

    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS)
    snapshot = _wrap_snapshot(records)
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
    )
    generate_master_portfolio_reports(result, snapshot, tmp_path, run_id="no-public-import")

    assert called is False


def test_master_portfolio_kill_switch_state_is_deterministic_and_visible_in_report(
    tmp_path: Path,
) -> None:
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
    snapshot = _wrap_snapshot(crash_records)
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

    first_run = run_master_portfolio_quarterly_backtest(
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
    second_run = run_master_portfolio_quarterly_backtest(
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

    assert first_run.ending_value == second_run.ending_value
    assert (
        first_run.account_risk_state.kill_switch_active
        == second_run.account_risk_state.kill_switch_active
    )
    assert (
        first_run.account_risk_state.kill_switch_triggered_at
        == second_run.account_risk_state.kill_switch_triggered_at
    )
    assert first_run.account_risk_state.kill_switch_active is True

    artifacts = generate_master_portfolio_reports(
        first_run, snapshot, tmp_path, run_id="kill-switch-visible"
    )
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["account_risk"]["kill_switch_active"] is True
    assert payload["account_risk"]["human_review_required"] is True
    assert any(
        event["event_kind"] == "triggered" for event in payload["account_risk"]["events"]
    )
