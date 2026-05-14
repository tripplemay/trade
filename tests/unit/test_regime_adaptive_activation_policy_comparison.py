"""F003 — three-policy comparative backtest harness for B015.

Exercises the core comparator on synthetic fixtures plus the real-snapshot wrapper's
skip semantics when the B014 manifest is absent. Default CI never reaches a real
snapshot — that path is covered by tests that supply a temporary manifest + CSV
bundle so the loader can run hermetically without network I/O.
"""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.activation_policy_comparison import (
    COMPARISON_STATUS_RAN,
    COMPARISON_STATUS_SKIPPED,
    ActivationPolicyComparisonResult,
    PolicyComparisonRow,
    build_monthly_signal_dates,
    load_regime_adaptive_snapshot_records,
    run_activation_policy_comparison,
    try_run_real_snapshot_activation_policy_comparison,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    POLICY_ALWAYS_ON,
    POLICY_ONLY_CRISIS,
    POLICY_ONLY_NON_NORMAL,
    default_regime_adaptive_config,
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


def _short_config():
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def _build_records(length: int = 120) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, [100.0] * length))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.1 + 0.02 * index)))
    return tuple(rows)


def test_run_activation_policy_comparison_returns_three_rows_one_per_policy() -> None:
    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_activation_policy_comparison(records, signal_dates, config)

    assert isinstance(result, ActivationPolicyComparisonResult)
    assert tuple(row.policy for row in result.policy_rows) == (
        POLICY_ALWAYS_ON,
        POLICY_ONLY_NON_NORMAL,
        POLICY_ONLY_CRISIS,
    )
    for row in result.policy_rows:
        assert isinstance(row, PolicyComparisonRow)
        assert row.rebalance_count == len(signal_dates)


def test_run_activation_policy_comparison_l1_firing_rates_match_policy_semantics() -> None:
    """In a NORMAL-only rising fixture, only always_on fires L1; the other two skip it."""

    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_activation_policy_comparison(records, signal_dates, config)
    rates = {row.policy: row.l1_firing_rate for row in result.policy_rows}

    assert rates[POLICY_ALWAYS_ON] == pytest.approx(1.0)
    assert rates[POLICY_ONLY_NON_NORMAL] == pytest.approx(0.0)
    assert rates[POLICY_ONLY_CRISIS] == pytest.approx(0.0)


def test_run_activation_policy_comparison_is_deterministic() -> None:
    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    first = run_activation_policy_comparison(records, signal_dates, config)
    second = run_activation_policy_comparison(records, signal_dates, config)

    for row_a, row_b in zip(first.policy_rows, second.policy_rows, strict=True):
        assert row_a.annualized_return == row_b.annualized_return
        assert row_a.annualized_volatility == row_b.annualized_volatility
        assert row_a.max_drawdown == row_b.max_drawdown
        assert row_a.turnover == row_b.turnover
        assert row_a.ending_value == row_b.ending_value


def test_run_activation_policy_comparison_regime_distribution_sums_to_period_count() -> None:
    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_activation_policy_comparison(records, signal_dates, config)

    for row in result.policy_rows:
        assert sum(row.regime_distribution.values()) == row.rebalance_count


def test_run_activation_policy_comparison_records_stress_window_drawdowns() -> None:
    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))
    stress_windows = (
        (date(2024, 3, 1), date(2024, 5, 1), "synthetic_window"),
    )

    result = run_activation_policy_comparison(
        records,
        signal_dates,
        config,
        stress_windows=stress_windows,
    )

    for row in result.policy_rows:
        assert "synthetic_window" in row.stress_window_max_drawdowns
        assert "synthetic_window" in row.stress_window_status
        assert row.stress_window_status["synthetic_window"] in {"pass", "fail", "skipped"}


def test_run_activation_policy_comparison_default_snapshot_status_is_ran() -> None:
    config = _short_config()
    records = _build_records(length=120)
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_activation_policy_comparison(records, signal_dates, config)

    assert result.snapshot_status == COMPARISON_STATUS_RAN


def test_try_run_real_snapshot_comparison_returns_skipped_when_manifest_missing(
    tmp_path: Path,
) -> None:
    missing_manifest = tmp_path / "regime-adaptive-prices-manifest.json"

    result = try_run_real_snapshot_activation_policy_comparison(
        missing_manifest,
        _short_config(),
    )

    assert result.snapshot_status == COMPARISON_STATUS_SKIPPED
    assert result.policy_rows == ()
    assert result.snapshot_reason is not None
    assert "manifest" in result.snapshot_reason.lower()


