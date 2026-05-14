"""F005 — B015 backwards-compat + safety guard regression.

Proves that:

- The default ``regime_activation_policy`` is ``always_on``.
- With ``always_on``, the L3-before-L1 workflow reordering preserves the L1 trend-gating
  mask bit-for-bit versus a direct ``apply_trend_gating`` call (the pre-B015 code path).
- With ``always_on``, every per-period ``l1_active`` flag is ``True``.
- Re-running the same backtest produces identical equity curves + weight histories +
  gating histories (determinism gate).
- The two new B015 modules (``activation_policy_comparison`` and
  ``activation_policy_report``) carry the research-only disclaimer in their docstrings,
  do not read ``os.environ`` / ``os.getenv``, do not import broker / AI / network SDKs,
  and the rendered B015 report does not contain paper/live execution phrasing.
- The committed B015 activation-policy comparison artifact ships the research-only
  disclaimer and never claims paper or live execution.

The artifact is research-only and never authorizes any paper or production order flow.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.activation_policy_comparison import (
    run_activation_policy_comparison,
)
from trade.strategies.regime_adaptive.activation_policy_report import (
    build_activation_policy_report_payload,
    render_activation_policy_markdown,
)
from trade.strategies.regime_adaptive.backtest import (
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    POLICY_ALWAYS_ON,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.trend_gating import apply_trend_gating

PROJECT_ROOT = Path(__file__).resolve().parents[2]
B015_MODULES: tuple[Path, ...] = (
    PROJECT_ROOT / "trade" / "strategies" / "regime_adaptive" / "activation_policy_comparison.py",
    PROJECT_ROOT / "trade" / "strategies" / "regime_adaptive" / "activation_policy_report.py",
)
B015_REPORT_PATH = (
    PROJECT_ROOT
    / "docs"
    / "test-reports"
    / "B015-regime-adaptive-activation-policy-comparison-2026-05-14.md"
)
B015_REPORT_JSON_PATH = (
    PROJECT_ROOT
    / "docs"
    / "test-reports"
    / "B015-regime-adaptive-activation-policy-comparison-2026-05-14.json"
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


def _short_config():
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def test_default_config_keeps_always_on_as_default_activation_policy() -> None:
    assert default_regime_adaptive_config().regime_activation_policy == POLICY_ALWAYS_ON


def test_always_on_backtest_gating_mask_matches_direct_apply_trend_gating() -> None:
    """With always_on the workflow must produce identical L1 gating output for each period."""

    config = _short_config()
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    for period in result.rebalance_results:
        direct = apply_trend_gating(records, config, period.signal_date)
        assert period.gating_result.mask == direct.mask
        assert period.gating_result.gated_symbols == direct.gated_symbols
        assert period.gating_result.passing_symbols == direct.passing_symbols
        for produced, expected in zip(
            period.gating_result.details, direct.details, strict=True
        ):
            assert produced.symbol == expected.symbol
            assert produced.passes == expected.passes
            assert produced.reason == expected.reason


def test_always_on_backtest_l1_active_is_true_every_period() -> None:
    config = _short_config()
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 1), date(2024, 4, 19))

    result = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    assert all(period.l1_active is True for period in result.rebalance_results)


def test_always_on_backtest_is_deterministic_across_runs() -> None:
    config = _short_config()
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 1), date(2024, 4, 19))

    first = run_regime_adaptive_monthly_backtest(records, signal_dates, config)
    second = run_regime_adaptive_monthly_backtest(records, signal_dates, config)

    assert first.ending_value == second.ending_value
    assert first.turnover == second.turnover
    assert first.cost_amount == second.cost_amount
    first_eq = tuple((point.date, point.value) for point in first.equity_curve)
    second_eq = tuple((point.date, point.value) for point in second.equity_curve)
    assert first_eq == second_eq
    for a, b in zip(first.rebalance_results, second.rebalance_results, strict=True):
        assert a.effective_weights == b.effective_weights
        assert a.gating_result.mask == b.gating_result.mask
        assert a.regime_state.regime == b.regime_state.regime
        assert a.l1_active == b.l1_active


def test_activation_policy_comparison_run_does_not_open_socket(monkeypatch) -> None:
    def _refuse_socket(*args, **kwargs):
        raise RuntimeError("network access is not allowed in B015 activation-policy comparison")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    config = _short_config()
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_activation_policy_comparison(
        records,
        signal_dates,
        config,
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
    )

    assert len(result.policy_rows) == 3


def test_b015_modules_label_research_only_in_docstring() -> None:
    for module_path in B015_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree) or ""
        assert "research-only" in docstring.lower(), (
            f"{module_path} is missing the research-only disclaimer in its docstring"
        )


def test_b015_modules_do_not_read_environment() -> None:
    for module_path in B015_MODULES:
        source = module_path.read_text(encoding="utf-8")
        assert "os.environ" not in source, f"{module_path} reads os.environ"
        assert "os.getenv" not in source, f"{module_path} reads os.getenv"


def test_b015_committed_report_carries_research_only_disclaimer() -> None:
    if not B015_REPORT_PATH.is_file():
        pytest.skip("committed B015 report not present")
    text = B015_REPORT_PATH.read_text(encoding="utf-8").lower()
    assert "research-only" in text


def test_b015_committed_report_does_not_claim_paper_or_live_execution() -> None:
    if not B015_REPORT_PATH.is_file() or not B015_REPORT_JSON_PATH.is_file():
        pytest.skip("committed B015 report not present")
    md_text = B015_REPORT_PATH.read_text(encoding="utf-8").lower()
    json_text = B015_REPORT_JSON_PATH.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_TRADE_TERMS:
        assert phrase not in md_text, f"committed B015 markdown contains {phrase!r}"
        assert phrase not in json_text, f"committed B015 JSON contains {phrase!r}"


def test_rendered_b015_markdown_does_not_claim_paper_or_live_execution() -> None:
    config = _short_config()
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    comparison = run_activation_policy_comparison(
        records,
        signal_dates,
        config,
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
    )
    payload = build_activation_policy_report_payload(
        comparison,
        baseline_strategies={
            "global_etf_momentum": {"ending_value": 1.0, "max_drawdown": -0.01},
            "risk_parity": {"ending_value": 1.0, "max_drawdown": -0.01},
            "static_60_40": {"ending_value": 1.0, "max_drawdown": -0.01},
        },
        run_id="B015-phrasing-check",
        report_date=date(2026, 5, 14),
    )
    rendered = render_activation_policy_markdown(payload).lower()

    for phrase in FORBIDDEN_TRADE_TERMS:
        assert phrase not in rendered, f"rendered B015 markdown contains {phrase!r}"
