#!/usr/bin/env python
"""B068 F001 — build the WIDE A-share point-in-time universe (research artifact).

Wires the existing, unit-tested universe primitives
(:func:`~workbench_api.data_refresh.cn_marketcap.discover_ashare_superset` →
:func:`~workbench_api.data_refresh.cn_universe.build_cn_universe`) into a
standalone research build that writes to a **research data root**, NOT the
production ``/var/lib/workbench/data`` that B067's live cn_attack advisory reads.
Keeping the wide universe out of the production path is the spec invariant #1
("不改 B067 surface"): F003's backtest injects this CSV explicitly, the live
advisory keeps consuming the curated seed-43 universe.

§23 (B068 F001): the wide superset is discovered from akshare's **sina spot**
(``stock_zh_a_spot``) — the only bulk list endpoint reachable on the prod VM
(the eastmoney push hosts ConnectionError there; verified by
``scripts/test/ashare_universe_probe.py --label vm``). Per-symbol historical
market cap comes from ``stock_value_em`` (eastmoney *finance* host, reachable
local + VM). The point-in-time top-N ranking inside ``build_cn_universe`` uses
only data dated ``<= as_of`` so membership is structurally leakage-free.

Turnover (the secondary ranking dimension) is read from an existing unified
prices CSV when supplied; the wide names are not in the seed prices CSV yet (F003
fetches their prices), so they rank on market cap alone here — honest and
leakage-free. The seed names that ARE priced still get their turnover dimension.

HARD BOUNDARY: akshare only (no broker SDK). Run on the VM from the deployed
backend so ``workbench_api`` imports resolve::

    cd /srv/workbench/current/backend
    /opt/workbench/.venv/bin/python /tmp/build_cn_wide_universe.py \
        --out-dir /var/lib/workbench/data/research/b068 \
        --prices-path /var/lib/workbench/data/snapshots/prices/unified/prices_daily.csv \
        --superset-size 500 --top-n 250 --from-date 2019-01-01
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path

from workbench_api.data_refresh.cn_marketcap import (
    CnMarketCapLoader,
    discover_ashare_superset,
)
from workbench_api.data_refresh.cn_universe import (
    UNIVERSE_RELPATH,
    build_cn_universe,
    quarterly_rebalance_dates,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B068 F001 wide A-share universe build")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="research data root (writes <out>/snapshots/universe/*.csv); NOT production",
    )
    parser.add_argument(
        "--prices-path",
        type=Path,
        default=None,
        help="unified prices CSV for the turnover dimension (optional; wide names "
        "rank on market cap alone when absent)",
    )
    parser.add_argument(
        "--superset-size",
        type=int,
        default=500,
        help="how many current top-turnover names to fetch market cap for (∪ seed)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=250,
        help="point-in-time universe size per rebalance (spec: 200-300)",
    )
    parser.add_argument("--from-date", type=_parse_date, default=date(2019, 1, 1))
    parser.add_argument("--to-date", type=_parse_date, default=date.today())
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="also write the summary JSON to this path",
    )
    return parser.parse_args(argv)


def _members_per_date(universe_path: Path) -> dict[str, int]:
    """Count members per as_of date in the written universe CSV (evidence)."""

    if not universe_path.is_file():
        return {}
    with universe_path.open(encoding="utf-8", newline="") as handle:
        counter = Counter(row["as_of_date"] for row in csv.DictReader(handle))
    return dict(sorted(counter.items()))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)

    # allow_sina_fallback=True is the whole point of this research build — it
    # opts into the VM-reachable sina spot the production refresh deliberately
    # does NOT use (so the live B067 advisory keeps its seed-43 universe).
    superset, provenance = discover_ashare_superset(
        top_n=args.superset_size, allow_sina_fallback=True
    )
    rebalances = quarterly_rebalance_dates(args.from_date, args.to_date)
    # No prices CSV → a non-existent sentinel path; build_cn_universe's reader
    # returns [] for a missing file, so every name's turnover dimension is 0
    # (mcap-only ranking). The wide names aren't priced yet anyway (F003 fetches).
    prices_path = args.prices_path or args.out_dir / "_no_prices_sentinel.csv"

    summary = build_cn_universe(
        data_root=args.out_dir,
        prices_path=prices_path,
        marketcap_loader=CnMarketCapLoader(),
        superset=superset,
        rebalance_dates=rebalances,
        from_date=args.from_date,
        to_date=args.to_date,
        top_n=args.top_n,
    )

    universe_path = args.out_dir.joinpath(*UNIVERSE_RELPATH)
    per_date = _members_per_date(universe_path)
    doc = {
        "batch": "b068_f001_wide_universe",
        "superset_provenance": provenance,
        "superset_size": summary.superset_size,
        "marketcap_symbols": summary.marketcap_symbols,
        "marketcap_rows": summary.marketcap_rows,
        "rebalance_dates": summary.rebalance_dates,
        "universe_rows": summary.universe_rows,
        "fetch_errors": summary.errors,
        "top_n": args.top_n,
        "from_date": args.from_date.isoformat(),
        "to_date": args.to_date.isoformat(),
        "universe_path": summary.universe_path,
        "marketcap_path": summary.marketcap_path,
        "members_per_date": per_date,
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