def test_build_monthly_signal_dates_returns_last_trading_day_per_month() -> None:
    trading_dates = (
        date(2024, 1, 5),
        date(2024, 1, 19),
        date(2024, 1, 31),
        date(2024, 2, 5),
        date(2024, 2, 28),
        date(2024, 3, 1),
        date(2024, 3, 29),
    )

    signal_dates = build_monthly_signal_dates(trading_dates, date(2024, 1, 1), date(2024, 3, 31))

    assert signal_dates == (date(2024, 1, 31), date(2024, 2, 28), date(2024, 3, 29))


def _write_csv(path: Path, rows: list[tuple[date, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("date", "open", "high", "low", "close", "adjusted_close", "volume"))
        for trading_date, price in rows:
            writer.writerow(
                (
                    trading_date.isoformat(),
                    f"{price:.6f}",
                    f"{price:.6f}",
                    f"{price:.6f}",
                    f"{price:.6f}",
                    f"{price:.6f}",
                    "1000",
                )
            )


def _write_fake_snapshot(tmp_path: Path) -> Path:
    """Write a B014-shaped manifest + per-ticker CSVs into ``tmp_path``."""

    config = default_regime_adaptive_config()
    output_dir = tmp_path
    files_manifest = []
    start = date(2022, 1, 1)
    end = date(2024, 7, 31)
    rows: list[tuple[date, float]] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            rows.append((current, 100.0 + (current - start).days * 0.1))
        current += timedelta(days=1)
    for index, entry in enumerate(config.universe):
        csv_path = output_dir / f"regime-adaptive-{entry.symbol}.csv"
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            ticker_rows = [(d, 100.0) for d, _ in rows]
        else:
            base = 100.0 + index * 0.5
            # add a small alternating perturbation so daily returns have non-zero variance
            ticker_rows = []
            for d, _ in rows:
                day_index = (d - start).days
                wiggle = 0.5 if day_index % 3 == 0 else (-0.3 if day_index % 3 == 1 else 0.1)
                price = base + day_index * (0.1 + 0.02 * index) + wiggle
                ticker_rows.append((d, price))
        _write_csv(csv_path, ticker_rows)
        files_manifest.append({
            "ticker": entry.symbol,
            "path": csv_path.as_posix(),
            "sha256": "test-stub",
            "row_count": len(ticker_rows),
            "start": rows[0][0].isoformat(),
            "end": rows[-1][0].isoformat(),
            "short_history_exempt": False,
        })
    manifest_path = output_dir / "regime-adaptive-prices-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "snapshot_id": "regime-adaptive:fake-test-stub",
                "source": "regime-adaptive-public-import",
                "tickers": [entry.symbol for entry in config.universe],
                "date_range": {"start": rows[0][0].isoformat(), "end": rows[-1][0].isoformat()},
                "files": files_manifest,
                "created_at": "2026-05-14T00:00:00+00:00",
                "limitations": {"disclaimer": "research-only", "data_label": "test", "extra": []},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_load_regime_adaptive_snapshot_records_reads_manifest_and_csvs(
    tmp_path: Path,
) -> None:
    manifest_path = _write_fake_snapshot(tmp_path)

    loaded = load_regime_adaptive_snapshot_records(manifest_path)

    assert loaded.snapshot_id == "regime-adaptive:fake-test-stub"
    symbols = {record.symbol for record in loaded.records}
    config = default_regime_adaptive_config()
    assert symbols == {entry.symbol for entry in config.universe}
    assert loaded.date_range[0] == date(2022, 1, 3)
    assert loaded.date_range[1] >= date(2024, 6, 1)


def test_try_run_real_snapshot_comparison_runs_three_policies_when_manifest_present(
    tmp_path: Path,
) -> None:
    manifest_path = _write_fake_snapshot(tmp_path)
    config = _short_config()

    result = try_run_real_snapshot_activation_policy_comparison(
        manifest_path,
        config,
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        window_start=date(2022, 7, 1),
        window_end=date(2024, 6, 30),
    )

    assert result.snapshot_status == COMPARISON_STATUS_RAN
    assert tuple(row.policy for row in result.policy_rows) == (
        POLICY_ALWAYS_ON,
        POLICY_ONLY_NON_NORMAL,
        POLICY_ONLY_CRISIS,
    )
    assert result.snapshot_manifest_id == "regime-adaptive:fake-test-stub"
