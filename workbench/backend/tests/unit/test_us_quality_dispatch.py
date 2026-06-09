"""B050 F002 — us_quality dispatch: DataFrame adapter + report builder.

The us_quality engine is the odd one out: it loads its own data, returns a daily
``pd.DataFrame`` equity curve, and reports no per-leg fills. These tests pin the
two new pieces:

1. ``adapt_us_quality`` converts the DataFrame curve → EquitySample rows, maps
   ``rebalance_periods`` → allocations, and surfaces **empty** trades (honest —
   no fabricated legs).
2. ``build_us_quality_report_payload`` emits a ``metrics`` block ``map_metrics``
   reads (CAGR / Sharpe / max_drawdown / turnover), so the result card renders.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd  # type: ignore[import-untyped]

from workbench_api.backtests import worker as worker_mod
from workbench_api.backtests.adapters import adapt_us_quality
from workbench_api.backtests.mapping import map_metrics


def _fake_result() -> SimpleNamespace:
    curve = pd.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            "equity": [100_000.0, 101_000.0, 102_500.0],
        }
    )
    daily_returns = pd.Series([float("nan"), 0.01, 0.014851])
    period = SimpleNamespace(
        signal_date=date(2024, 1, 2),
        execution_date=date(2024, 1, 3),
        valuation_date=date(2024, 1, 4),
        target_weights={"AAPL": 0.6, "MSFT": 0.4},
        starting_value=100_000.0,
        ending_value=102_500.0,
        cost_amount=12.5,
        turnover=0.5,
        cash_buffer=0.0,
        sector_exposure={"tech": 1.0},
    )
    return SimpleNamespace(
        parameters=SimpleNamespace(
            strategy_id="us_quality_momentum",
            top_n=15,
            rebalance_frequency="monthly",
            max_position_weight=0.07,
            max_sector_weight=0.30,
            earnings_window_days=5,
        ),
        config=SimpleNamespace(cost_bps=5.0, slippage_bps=5.0),
        starting_capital=100_000.0,
        ending_value=102_500.0,
        equity_curve=curve,
        rebalance_periods=(period,),
        daily_returns=daily_returns,
    )


def _minimal_snapshot() -> object:
    from trade.data.loader import DataSnapshot  # type: ignore[import-untyped]

    return DataSnapshot(
        records=(),
        source="test",
        adjusted_price_policy="adjusted_close",
        data_snapshot_id="t-snap",
        checksum="deadbeef",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        symbols=(),
        trading_calendar_gaps=(),
    )


def test_adapt_us_quality_converts_dataframe_and_empty_trades() -> None:
    mapped = adapt_us_quality(_fake_result())
    assert mapped["equity"] == [
        {"date": "2024-01-02", "nav": 100_000.0},
        {"date": "2024-01-03", "nav": 101_000.0},
        {"date": "2024-01-04", "nav": 102_500.0},
    ]
    assert mapped["allocations"] == [
        {"date": "2024-01-02", "weights": {"AAPL": 0.6, "MSFT": 0.4}}
    ]
    # Honest absence — the engine reports no fills; we never fabricate trades.
    assert mapped["trades"] == []


def test_us_quality_report_payload_metrics_are_readable() -> None:
    from trade.reporting.us_quality_momentum import (  # type: ignore[import-untyped]
        build_us_quality_report_payload,
        render_us_quality_markdown,
    )

    payload = build_us_quality_report_payload(_fake_result(), _minimal_snapshot(), "run-1")
    metrics = map_metrics(payload)
    # All four headline metrics present + numeric (non-placeholder).
    assert isinstance(metrics["cagr"], float)
    assert isinstance(metrics["sharpe"], float)
    assert isinstance(metrics["max_drawdown"], float)
    assert metrics["turnover"] == 0.5  # the single period's turnover
    # Markdown renders without raising and names the strategy.
    md = render_us_quality_markdown(payload)
    assert "US Quality Momentum Report run-1" in md


def test_dispatch_table_wires_us_quality() -> None:
    assert worker_mod._DISPATCH["B025-us-quality-momentum"] is worker_mod._run_us_quality


def test_dispatch_table_wires_hk_china() -> None:
    # B050 F003: the standalone HK-China engine is wired; its result is
    # risk_parity-isomorphic so it reuses adapt_risk_parity.
    assert worker_mod._DISPATCH["B011-satellite-hk-china"] is worker_mod._run_hk_china
