"""B016 F005 — backwards-compat snapshot + safety regression.

Backwards-compat: pin specific numerical outputs from the inverse-vol
path on a deterministic synthetic fixture. If any future change perturbs
the B010 default behaviour, this snapshot mismatches and the test fails.
This complements the existing B010 + B011 + B013 + B015 suites (which all
keep passing without modification) by providing an explicit bit-for-bit
sentinel for the inverse-vol target_weights / ending_value / parameter_hash.

Safety regression: AST-walk the new B016 strategy modules
(``risk_parity_hrp.py`` and ``risk_parity_hrp_comparison.py``) plus the CLI
script, asserting:

- No ``scipy`` / ``numpy`` / ``pandas`` / ``sklearn`` / ``networkx`` imports.
- No broker / AI / public-import imports.
- No ``os.environ`` / ``os.getenv`` reads.
- Default fixture-driven runs perform no socket I/O.
- B016 outputs contain no paper / live execution phrasing.
"""

from __future__ import annotations

import ast
import json
import socket
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import DataSnapshot, PriceBar
from trade.strategies.risk_parity import RiskParityParameters

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NEW_B016_MODULE_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp.py",
    PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp_comparison.py",
    PROJECT_ROOT / "scripts" / "generate_b016_hrp_comparison_report.py",
)

# Forbidden import sets for B016 modules.
FORBIDDEN_NUMERICAL_LIBRARIES: frozenset[str] = frozenset(
    {
        "networkx",
        "numpy",
        "pandas",
        "scikit_learn",
        "scikit-learn",
        "scipy",
        "sklearn",
    }
)

FORBIDDEN_BROKER_AI_PUBLIC_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "alpaca",
        "anthropic",
        "ibapi",
        "openai",
        "polygon",
        "trade.ai",
        "trade.brokers",
        "trade.data.public_import",
    }
)

FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES: frozenset[str] = frozenset(
    {
        "boto3",
        "google.cloud",
        "http.client",
        "requests",
        "urllib.request",
        "websocket",
        "yfinance",
    }
)


# --------------------------------------------------------------------------- #
# Backwards-compat snapshot for the inverse-vol path
# --------------------------------------------------------------------------- #


def _three_asset_fixture() -> tuple[PriceBar, ...]:
    """Deterministic 3-asset fixture with reproducible price history."""

    def history(symbol: str, pattern: tuple[float, ...]) -> tuple[PriceBar, ...]:
        start = date(2024, 1, 1)
        price = 100.0
        records: list[PriceBar] = []
        for index in range(90):
            if index:
                price *= 1.0 + pattern[index % len(pattern)]
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

    return (
        history("SPY", (0.012, -0.010, 0.008, -0.006))
        + history("AGG", (0.003, -0.002, 0.001, -0.0005))
        + history("SGOV", (0.0001, 0.0001, 0.0001, 0.0001))
    )


