#!/usr/bin/env python
"""B068 F003 — fetch WIDE A-share prices + fundamentals + benchmark (research data).

The data prerequisite for the 4-config wide-universe backtest. Reads the F001 wide
PIT universe (``cn_pit_universe.csv``), then fetches — per member, best-effort —

* **prices** via :class:`CnSymbolProvider` (eastmoney→sina→baostock fallback; the
  sina ``stock_zh_a_daily`` leg is the VM-reachable one, B066/B068 §23), and
* **CAS fundamentals** via :class:`CnFundamentalsLoader`
  (``stock_financial_abstract`` + ``stock_value_em``, eastmoney *finance* host,
  reachable local + VM — verified B068 F003),

writing the unified CSVs into a **research data root** (NOT the production
``/var/lib/workbench/data`` that B067's live advisory reads). The CSI 300
benchmark is fetched via the sina index endpoint. The F003 runner then points
``WORKBENCH_DATA_ROOT`` at this research root so the existing loaders read exactly
this data and the 4-config comparison runs on the wide universe — leaving the live
B067 surface untouched (spec invariant #1).

Quality (for Q1) needs the wide fundamentals; prices (for Q2 σ / Q3) need the wide
price history. Per-member failures are logged + counted, never fatal (a thin name
just drops out, honestly).

HARD BOUNDARY: akshare only (no broker SDK). Run on the VM from the deployed
backend so ``workbench_api`` imports resolve::

    cd /srv/workbench/current/backend
    /opt/workbench/.venv/bin/python /tmp/fetch_cn_wide_data.py \
        --universe ~/b068_out/snapshots/universe/cn_pit_universe.csv \
        --out-dir ~/b068_out --from-date 2017-06-01
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import date
from pathlib import Path

from workbench_api.data_refresh.cn_benchmark import AkshareCsiLoader, run_cn_benchmark_refresh
from workbench_api.data_refresh.cn_fundamentals import CnFundamentalsLoader
from workbench_api.data_refresh.refresh import (
    FUNDAMENTALS_HEADER,
    FUNDAMENTALS_RELPATH,
    PRICES_HEADER,
    PRICES_RELPATH,
)
from workbench_api.symbols.cn_provider import CnSymbolProvider

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B068 F003 wide CN data fetch")
    parser.add_argument("--universe", type=Path, required=True, help="wide cn_pit_universe.csv")
    parser.add_argument("--out-dir", type=Path, required=True, help="research data root")
    parser.add_argument("--from-date", type=_parse_date, default=date(2017, 6, 1))
    parser.add_argument("--to-date", type=_parse_date, default=date.today())
    parser.add_argument("--no-prices", action="store_true")
    parser.add_argument("--no-fundamentals", action="store_true")
    parser.add_argument("--no-benchmark", action="store_true")
    parser.add_argument("--out-json", type=Path, default=None)
    return parser.parse_args(argv)


def _universe_members(universe_path: Path) -> list[str]:
    with universe_path.open(encoding="utf-8", newline="") as handle:
        members = {row["ticker"] for row in csv.DictReader(handle)}
    return sorted(members)


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


_FetchResult = tuple[list[list[object]], int, int]


def _fetch_prices(members: list[str], from_date: date, to_date: date) -> _FetchResult:
    provider = CnSymbolProvider()
    rows: list[list[object]] = []
    symbols = 0
    errors = 0
    for index, ticker in enumerate(members, start=1):
        try:
            bars = provider.get_price_history(ticker, from_date, to_date)
        except Exception:  # noqa: BLE001 — best-effort; a thin name never aborts
            errors += 1
            logger.warning("price_fetch_failure", extra={"ticker": ticker})
            continue
        if not bars:
            errors += 1
            continue
        symbols += 1
        rows.extend(
            [
                b.bar_date.isoformat(),
                b.ticker,
                b.open,
                b.high,
                b.low,
                b.close,
                b.adj_close,
                b.volume,
            ]
            for b in bars
        )
        if index % 50 == 0:
            logger.info(
                "price_progress",
                extra={"done": index, "total": len(members), "rows": len(rows)},
            )
    return rows, symbols, errors


def _fetch_fundamentals(members: list[str], from_date: date, to_date: date) -> _FetchResult:
    loader = CnFundamentalsLoader()
    rows: list[list[object]] = []
    symbols = 0
    errors = 0
    for index, ticker in enumerate(members, start=1):
        try:
            records = loader.fetch_fundamentals_rows(ticker, from_date, to_date)
        except Exception:  # noqa: BLE001 — best-effort
            errors += 1
            logger.warning("fundamentals_fetch_failure", extra={"ticker": ticker})
            continue
        if not records:
            errors += 1
            continue
        symbols += 1
        rows.extend([record.get(col) for col in FUNDAMENTALS_HEADER] for record in records)
        if index % 50 == 0:
            logger.info(
                "fundamentals_progress",
                extra={"done": index, "total": len(members), "rows": len(rows)},
            )
    return rows, symbols, errors


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    members = _universe_members(args.universe)
    summary: dict[str, object] = {
        "batch": "b068_f003_wide_data",
        "members": len(members),
        "from_date": args.from_date.isoformat(),
        "to_date": args.to_date.isoformat(),
    }

    if not args.no_prices:
        rows, symbols, errors = _fetch_prices(members, args.from_date, args.to_date)
        _write_csv(args.out_dir.joinpath(*PRICES_RELPATH), PRICES_HEADER, rows)
        summary |= {"price_symbols": symbols, "price_rows": len(rows), "price_errors": errors}

    if not args.no_fundamentals:
        rows, symbols, errors = _fetch_fundamentals(members, args.from_date, args.to_date)
        _write_csv(args.out_dir.joinpath(*FUNDAMENTALS_RELPATH), FUNDAMENTALS_HEADER, rows)
        summary |= {
            "fundamental_symbols": symbols,
            "fundamental_rows": len(rows),
            "fundamental_errors": errors,
        }

    if not args.no_benchmark:
        benchmark_rows = run_cn_benchmark_refresh(
            data_root=args.out_dir, loader=AkshareCsiLoader()
        )
        summary |= {"benchmark_rows": benchmark_rows}

    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
