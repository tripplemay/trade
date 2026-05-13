"""Safety regression coverage for the B010 Risk Parity research path."""

from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import DataSnapshot, PriceBar
from trade.reporting.risk_parity import generate_risk_parity_reports
from trade.strategies.risk_parity import RiskParityParameters, generate_risk_parity_signal

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RISK_PARITY_MODULE_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "trade" / "strategies" / "risk_parity.py",
    PROJECT_ROOT / "trade" / "backtest" / "risk_parity.py",
    PROJECT_ROOT / "trade" / "reporting" / "risk_parity.py",
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
    "live trading",
    "paper broker",
    "paper execution",
    "paper trading",
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


def _synthetic_daily_history(
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
        source="unit-risk-parity-safety-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:risk-parity-safety-unit",
        checksum="c" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=symbols,
        trading_calendar_gaps=(),
        manifest_path=None,
        manifest_snapshot_id=None,
    )


def test_risk_parity_modules_do_not_import_network_or_credential_clients() -> None:
    for module_path in RISK_PARITY_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES
        assert leaks == set(), (
            f"{module_path} imports forbidden network/credential modules: {leaks}"
        )


def test_risk_parity_modules_do_not_import_brokers_ai_or_public_import_paths() -> None:
    for module_path in RISK_PARITY_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_BROKER_AI_PUBLIC_IMPORT_MODULES
        assert (
            leaks == set()
        ), f"{module_path} must not import broker/AI/public-import paths: {leaks}"


def test_risk_parity_modules_do_not_import_frontend_or_dashboard_dependencies() -> None:
    for module_path in RISK_PARITY_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_FRONTEND_OR_DASHBOARD_MODULES
        assert (
            leaks == set()
        ), f"{module_path} must not pull in frontend/dashboard frameworks: {leaks}"


def test_risk_parity_signal_runs_offline_without_env_or_secrets(
    monkeypatch: Any,
) -> None:
    for env_name in (
        "API_KEY",
        "BROKER_API_KEY",
        "IBKR_API_KEY",
        "LIVE_TRADING_AUTHORIZATION",
        "OPENAI_API_KEY",
        "POLYGON_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)
    records = _synthetic_daily_history(("SPY", "AGG", "SGOV"), 90)
    parameters = RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
    )

    signal = generate_risk_parity_signal(records, parameters)

    assert signal.target_weights
    assert signal.parameters.max_exposure <= 1.0


def test_risk_parity_backtest_completes_without_socket_or_filesystem_writes_outside_output_dir(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in risk parity safety guard")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    fixtures_dir = PROJECT_ROOT / "trade" / "data" / "fixtures"
    fixtures_before = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())

    records = _synthetic_daily_history(("SPY", "AGG", "SGOV"), 90)
    snapshot = _wrap_snapshot(records)
    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10),),
        RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
        ),
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )
    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="offline-safety")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()

    fixtures_after = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())
    assert fixtures_after == fixtures_before, (
        "risk parity pipeline must not write generated market data into committed fixtures"
    )


def test_risk_parity_reports_do_not_claim_paper_or_live_execution(tmp_path: Path) -> None:
    records = _synthetic_daily_history(("SPY", "AGG", "SGOV"), 90)
    snapshot = _wrap_snapshot(records)
    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10),),
        RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
        ),
    )
    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="claim-check")

    json_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    for phrase in FORBIDDEN_TRADE_TERMS_IN_REPORT:
        assert phrase not in json_text, f"forbidden phrase {phrase!r} appeared in JSON report"
        assert phrase not in markdown_text, (
            f"forbidden phrase {phrase!r} appeared in Markdown report"
        )


def test_risk_parity_default_parameters_avoid_broker_or_live_language() -> None:
    parameters = RiskParityParameters()
    parameter_repr = repr(parameters).lower()
    for phrase in ("broker", "paper", "live", "place_order", "submit_order"):
        assert phrase not in parameter_repr, (
            f"default parameters expose forbidden phrase {phrase!r}: {parameter_repr}"
        )


def test_risk_parity_backtest_rejects_leverage_via_max_exposure_validation() -> None:
    leveraged_parameters = RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        max_exposure=1.5,
    )

    with pytest.raises(Exception, match="leverage"):
        run_risk_parity_monthly_backtest(
            _synthetic_daily_history(("SPY", "AGG", "SGOV"), 90),
            (date(2024, 3, 10),),
            leveraged_parameters,
        )


def test_risk_parity_workflow_does_not_invoke_public_import_stub(
    tmp_path: Path, monkeypatch: Any
) -> None:
    called = False

    def _flag_call() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("trade.data.public_import.import_public_data_stub", _flag_call)

    records = _synthetic_daily_history(("SPY", "AGG", "SGOV"), 90)
    snapshot = _wrap_snapshot(records)
    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10),),
        RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
        ),
    )
    generate_risk_parity_reports(result, snapshot, tmp_path, run_id="no-public-import-call")

    assert called is False
