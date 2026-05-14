#!/usr/bin/env python3
"""Generate the B016 risk-parity HRP comparison report (research-only).

Tries to load the B014 yfinance manifest at
``data/public-cache/regime-adaptive-prices-manifest.json``. When present,
runs the two-method comparative backtest (inverse_volatility vs hrp) on the
B013 9-asset universe over the snapshot's overlapping window. When absent,
falls back to a synthetic 9-asset fixture so the report can still be
produced as a schema example; in that case the report's
``real_data_status.status`` is ``skipped`` and the narrative explicitly
notes that real-data findings require the manifest. Reuses the B014
cross-strategy comparison sidecar for the static_60_40 baseline row.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.risk_parity import RiskParityParameters
from trade.strategies.risk_parity_hrp_comparison import (
    COMPARISON_STATUS_RAN,
    COMPARISON_STATUS_SKIPPED,
    HRPComparisonResult,
    build_monthly_signal_dates,
    generate_hrp_comparison_report,
    load_static_60_40_baseline,
    run_hrp_comparison,
    try_run_real_snapshot_hrp_comparison,
)

DEFAULT_MANIFEST_PATH = Path("data/public-cache/regime-adaptive-prices-manifest.json")
DEFAULT_B014_COMPARISON_PATH = Path(
    "docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/test-reports")
SYNTHETIC_START = date(2022, 1, 1)
SYNTHETIC_END = date(2024, 7, 31)

B013_NINE_ASSET_UNIVERSE: tuple[str, ...] = (
    "SPY",
    "VEA",
    "VWO",
    "AGG",
    "IEF",
    "GLD",
    "VNQ",
    "DBC",
    "SGOV",
)


def _default_strategy_template() -> RiskParityParameters:
    return RiskParityParameters(
        universe=B013_NINE_ASSET_UNIVERSE,
        volatility_lookback=120,
        defensive_asset="SGOV",
        target_volatility=0.08,
        max_asset_weight=0.35,
    )


def _build_synthetic_records(
    universe: tuple[str, ...],
) -> tuple[PriceBar, ...]:
    records: list[PriceBar] = []
    current = SYNTHETIC_START
    weekdays: list[date] = []
    while current <= SYNTHETIC_END:
        if current.weekday() < 5:
            weekdays.append(current)
        current += timedelta(days=1)
    for index, symbol in enumerate(universe):
        if symbol == "SGOV":
            for trading_date in weekdays:
                records.append(
                    PriceBar(
                        date=trading_date,
                        symbol=symbol,
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
            wiggle = (
                0.5 if day_index % 3 == 0
                else (-0.3 if day_index % 3 == 1 else 0.1)
            )
            price = base + day_index * slope + wiggle
            records.append(
                PriceBar(
                    date=trading_date,
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1_000,
                )
            )
    return tuple(records)


def _run_synthetic_fallback(
    template: RiskParityParameters,
    manifest_path: Path,
) -> HRPComparisonResult:
    records = _build_synthetic_records(tuple(template.universe))
    trading_dates = tuple(sorted({record.date for record in records}))
    signal_dates = build_monthly_signal_dates(
        trading_dates, date(2022, 7, 1), date(2024, 6, 30)
    )
    return run_hrp_comparison(
        records,
        signal_dates,
        template,
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        snapshot_status=COMPARISON_STATUS_SKIPPED,
        snapshot_reason=(
            f"B014 yfinance manifest not found at {manifest_path}; ran on a "
            "synthetic 9-asset fixture as a smoke check only. Re-run after "
            "`scripts/fetch_yfinance_regime_adaptive_csvs.py` populates the "
            "manifest to obtain real-data findings."
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
        help="B014 cross-strategy comparison sidecar for the static_60_40 baseline row.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional explicit run id; defaults to B016-risk-parity-hrp-comparison-<today>.",
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
    template = _default_strategy_template()

    if args.manifest_path.is_file():
        comparison = try_run_real_snapshot_hrp_comparison(
            args.manifest_path,
            template,
            backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        )
        if comparison.snapshot_status != COMPARISON_STATUS_RAN:
            comparison = _run_synthetic_fallback(template, args.manifest_path)
    else:
        comparison = _run_synthetic_fallback(template, args.manifest_path)

    baseline_60_40 = load_static_60_40_baseline(args.b014_comparison_path)

    report_date = args.report_date or date.today()
    run_id = args.run_id or (
        f"B016-risk-parity-hrp-comparison-{report_date.isoformat()}"
    )
    artifacts = generate_hrp_comparison_report(
        comparison,
        baseline_60_40=baseline_60_40,
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
