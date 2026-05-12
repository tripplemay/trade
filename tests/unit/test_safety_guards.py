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
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BROKER_API_KEY", raising=False)

    artifacts = run_fixture_workflow(tmp_path, run_id="no-secret")

    assert artifacts.json_path.exists()


def test_no_network_modules_imported_by_trade_package() -> None:
    forbidden_modules = {"requests", "urllib.request", "http.client", "socket"}
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
    forbidden_names = {"paper", "live", "order", "submit", "broker_call"}
    broker_source = (PROJECT_ROOT / "trade" / "brokers" / "__init__.py").read_text(encoding="utf-8")

    assert all(name not in broker_source.lower() for name in forbidden_names)


def test_ai_has_no_trade_or_parameter_authority() -> None:
    assert ai_exports == []
    ai_source = (PROJECT_ROOT / "trade" / "ai" / "__init__.py").read_text(encoding="utf-8").lower()

    assert "place_order" not in ai_source
    assert "buy" not in ai_source
    assert "sell" not in ai_source
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
