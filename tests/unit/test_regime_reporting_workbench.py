"""B057 F002 — trade.reporting.regime_adaptive (the workbench backtest report).

The workbench backtest worker renders the regime mode through this module: a
lean payload (the research payload without the fixed historical stress windows,
since an arbitrary user-selected backtest range rarely overlaps them) plus a
Simplified-Chinese summary markdown (B054). These tests build a real regime
backtest result from synthetic records and pin both the payload metrics shape
``workbench_api.backtests.mapping.map_metrics`` reads, and the Chinese render.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from trade.data.loader import DataSnapshot, PriceBar
from trade.reporting.regime_adaptive import (
    build_regime_adaptive_report_payload,
    render_regime_adaptive_markdown,
)
from trade.strategies.regime_adaptive.backtest import run_regime_adaptive_monthly_backtest
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)


def _rising(length: int, start: float, step: float) -> list[float]:
    return [start + step * index for index in range(length)]


def _bars(symbol: str, prices: list[float]) -> list[PriceBar]:
    start = date(2024, 1, 1)
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


def _build_records(length: int = 120) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, _rising(length, 100.0, 0.0)))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, 100.0, 0.1 + 0.02 * index)))
    return tuple(rows)


def _make_snapshot(records: tuple[PriceBar, ...]) -> DataSnapshot:
    dates = tuple(sorted({record.date for record in records}))
    symbols = tuple(sorted({record.symbol for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-regime-workbench-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:regime-workbench",
        checksum="w" * 64,
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


def _result() -> tuple[DataSnapshot, object]:
    records = _build_records(120)
    snapshot = _make_snapshot(records)
    result = run_regime_adaptive_monthly_backtest(
        records, (date(2024, 3, 20), date(2024, 4, 19)), _short_config()
    )
    return snapshot, result


def test_workbench_payload_has_metrics_block_for_map_metrics() -> None:
    snapshot, result = _result()
    payload = build_regime_adaptive_report_payload(result, snapshot, "wb-1")
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    # The exact keys workbench_api.backtests.mapping.map_metrics reads.
    assert {"CAGR", "Sharpe", "max_drawdown", "turnover"} <= set(metrics)


def test_workbench_payload_drops_fixed_stress_windows() -> None:
    # The workbench builder passes stress_windows=() (an arbitrary backtest
    # range rarely overlaps the doctrinal 2020/2022 windows) — so the section is
    # present but empty rather than carrying skipped placeholders for fixed dates.
    snapshot, result = _result()
    payload = build_regime_adaptive_report_payload(result, snapshot, "wb-2")
    assert payload["stress_validation"] == {}


def test_workbench_markdown_is_chinese_and_research_state() -> None:
    snapshot, result = _result()
    payload = build_regime_adaptive_report_payload(result, snapshot, "wb-3")
    md = render_regime_adaptive_markdown(payload)
    assert "智能择时组合回测报告 wb-3" in md
    assert "夏普比率" in md  # Chinese metric labels
    assert "研究态" in md  # honest research-state marker (not a return forecast)
