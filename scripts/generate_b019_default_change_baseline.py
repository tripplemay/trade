#!/usr/bin/env python3
"""B019 F004 — default-change baseline sidecar.

Re-run B010 + B013 on the three B019 windows (calm, stress 2020,
stress 2022) under the **new** defaults set by F003 (B013 quarterly /
target_volatility=0.11; B010 unchanged). Emits a JSON+MD sidecar at
``docs/test-reports/B019-default-change-baseline-<report-date>.{json,md}``
that future batches can use as the canonical reference baseline rather
than the historical B014 sidecar (which was captured under the prior
defaults and is not rewritten — see the spec).

When the B014 yfinance manifest at
``data/public-cache/regime-adaptive-prices-manifest.json`` is present,
the run uses the real snapshot. When absent, falls back to a synthetic
9-asset fixture (mirror of B018's fallback) so the sidecar can still be
produced as a schema example; in that case the JSON tags
``real_data_status.status='skipped'`` and the markdown explicitly notes
the fallback. Research-only — no live / paper / broker integration.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from trade.analysis.parameter_sweep import (
    STRATEGY_B010,
    STRATEGY_B013,
    SweepRunResult,
    SweepWindow,
    run_cadence_vs_default_sweep,
)
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.activation_policy_comparison import (
    load_regime_adaptive_snapshot_records,
)
from trade.strategies.regime_adaptive.config import RegimeAdaptiveConfig
from trade.strategies.risk_parity import RiskParityParameters

DEFAULT_MANIFEST_PATH = Path(
    "data/public-cache/regime-adaptive-prices-manifest.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/test-reports")
DISCLAIMER = (
    "Research-only sidecar; this run does not authorize paper or live trading."
)
SNAPSHOT_ID = "regime-adaptive:b69883b08eedea7d"

WINDOWS: tuple[SweepWindow, ...] = (
    SweepWindow(
        name="calm",
        start_date=date(2020, 6, 1),
        end_date=date(2022, 12, 31),
        benchmark_ending_value=158_978.38353347202,
    ),
    SweepWindow(
        name="stress_2020",
        start_date=date(2020, 2, 1),
        end_date=date(2020, 12, 31),
        benchmark_ending_value=None,
    ),
    SweepWindow(
        name="stress_2022",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        benchmark_ending_value=None,
    ),
)

_SYNTHETIC_UNIVERSE: tuple[str, ...] = (
    "SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC", "SGOV",
)


def _amplitude_for(symbol: str) -> float:
    return {
        "SPY": 0.018, "QQQ": 0.022, "VEA": 0.020, "VWO": 0.025,
        "IEF": 0.006, "TLT": 0.012, "GLD": 0.012, "DBC": 0.020,
        "SGOV": 0.0005,
    }[symbol]


def _phase_for(symbol: str) -> int:
    return {
        "SPY": 0, "QQQ": 0, "VEA": 0, "VWO": 0, "IEF": 1, "TLT": 1,
        "GLD": 0, "DBC": 1, "SGOV": 0,
    }[symbol]


def _synthetic_records(days: int = 1500) -> tuple[PriceBar, ...]:
    """Mirror of the B018 synthetic 9-asset fixture, extended to cover B019 windows."""

    start = date(2019, 1, 2)
    bars: list[PriceBar] = []
    for index, symbol in enumerate(_SYNTHETIC_UNIVERSE):
        price = 100.0 + index
        amp = _amplitude_for(symbol)
        phase = _phase_for(symbol)
        current = start
        observation = 0
        while observation < days:
            if current.weekday() < 5:
                if observation:
                    step = amp if (observation + phase) % 2 == 0 else -amp * 0.95
                    price *= 1.0 + step
                bars.append(
                    PriceBar(
                        date=current,
                        symbol=symbol,
                        open=price * 0.999,
                        close=price,
                        adjusted_close=price,
                        volume=1000,
                    )
                )
                observation += 1
            current += timedelta(days=1)
    return tuple(bars)


def _row_to_dict(row: SweepRunResult) -> dict[str, object]:
    return {
        "status": row.status,
        "ending_value": row.ending_value,
        "gap_vs_60_40": (
            row.gap_vs_60_40 if row.gap_vs_60_40 != 0.0 or row.status != "ran" else 0.0
        ),
        "max_drawdown": row.max_drawdown,
        "turnover": row.turnover,
        "transaction_costs": row.transaction_costs,
        "sharpe": row.sharpe,
        "rebalance_count": row.rebalance_count,
        "skipped_reason": row.skipped_reason,
        "cadence": row.cadence,
        "vol_target": row.vol_target,
    }


def _per_strategy_baseline(
    records: tuple[PriceBar, ...],
    strategy_name: str,
) -> dict[str, dict[str, object]]:
    """Run only the default-baseline cells (empty grid) for the strategy."""

    rows = run_cadence_vs_default_sweep(
        records,
        strategy_name,
        cadences=(),
        vol_targets=(),
        windows=WINDOWS,
        default_baseline=True,
    )
    by_window: dict[str, dict[str, object]] = {}
    for row in rows:
        by_window[row.window] = _row_to_dict(row)
    return by_window


def _build_payload(
    records: tuple[PriceBar, ...],
    *,
    real_data_status: dict[str, object],
    report_date: date,
    run_id: str,
) -> dict[str, object]:
    b010_default = RiskParityParameters()
    b013_default = RegimeAdaptiveConfig()
    return {
        "run": {
            "batch": "B019",
            "feature": "F004",
            "description": (
                "B010 + B013 default-change baseline (post-F003) on three "
                "B019 windows. Reference snapshot for future batches; "
                "supersedes the historical B014 cross-strategy sidecar "
                "for the post-F003 default values only."
            ),
            "report_date": report_date.isoformat(),
            "run_id": run_id,
        },
        "real_data_status": real_data_status,
        "defaults": {
            "b010": {
                "rebalance_frequency": b010_default.rebalance_frequency,
                "target_volatility": b010_default.target_volatility,
                "changed_in_b019": False,
            },
            "b013": {
                "cadence": "quarterly",
                "target_volatility": b013_default.target_volatility,
                "changed_in_b019": True,
                "previous_target_volatility": 0.08,
                "previous_cadence": "monthly",
            },
        },
        "matrix": {
            "b010": _per_strategy_baseline(records, STRATEGY_B010),
            "b013": _per_strategy_baseline(records, STRATEGY_B013),
        },
        "disclaimer": DISCLAIMER,
    }


def _format_window_block(label: str, by_window: dict[str, dict[str, object]]) -> list[str]:
    lines = [f"### {label}", ""]
    lines.append("| window | status | ending_value | max_drawdown | turnover | rebalance_count |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for name in ("calm", "stress_2020", "stress_2022"):
        cell = by_window.get(name, {})
        status = str(cell.get("status", "missing"))
        ending = cell.get("ending_value", 0.0)
        dd = cell.get("max_drawdown", 0.0)
        tov = cell.get("turnover", 0.0)
        rc = cell.get("rebalance_count", 0)
        ending_s = (
            f"{float(ending):,.2f}" if isinstance(ending, (int, float)) else str(ending)
        )
        dd_s = f"{float(dd):.4f}" if isinstance(dd, (int, float)) else str(dd)
        tov_s = f"{float(tov):.4f}" if isinstance(tov, (int, float)) else str(tov)
        lines.append(
            f"| {name} | {status} | {ending_s} | {dd_s} | {tov_s} | {rc} |"
        )
    lines.append("")
    return lines


def _render_markdown(payload: dict[str, object]) -> str:
    run = payload["run"]
    real = payload["real_data_status"]
    defaults = payload["defaults"]
    matrix = payload["matrix"]
    assert isinstance(run, dict)
    assert isinstance(real, dict)
    assert isinstance(defaults, dict)
    assert isinstance(matrix, dict)

    lines: list[str] = [
        f"# {run['run_id']}",
        "",
        f"_{DISCLAIMER}_",
        "",
        "## Run Metadata",
        "- Batch: B019",
        "- Feature: F004",
        f"- Report date: {run['report_date']}",
        f"- Description: {run['description']}",
        "",
        "## Real-Data Status",
        f"- Status: `{real['status']}`",
    ]
    if real.get("snapshot_id"):
        lines.append(f"- Snapshot: `{real['snapshot_id']}`")
    if real.get("manifest_path"):
        lines.append(f"- Manifest: `{real['manifest_path']}`")
    if real.get("date_range"):
        lines.append(f"- Date range: {real['date_range']}")
    if real.get("reason"):
        lines.append(f"- Reason: {real['reason']}")
    lines.append("")

    lines.extend([
        "## Default Configuration After F003",
        "",
        "| strategy | cadence | target_volatility | changed_in_b019 |",
        "|---|---|---:|:---:|",
    ])
    b010 = defaults["b010"]
    b013 = defaults["b013"]
    assert isinstance(b010, dict)
    assert isinstance(b013, dict)
    lines.append(
        f"| B010 | {b010['rebalance_frequency']} | "
        f"{float(b010['target_volatility']):.4f} | {b010['changed_in_b019']} |"  # type: ignore[arg-type]
    )
    lines.append(
        f"| B013 | {b013['cadence']} | "
        f"{float(b013['target_volatility']):.4f} | {b013['changed_in_b019']} |"  # type: ignore[arg-type]
    )
    lines.append("")
    lines.append(
        "B013 was retuned by B019 F003 from `(monthly, 0.08)` to "
        "`(quarterly, 0.11)` per the F002 winning cell. B010 is unchanged "
        "(F002 verdict `gate_met=False` for B010)."
    )
    lines.append("")

    lines.append("## Per-Window Default Backtest")
    lines.append("")
    b010_matrix = matrix["b010"]
    b013_matrix = matrix["b013"]
    assert isinstance(b010_matrix, dict)
    assert isinstance(b013_matrix, dict)
    lines.extend(_format_window_block("B010 (unchanged defaults)", b010_matrix))
    lines.extend(_format_window_block("B013 (post-F003 defaults)", b013_matrix))

    lines.append("## Provenance")
    lines.append(
        "Sidecar generated by `scripts/generate_b019_default_change_baseline.py`."
    )
    lines.append(
        "Cross-references: B019 spec `docs/specs/B019-b010-b013-cadence-vol-target-retune-spec.md`,"
    )
    lines.append(
        "F002 sweep sidecar `docs/test-reports/B019-retune-sweep-2026-05-15.{json,md}`."
    )
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the B014 yfinance manifest JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the JSON + Markdown sidecars are written.",
    )
    parser.add_argument(
        "--report-date",
        type=lambda value: date.fromisoformat(value),
        default=None,
        help="Override the report date (YYYY-MM-DD); defaults to today.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Override the run id; defaults to B019-default-change-baseline-<date>.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report_date = args.report_date or date.today()
    run_id = args.run_id or f"B019-default-change-baseline-{report_date.isoformat()}"

    if args.manifest_path.is_file():
        bundle = load_regime_adaptive_snapshot_records(args.manifest_path)
        records = bundle.records
        real_data_status: dict[str, object] = {
            "status": "ran",
            "snapshot_id": bundle.snapshot_id,
            "manifest_path": str(args.manifest_path),
            "date_range": (
                f"{bundle.date_range[0].isoformat()}.."
                f"{bundle.date_range[1].isoformat()}"
            ),
        }
    else:
        records = _synthetic_records()
        real_data_status = {
            "status": "skipped",
            "snapshot_id": None,
            "manifest_path": str(args.manifest_path),
            "reason": (
                f"manifest absent at {args.manifest_path}; ran on a synthetic "
                "9-asset fixture as a schema example only. Re-run after "
                "`scripts/fetch_yfinance_regime_adaptive_csvs.py` populates "
                "the manifest to obtain real-data findings."
            ),
        }

    payload = _build_payload(
        records,
        real_data_status=real_data_status,
        report_date=report_date,
        run_id=run_id,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{run_id}.json"
    md_path = args.output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    print(f"json     : {json_path}")
    print(f"markdown : {md_path}")
    print(f"status   : {real_data_status['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
