#!/usr/bin/env python3
"""Generate the B015 activation-policy comparison report (research-only).

Tries to load the B014 yfinance manifest at
``data/public-cache/regime-adaptive-prices-manifest.json``. When present, runs the
three-policy comparative backtest over the snapshot's overlapping window. When absent,
falls back to a synthetic 9-asset fixture so the report can still be produced as a
schema example; in that case the report's ``real_data_status.status`` is ``skipped`` and
the narrative explicitly notes that real-data findings require the manifest. Reuses the
B014 cross-strategy comparison sidecar for the B006 / B010 / 60-40 baseline rows.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.activation_policy_comparison import (
    COMPARISON_STATUS_RAN,
    COMPARISON_STATUS_SKIPPED,
    ActivationPolicyComparisonResult,
    build_monthly_signal_dates,
    run_activation_policy_comparison,
    try_run_real_snapshot_activation_policy_comparison,
)
from trade.strategies.regime_adaptive.activation_policy_report import (
    DEFAULT_B014_COMPARISON_PATH,
    generate_activation_policy_report,
    load_b014_comparison_baselines,
)
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    RegimeAdaptiveConfig,
    default_regime_adaptive_config,
)

DEFAULT_MANIFEST_PATH = Path("data/public-cache/regime-adaptive-prices-manifest.json")
DEFAULT_OUTPUT_DIR = Path("docs/test-reports")
SYNTHETIC_START = date(2022, 1, 1)
SYNTHETIC_END = date(2024, 7, 31)


def _build_synthetic_records(config: RegimeAdaptiveConfig) -> tuple[PriceBar, ...]:
    records: list[PriceBar] = []
    current = SYNTHETIC_START
    weekdays: list[date] = []
    while current <= SYNTHETIC_END:
        if current.weekday() < 5:
            weekdays.append(current)
        current += timedelta(days=1)
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            for trading_date in weekdays:
                records.append(
                    PriceBar(
                        date=trading_date,
                        symbol=entry.symbol,
                        open=100.0,
                        close=100.0,
                        adjusted_close=100.0,
                        volume=1_000,
                    )
                )
            continue
        base = 100.0 + index * 0.5
        slope = 0.1 + 0.02 * index
        for trading_date in weekdays:
            day_index = (trading_date - SYNTHETIC_START).days
            wiggle = 0.5 if day_index % 3 == 0 else (-0.3 if day_index % 3 == 1 else 0.1)
            price = base + day_index * slope + wiggle
            records.append(
                PriceBar(
                    date=trading_date,
                    symbol=entry.symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1_000,
                )
            )
    return tuple(records)


def _run_synthetic_fallback(
    config: RegimeAdaptiveConfig,
    manifest_path: Path,
) -> ActivationPolicyComparisonResult:
    records = _build_synthetic_records(config)
    trading_dates = tuple(sorted({record.date for record in records}))
    signal_dates = build_monthly_signal_dates(
        trading_dates, date(2022, 7, 1), date(2024, 6, 30)
    )
    return run_activation_policy_comparison(
        records,
        signal_dates,
        config,
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        snapshot_status=COMPARISON_STATUS_SKIPPED,
        snapshot_reason=(
            f"B014 yfinance manifest not found at {manifest_path}; ran on a synthetic "
            "9-asset fixture as a smoke check only. Re-run after `scripts/"
            "fetch_yfinance_regime_adaptive_csvs.py` populates the manifest to obtain "
            "real-data findings."
        ),
        snapshot_manifest_id=None,
        snapshot_date_range=None,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the B014 yfinance snapshot manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the report markdown + JSON sidecar are written.",
    )
    parser.add_argument(
        "--b014-comparison-path",
        type=Path,
        default=DEFAULT_B014_COMPARISON_PATH,
        help="B014 cross-strategy comparison sidecar reused for baseline rows.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional explicit run id; defaults to a B015-comparison-<today> slug.",
    )
    parser.add_argument(
        "--report-date",
        type=lambda value: date.fromisoformat(value),
        default=None,
        help="Override the report_date (ISO YYYY-MM-DD); defaults to today.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = default_regime_adaptive_config()

    if args.manifest_path.is_file():
        comparison = try_run_real_snapshot_activation_policy_comparison(
            args.manifest_path,
            config,
            backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        )
        if comparison.snapshot_status != COMPARISON_STATUS_RAN:
            # The manifest existed but the harness still chose to skip (window empty etc.).
            comparison = _run_synthetic_fallback(config, args.manifest_path)
    else:
        comparison = _run_synthetic_fallback(config, args.manifest_path)

    baselines: dict[str, dict[str, object]]
    if args.b014_comparison_path.is_file():
        baselines = load_b014_comparison_baselines(args.b014_comparison_path)
    else:
        baselines = {"global_etf_momentum": {}, "risk_parity": {}, "static_60_40": {}}

    report_date = args.report_date or date.today()
    run_id = args.run_id or (
        f"B015-regime-adaptive-activation-policy-comparison-{report_date.isoformat()}"
    )
    artifacts = generate_activation_policy_report(
        comparison,
        baseline_strategies=baselines,
        output_dir=args.output_dir,
        run_id=run_id,
        report_date=report_date,
    )
    print(f"markdown : {artifacts.markdown_path}")
    print(f"json     : {artifacts.json_path}")
    print(f"status   : {comparison.snapshot_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
