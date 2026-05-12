import ast
from pathlib import Path
from typing import Any

from trade.ai import __all__ as ai_exports
from trade.brokers import __all__ as broker_exports
from trade.workflow import run_fixture_workflow

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_required_workflow_does_not_require_env_or_api_keys(
    tmp_path: Path, monkeypatch: Any
) -> None:
    for env_name in (
        "API_KEY",
        "BROKER_API_KEY",
        "OPENAI_API_KEY",
        "POLYGON_API_KEY",
        "IBKR_API_KEY",
        "LIVE_TRADING_AUTHORIZATION",
    ):
        monkeypatch.delenv(env_name, raising=False)

    artifacts = run_fixture_workflow(tmp_path, run_id="no-secret")

    assert artifacts.json_path.exists()
    assert artifacts.report["run"]["environment"] == "local_or_ci_fixture"  # type: ignore[index]


def test_no_network_modules_imported_by_trade_package() -> None:
    forbidden_modules = {
        "http.client",
        "requests",
        "socket",
        "urllib.request",
        "websocket",
        "yfinance",
    }
    imported_modules: set[str] = set()
    for source_path in (PROJECT_ROOT / "trade").rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    assert imported_modules.isdisjoint(forbidden_modules)


def test_no_broker_or_live_entrypoints_are_exported() -> None:
    assert broker_exports == []
    forbidden_names = {
        "broker_call",
        "connect",
        "live",
        "order",
        "paper",
        "place",
        "submit",
        "trade",
    }
    broker_source = (PROJECT_ROOT / "trade" / "brokers" / "__init__.py").read_text(encoding="utf-8")

    assert all(name not in broker_source.lower() for name in forbidden_names)


def test_ai_has_no_trade_or_parameter_authority() -> None:
    assert ai_exports == []
    ai_source = (PROJECT_ROOT / "trade" / "ai" / "__init__.py").read_text(encoding="utf-8").lower()

    assert "place_order" not in ai_source
    assert "buy" not in ai_source
    assert "sell" not in ai_source
    assert "rebalance" not in ai_source
    assert "mutate_parameters" not in ai_source
    assert "set_parameters" not in ai_source


def test_reports_do_not_claim_paper_or_live_execution(tmp_path: Path) -> None:
    artifacts = run_fixture_workflow(tmp_path, run_id="guard-report")
    report_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    assert "paper execution" not in report_text
    assert "live execution" not in report_text
    assert "paper execution" not in markdown_text
    assert "live execution" not in markdown_text
    assert "broker fill" not in report_text
    assert "broker fill" not in markdown_text


def test_strategy_and_reporting_do_not_import_brokers_or_ai() -> None:
    guarded_paths = [
        PROJECT_ROOT / "trade" / "strategies",
        PROJECT_ROOT / "trade" / "backtest",
        PROJECT_ROOT / "trade" / "reporting",
        PROJECT_ROOT / "trade" / "workflow.py",
    ]
    imported_modules: set[str] = set()
    for path in guarded_paths:
        source_paths = (path,) if path.is_file() else tuple(path.rglob("*.py"))
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module)

    assert "trade.brokers" not in imported_modules
    assert "trade.ai" not in imported_modules
