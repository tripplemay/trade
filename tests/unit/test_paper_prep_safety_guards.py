"""Safety regression coverage for the B012 Paper Trading prep research path."""

from __future__ import annotations

import ast
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.paper_prep.bridge import (
    BridgeError,
    generate_target_positions_from_master,
)
from trade.paper_prep.broker_adapter import FORBIDDEN_BROKER_SDK_MODULES
from trade.paper_prep.mock_broker import (
    DEFAULT_JOURNAL_PATH,
    MockBroker,
    default_account_state,
)
from trade.paper_prep.target_positions import (
    DISCLAIMER,
    AccountState,
)
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow
from trade.strategies.risk_parity import RiskParityParameters

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_PREP_DIR = PROJECT_ROOT / "trade" / "paper_prep"
PAPER_PREP_MODULE_PATHS: tuple[Path, ...] = tuple(PAPER_PREP_DIR.rglob("*.py"))

FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES: frozenset[str] = frozenset(
    {
        "boto3",
        "google.cloud",
        "http.client",
        "ibapi",
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

FORBIDDEN_TRADE_TERMS: tuple[str, ...] = (
    "broker fill",
    "executed-order",
    "live execution",
    "paper broker",
    "paper execution",
    "place_order",
    "submit_order",
)

FORBIDDEN_API_HOSTS: tuple[str, ...] = (
    "alpaca.markets",
    "api.alpaca.markets",
    "api.tradier.com",
    "paper-api.alpaca.markets",
    "polygon.io",
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


def _master_result() -> Any:
    records = _synthetic_daily_universe(("SPY", "VEA", "AGG", "GLD", "SGOV"), 275)
    return run_master_portfolio_quarterly_backtest(
        records,
        (date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30)),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0
        ),
    )


def test_paper_prep_modules_do_not_import_forbidden_broker_sdks() -> None:
    forbidden = set(FORBIDDEN_BROKER_SDK_MODULES)
    for module_path in PAPER_PREP_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & forbidden
        assert leaks == set(), (
            f"{module_path} imports forbidden broker SDK module: {leaks}"
        )


def test_paper_prep_modules_do_not_import_network_or_credential_clients() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES
        assert leaks == set(), (
            f"{module_path} imports forbidden network/credential module: {leaks}"
        )


def test_paper_prep_modules_do_not_import_frontend_or_dashboard_dependencies() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_FRONTEND_OR_DASHBOARD_MODULES
        assert leaks == set(), (
            f"{module_path} must not pull in frontend/dashboard frameworks: {leaks}"
        )


def test_paper_prep_sources_never_reference_paper_or_live_trading_api_hosts() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        source = module_path.read_text(encoding="utf-8").lower()
        for host in FORBIDDEN_API_HOSTS:
            assert host not in source, f"{module_path} references forbidden host {host!r}"


def test_paper_prep_sources_do_not_use_paper_or_live_execution_language() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        source = module_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_TRADE_TERMS:
            assert phrase not in source, f"{module_path} contains forbidden phrase {phrase!r}"


def test_paper_prep_sources_do_not_read_os_environ_or_secrets() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        source = module_path.read_text(encoding="utf-8")
        assert "os.environ" not in source, f"{module_path} reads os.environ"
        assert "os.getenv" not in source, f"{module_path} reads os.getenv"
        assert "secrets.token" not in source, f"{module_path} pulls a secrets token"


def test_paper_prep_module_docstrings_label_research_only() -> None:
    for module_path in PAPER_PREP_MODULE_PATHS:
        if module_path.name == "__init__.py":
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            docstring = ast.get_docstring(tree) or ""
            assert "research-only" in docstring.lower() or "research only" in docstring.lower()
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree) or ""
        assert "research-only" in docstring.lower() or "research only" in docstring.lower(), (
            f"{module_path} missing research-only disclaimer in docstring"
        )


def test_mock_broker_default_construction_does_not_touch_network(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in paper-prep safety guard")

    monkeypatch.setattr("socket.socket", _refuse_socket)
    monkeypatch.setattr("os.environ", {})

    broker = MockBroker(
        account_state=default_account_state(),
        journal_path=tmp_path / "journal.jsonl",
    )

    assert broker.get_account_state().cash == 250_000.0


def test_default_journal_path_resides_under_data_paper_prep() -> None:
    """The default journal path must live under data/paper-prep, which is gitignored."""

    assert DEFAULT_JOURNAL_PATH.parts[:2] == ("data", "paper-prep")
    assert ".jsonl" in DEFAULT_JOURNAL_PATH.name


def test_mock_broker_journal_lines_carry_research_only_disclaimer(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.jsonl"
    broker = MockBroker(
        account_state=default_account_state(),
        journal_path=journal_path,
        clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
    )

    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:safety",
        clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
    )
    broker.submit_target_positions(positions)

    payload = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["target_positions"]["disclaimer"] == DISCLAIMER
    assert "research-only" in payload["target_positions"]["disclaimer"].lower()


def test_bridge_from_master_fails_closed_on_missing_signal_date_regression() -> None:
    with pytest.raises(BridgeError, match="signal_date"):
        generate_target_positions_from_master(
            _master_result(),
            account_state=default_account_state(),
            signal_date=date(2024, 5, 15),
            snapshot_id="fixture:safety",
            clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
        )


def test_bridge_from_master_rejects_account_state_with_zero_capacity() -> None:
    """An account with no capacity collapses every exposure to zero rather than leverage."""

    zero_account = AccountState(
        account_state_id="research-account-default",
        cash=0.0,
        equity_value=0.0,
        open_positions={},
    )
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=zero_account,
        snapshot_id="fixture:safety",
        clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
    )
    total_dollar = (
        sum(entry.target_dollar_exposure for entry in positions.entries)
        + positions.defensive_allocation.dollar_exposure
    )
    assert total_dollar == 0.0


def test_paper_prep_pipeline_does_not_modify_committed_fixtures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    fixtures_dir = PROJECT_ROOT / "trade" / "data" / "fixtures"
    fixtures_before = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())

    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in paper-prep safety guard")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    broker = MockBroker(
        account_state=default_account_state(),
        journal_path=tmp_path / "journal.jsonl",
        clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
    )
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:safety",
        clock=lambda: datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC),
    )
    broker.submit_target_positions(positions)

    fixtures_after = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())
    assert fixtures_after == fixtures_before