def _inverse_vol_parameters() -> RiskParityParameters:
    return RiskParityParameters(
        universe=("SPY", "AGG", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.08,
        max_asset_weight=1.0,
    )


# Reference values captured once from the unchanged B010 inverse-vol path on
# the deterministic fixture above. If any future change perturbs the math,
# these values diverge and the test fails — an explicit bit-for-bit sentinel.
_EXPECTED_PARAMETER_HASH = (
    "e88eb38fafb1c486f99df9dd48a5493749449afd54ad670defc8dcfef5214d0f"
)
_EXPECTED_WEIGHTS = {
    "AGG": 0.832887495,
    "SPY": 0.167112505,
    "SGOV": 0.0,
}
_EXPECTED_EXPOSURE_SCALE = 1.0
_EXPECTED_DEFENSIVE_WEIGHT = 0.0
_EXPECTED_ENDING_VALUE = 99694.29055771964
_EXPECTED_TURNOVER = 1.0
_EXPECTED_COST_AMOUNT = 29.999999999999996


def test_inverse_vol_parameter_hash_is_bit_for_bit_b010() -> None:
    params = _inverse_vol_parameters()

    assert params.parameter_hash() == _EXPECTED_PARAMETER_HASH


def test_inverse_vol_target_weights_are_bit_for_bit_b010() -> None:
    records = _three_asset_fixture()
    params = _inverse_vol_parameters()

    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        params,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    period0 = result.rebalance_results[0]
    for symbol, expected in _EXPECTED_WEIGHTS.items():
        actual = period0.signal.target_weights.get(symbol, 0.0)
        assert round(actual, 9) == round(expected, 9), (
            f"weight regression for {symbol}: got {actual}, expected {expected}"
        )
    assert period0.signal.exposure_scale == _EXPECTED_EXPOSURE_SCALE
    assert period0.signal.defensive_weight == _EXPECTED_DEFENSIVE_WEIGHT


def test_inverse_vol_backtest_outputs_are_bit_for_bit_b010() -> None:
    records = _three_asset_fixture()
    params = _inverse_vol_parameters()

    result = run_risk_parity_monthly_backtest(
        records,
        (date(2024, 3, 10), date(2024, 3, 20)),
        params,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    assert result.starting_capital == 100_000.0
    assert round(result.ending_value, 8) == round(_EXPECTED_ENDING_VALUE, 8)
    assert round(result.turnover, 8) == round(_EXPECTED_TURNOVER, 8)
    assert round(result.cost_amount, 8) == round(_EXPECTED_COST_AMOUNT, 8)


def test_default_construction_equals_explicit_inverse_volatility() -> None:
    """Switching from implicit default to explicit ``weighting_method='inverse_volatility'``
    must produce identical RiskParityParameters in every respect."""

    implicit = RiskParityParameters()
    explicit = RiskParityParameters(weighting_method="inverse_volatility")

    assert implicit == explicit
    assert implicit.parameter_hash() == explicit.parameter_hash()


# --------------------------------------------------------------------------- #
# Import-AST safety guards on new B016 modules
# --------------------------------------------------------------------------- #


def _collect_imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("module_path", NEW_B016_MODULE_PATHS, ids=lambda p: p.name)
def test_b016_module_has_no_third_party_numerical_imports(module_path: Path) -> None:
    """No scipy / numpy / pandas / sklearn / networkx in B016 modules."""

    imports = _collect_imported_modules(module_path)
    forbidden = imports & FORBIDDEN_NUMERICAL_LIBRARIES
    assert not forbidden, (
        f"{module_path.name} imports forbidden numerical libraries: {forbidden}"
    )


@pytest.mark.parametrize("module_path", NEW_B016_MODULE_PATHS, ids=lambda p: p.name)
def test_b016_module_has_no_broker_ai_or_public_import_imports(module_path: Path) -> None:
    """No broker / AI / LLM SDK / trade.brokers / trade.ai / trade.data.public_import."""

    imports = _collect_imported_modules(module_path)
    forbidden = imports & FORBIDDEN_BROKER_AI_PUBLIC_IMPORT_MODULES
    assert not forbidden, (
        f"{module_path.name} imports forbidden broker/AI modules: {forbidden}"
    )


@pytest.mark.parametrize(
    "module_path",
    (
        PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp.py",
        PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp_comparison.py",
    ),
    ids=lambda p: p.name,
)
def test_b016_strategy_module_has_no_network_or_credential_imports(
    module_path: Path,
) -> None:
    """trade/strategies/ HRP modules must not import network / credential clients."""

    imports = _collect_imported_modules(module_path)
    forbidden = imports & FORBIDDEN_NETWORK_OR_CREDENTIAL_MODULES
    assert not forbidden, (
        f"{module_path.name} imports forbidden network/credential modules: {forbidden}"
    )


# --------------------------------------------------------------------------- #
# Source-level guards on new B016 strategy modules
# --------------------------------------------------------------------------- #


_STRATEGY_HRP_MODULES: tuple[Path, ...] = (
    PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp.py",
    PROJECT_ROOT / "trade" / "strategies" / "risk_parity_hrp_comparison.py",
)


@pytest.mark.parametrize("module_path", _STRATEGY_HRP_MODULES, ids=lambda p: p.name)
def test_b016_strategy_module_has_no_env_reads(module_path: Path) -> None:
    """No os.environ or os.getenv reads in B016 strategy modules."""

    source = module_path.read_text(encoding="utf-8")
    assert "os.environ" not in source, (
        f"{module_path.name} reads os.environ"
    )
    assert "os.getenv" not in source, (
        f"{module_path.name} reads os.getenv"
    )
    assert "getenv(" not in source, (
        f"{module_path.name} calls getenv(...)"
    )


# --------------------------------------------------------------------------- #
# Runtime safety: fixture run performs no socket I/O
# --------------------------------------------------------------------------- #


def test_hrp_workflow_completes_without_socket_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default HRP fixture run must not touch the network."""

    real_socket = socket.socket

    def _refuse(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - guard
        raise AssertionError(
            f"HRP workflow attempted socket I/O: args={args!r} kwargs={kwargs!r}"
        )

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    try:
        records = _three_asset_fixture()
        params = RiskParityParameters(
            universe=("SPY", "AGG", "SGOV"),
            volatility_lookback=60,
            defensive_asset="SGOV",
            target_volatility=0.08,
            max_asset_weight=1.0,
            weighting_method="hrp",
        )
        result = run_risk_parity_monthly_backtest(
            records,
            (date(2024, 3, 10),),
            params,
            BacktestParameters(starting_capital=100_000.0),
        )
        assert result.ending_value > 0
        assert result.parameters.weighting_method == "hrp"
    finally:
        monkeypatch.setattr(socket, "socket", real_socket)


# --------------------------------------------------------------------------- #
# B016 output / report phrasing guards
# --------------------------------------------------------------------------- #


_FORBIDDEN_OUTPUT_PHRASES: tuple[str, ...] = (
    "paper-execution",
    "paper execution",
    "live execution",
    "live-execution",
    "executed-order",
    "executed order",
    "place_order",
    "submit_order",
)


def test_canonical_b016_report_outputs_have_no_paper_or_live_execution_phrasing() -> None:
    """The committed canonical artifacts must be free of execution phrasing."""

    artifact_dir = PROJECT_ROOT / "docs" / "test-reports"
    files = sorted(artifact_dir.glob("B016-risk-parity-hrp-comparison-*"))
    assert files, "Canonical B016 comparison artifacts are missing from docs/test-reports/"
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in _FORBIDDEN_OUTPUT_PHRASES:
            assert phrase not in text, (
                f"{path.name} contains forbidden execution phrasing: {phrase!r}"
            )


def test_freshly_generated_report_has_no_paper_or_live_execution_phrasing(
    tmp_path: Path,
) -> None:
    """A freshly generated B016 report (skipped or ran branch) must be clean."""

    from trade.strategies.risk_parity_hrp_comparison import (
        generate_hrp_comparison_report,
        try_run_real_snapshot_hrp_comparison,
    )

    comparison = try_run_real_snapshot_hrp_comparison(
        tmp_path / "missing-manifest.json",
        _inverse_vol_parameters(),
    )
    artifacts = generate_hrp_comparison_report(
        comparison,
        baseline_60_40={},
        output_dir=tmp_path,
        run_id="B016-rp-hrp-safety-check",
        report_date=date(2026, 5, 14),
    )
    md = artifacts.markdown_path.read_text(encoding="utf-8").lower()
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    json_str = json.dumps(payload).lower()
    for phrase in _FORBIDDEN_OUTPUT_PHRASES:
        assert phrase not in md, f"markdown contains forbidden phrase: {phrase!r}"
        assert phrase not in json_str, f"json contains forbidden phrase: {phrase!r}"


# --------------------------------------------------------------------------- #
# Optional: snapshot DataSnapshot helper for report generation (no network)
# --------------------------------------------------------------------------- #


def test_three_asset_fixture_runs_without_data_snapshot_dependency() -> None:
    """Sanity: the snapshot test fixture itself doesn't depend on snapshot manifests."""

    records = _three_asset_fixture()
    dates = tuple(sorted({record.date for record in records}))
    snapshot = DataSnapshot(
        records=records,
        source="b016-safety-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:b016-safety",
        checksum="d" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=("AGG", "SGOV", "SPY"),
        trading_calendar_gaps=(),
    )

    assert snapshot.start_date == dates[0]
    assert snapshot.end_date == dates[-1]
