"""Safety regression coverage for the B013 Regime-Adaptive Multi-Asset research path."""

from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import DataSnapshot, PriceBar
from trade.strategies.regime_adaptive.backtest import (
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.reports import (
    generate_regime_adaptive_reports,
)
from trade.strategies.regime_adaptive.sensitivity import (
    run_regime_adaptive_sensitivity_sweep,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGIME_ADAPTIVE_DIR = PROJECT_ROOT / "trade" / "strategies" / "regime_adaptive"
REGIME_ADAPTIVE_STRATEGY_MODULES: tuple[Path, ...] = tuple(
    path for path in REGIME_ADAPTIVE_DIR.rglob("*.py")
)

FORBIDDEN_BROKER_SDK_MODULES: frozenset[str] = frozenset(
    {
        "alpaca",
        "alpaca_trade_api",
        "futu",
        "futu_api",
        "ib_insync",
        "polygon",
        "tiger",
        "tiger_api",
        "tradier",
    }
)

FORBIDDEN_AI_LLM_MODULES: frozenset[str] = frozenset(
    {
        "anthropic",
        "google.generativeai",
        "langchain",
        "openai",
        "sklearn",
        "tensorflow",
        "torch",
        "transformers",
    }
)

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

FORBIDDEN_FRONTEND_MODULES: frozenset[str] = frozenset(
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

FORBIDDEN_TRADE_TERMS_IN_REPORT: tuple[str, ...] = (
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


def _records(length: int = 120) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.0)))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.1 + 0.02 * index)))
    return tuple(rows)


def _wrap_snapshot(records: tuple[PriceBar, ...]) -> DataSnapshot:
    dates = tuple(sorted({record.date for record in records}))
    symbols = tuple(sorted({record.symbol for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-regime-adaptive-safety",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:regime-adaptive-safety",
        checksum="s" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=symbols,
        trading_calendar_gaps=(),
        manifest_path=None,
        manifest_snapshot_id=None,
    )


def _short_config() -> object:
    from dataclasses import replace

    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def test_regime_adaptive_modules_do_not_import_forbidden_broker_sdks() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_BROKER_SDK_MODULES
        assert leaks == set(), f"{module_path} imports forbidden broker SDK: {leaks}"


def test_regime_adaptive_modules_do_not_import_forbidden_ai_or_ml_sdks() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_AI_LLM_MODULES
        assert leaks == set(), f"{module_path} imports forbidden AI/LLM SDK: {leaks}"


def test_regime_adaptive_modules_do_not_import_forbidden_network_clients() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES
        assert leaks == set(), f"{module_path} imports forbidden network client: {leaks}"


def test_regime_adaptive_modules_do_not_import_frontend_or_dashboard_dependencies() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        imported = _module_imports(module_path)
        leaks = imported & FORBIDDEN_FRONTEND_MODULES
        assert leaks == set(), (
            f"{module_path} must not pull in frontend/dashboard frameworks: {leaks}"
        )


def test_regime_adaptive_modules_never_reference_paper_or_live_api_hosts() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        source = module_path.read_text(encoding="utf-8").lower()
        for host in FORBIDDEN_API_HOSTS:
            assert host not in source, f"{module_path} references forbidden host {host!r}"


def test_regime_adaptive_modules_do_not_use_paper_or_live_execution_language() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        source = module_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_TRADE_TERMS_IN_REPORT:
            assert phrase not in source, f"{module_path} contains forbidden phrase {phrase!r}"


def test_regime_adaptive_strategy_modules_do_not_read_os_environ_or_getenv() -> None:
    """Strategy modules must not read environment variables; scripts/ is excluded by design."""

    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        source = module_path.read_text(encoding="utf-8")
        assert "os.environ" not in source, f"{module_path} reads os.environ"
        assert "os.getenv" not in source, f"{module_path} reads os.getenv"


def test_regime_adaptive_module_docstrings_label_research_only() -> None:
    for module_path in REGIME_ADAPTIVE_STRATEGY_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree) or ""
        assert "research-only" in docstring.lower() or "research only" in docstring.lower(), (
            f"{module_path} missing research-only disclaimer in docstring"
        )


def test_default_fixture_backtest_does_not_open_socket(tmp_path: Path, monkeypatch: Any) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in regime-adaptive safety guard")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    records = _records()
    snapshot = _wrap_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        _short_config(),
        BacktestParameters(starting_capital=100_000.0),
    )
    artifacts = generate_regime_adaptive_reports(result, snapshot, tmp_path, run_id="offline")

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()


