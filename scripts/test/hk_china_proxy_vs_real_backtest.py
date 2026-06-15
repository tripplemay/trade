#!/usr/bin/env python
"""B063 F004 — proxy-vs-real HK-China comparison driver (VM/ops runner, NOT CI).

Runs the B063 decision backtest on the prod VM, where the real CN/HK prices
(akshare, via the workbench ``data_refresh`` job) and FX rates (FRED
DEXCHUS/DEXHKUS) actually live. It reads the unified prices CSV
(``WORKBENCH_DATA_ROOT``-aware) — which now carries both the proxy ETFs
(MCHI/FXI/KWEB/ASHR, already USD) and the wide CN/HK individual-stock universe
— plus the unified FX CSV, assembles the two same-caliber USD frames, derives
the shared quarterly signal calendar, runs the comparison, and writes ONE
structured JSON payload (the F003 comparison + run metadata + honest bias
notes) for the B063 decision report.

Like ``ashare_quality_check.py`` / ``ashare_p0_probe.py`` this is a spike/ops
runner — NOT in CI (``testpaths = ["tests"]``) — and never touches a broker:
read-only market data → in-memory backtest → JSON. The pure assembly logic is
:mod:`trade.backtest.hk_china_comparison_runner` (mypy-strict, unit-tested).

By default it runs TWO configurations so the report can separate concentration
from data-source (spec §3):

* ``default``   — real ``top_n=6`` (a fair multi-name basket vs diversified ETFs).
* ``matched``   — real ``top_n`` set to the proxy's ``top_n`` (isolates the
  data-source effect by holding concentration fixed).

Usage::

    WORKBENCH_DATA_ROOT=/var/lib/workbench/data \
      python scripts/test/hk_china_proxy_vs_real_backtest.py --out comparison.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# trade is importable as an installed wheel on the VM and from the repo root in a
# dev checkout; no sys.path surgery needed (unlike the workbench-only scripts).
from trade.backtest.hk_china_comparison_runner import (
    build_runner_payload,
    build_usd_frames,
    run_comparison_from_unified,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.data_root import unified_prices_path
from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import (
    PRICES_REQUIRED_COLUMNS,
    UNIFIED_PRICES_PATH,
)
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/test/hk_china_proxy_vs_real_backtest.py",
        description="B063 F004 — run the proxy-vs-real HK-China comparison on real VM data.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the JSON report here (default: stdout).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Override WORKBENCH_DATA_ROOT for the unified prices + FX CSVs.",
    )
    parser.add_argument(
        "--real-top-n",
        type=int,
        default=HkChinaRealParameters().top_n,
        help="Real-side basket size for the 'default' config (default: %(default)s).",
    )
    parser.add_argument(
        "--starting-capital",
        type=float,
        default=BacktestParameters().starting_capital,
        help="Starting capital, USD (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _load_unified_prices() -> pd.DataFrame:
    path = unified_prices_path(UNIFIED_PRICES_PATH)
    if not path.is_file():
        raise SystemExit(f"unified prices CSV not found: {path}")
    frame = pd.read_csv(path)
    missing = [c for c in PRICES_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SystemExit(f"unified prices CSV {path} missing required columns {missing}")
    return frame


def _run_config(
    unified: pd.DataFrame,
    converter: FxConverter,
    *,
    real_top_n: int,
    backtest_parameters: BacktestParameters,
) -> dict[str, object]:
    proxy_parameters = HkChinaMomentumParameters()
    real_parameters = HkChinaRealParameters(top_n=real_top_n)
    result, signal_dates = run_comparison_from_unified(
        unified,
        converter,
        proxy_parameters=proxy_parameters,
        real_parameters=real_parameters,
        backtest_parameters=backtest_parameters,
    )
    proxy_usd, real_usd = build_usd_frames(
        unified,
        converter,
        proxy_defensive_asset=proxy_parameters.defensive_asset,
        real_defensive_asset=real_parameters.defensive_asset,
    )
    return build_runner_payload(result, signal_dates, proxy_usd, real_usd)


def _summary_line(label: str, payload: dict[str, Any]) -> str:
    proxy_m = payload["proxy"]["metrics"]
    real_m = payload["real"]["metrics"]
    return (
        f"[{label}] n={payload['run_metadata']['n_signal_dates']} | "
        f"proxy CAGR={proxy_m['cagr']:.4f} Sharpe={proxy_m['sharpe']:.3f} "
        f"MaxDD={proxy_m['max_drawdown']:.4f} | "
        f"real CAGR={real_m['cagr']:.4f} Sharpe={real_m['sharpe']:.3f} "
        f"MaxDD={real_m['max_drawdown']:.4f}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.data_root is not None:
        os.environ["WORKBENCH_DATA_ROOT"] = str(args.data_root)

    unified = _load_unified_prices()
    converter = FxConverter.load()
    backtest_parameters = BacktestParameters(starting_capital=args.starting_capital)
    proxy_top_n = HkChinaMomentumParameters().top_n

    configs = {
        "default": args.real_top_n,  # fair multi-name basket vs diversified ETFs
        "matched_top_n": proxy_top_n,  # isolate data-source: concentration held fixed
    }
    report: dict[str, object] = {
        "batch": "B063",
        "feature": "F004",
        "generated_at": datetime.now(UTC).isoformat(),
        "proxy_top_n": proxy_top_n,
        "fx_currencies_loaded": converter.currencies(),
        "configs": {},
    }
    for label, real_top_n in configs.items():
        payload = _run_config(
            unified,
            converter,
            real_top_n=real_top_n,
            backtest_parameters=backtest_parameters,
        )
        report["configs"][label] = payload  # type: ignore[index]
        print(_summary_line(label, payload), file=sys.stderr)

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