def test_default_fixture_backtest_does_not_modify_committed_fixtures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    fixtures_dir = PROJECT_ROOT / "trade" / "data" / "fixtures"
    fixtures_before = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())

    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed during regime-adaptive backtest")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    records = _records()
    snapshot = _wrap_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        _short_config(),
    )
    generate_regime_adaptive_reports(result, snapshot, tmp_path, run_id="fixtures-untouched")

    fixtures_after = sorted(path.name for path in fixtures_dir.iterdir() if path.is_file())
    assert fixtures_after == fixtures_before


def test_default_fixture_reports_do_not_claim_paper_or_live_execution(tmp_path: Path) -> None:
    records = _records()
    snapshot = _wrap_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        _short_config(),
    )
    artifacts = generate_regime_adaptive_reports(result, snapshot, tmp_path, run_id="phrasing")

    json_text = artifacts.json_path.read_text(encoding="utf-8").lower()
    markdown_text = artifacts.markdown_path.read_text(encoding="utf-8").lower()

    for phrase in FORBIDDEN_TRADE_TERMS_IN_REPORT:
        assert phrase not in json_text
        assert phrase not in markdown_text


def test_default_regime_adaptive_config_does_not_carry_broker_or_live_language() -> None:
    config = default_regime_adaptive_config()
    config_repr = repr(config).lower()
    for phrase in ("broker", "paper", "live", "place_order", "submit_order"):
        assert phrase not in config_repr, (
            f"default config exposes forbidden phrase {phrase!r}: {config_repr}"
        )


def test_sensitivity_sweep_module_runs_without_socket(monkeypatch: Any) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in regime-adaptive sweep")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    short_sweep = {
        "target_volatility": (0.06, 0.08, 0.10),
        "tolerance_band": (0.00, 0.03, 0.05),
    }
    result = run_regime_adaptive_sensitivity_sweep(
        records=_records(),
        signal_dates=(date(2024, 3, 20), date(2024, 4, 19)),
        base_config=_short_config(),
        sweep_specification=short_sweep,
    )
    assert len(result.variations) > 0


def test_research_disclaimer_present_in_report_payload(tmp_path: Path) -> None:
    records = _records()
    snapshot = _wrap_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        _short_config(),
    )
    payload = generate_regime_adaptive_reports(
        result, snapshot, tmp_path, run_id="disclaimer"
    ).report

    limitations = payload["research_limitations"]
    assert "research-only" in limitations["disclaimer"].lower()


def test_regime_adaptive_strategy_scan_excludes_scripts_acquisition_path() -> None:
    """The scripts/ acquisition script may legitimately read env in the future; ensure it
    is NOT scanned as a strategy module."""

    strategy_paths = {path.resolve() for path in REGIME_ADAPTIVE_STRATEGY_MODULES}
    script_path = PROJECT_ROOT / "scripts" / "acquire_regime_adaptive_snapshot.py"
    assert script_path.resolve() not in strategy_paths


@pytest.mark.parametrize(
    "monkey_env",
    ["API_KEY", "BROKER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
)
def test_default_fixture_backtest_runs_without_env_vars(
    tmp_path: Path, monkeypatch: Any, monkey_env: str
) -> None:
    monkeypatch.delenv(monkey_env, raising=False)
    records = _records()
    result = run_regime_adaptive_monthly_backtest(
        records,
        (date(2024, 3, 20), date(2024, 4, 19)),
        _short_config(),
    )
    assert result.ending_value > 0
