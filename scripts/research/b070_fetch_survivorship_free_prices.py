#!/usr/bin/env python
"""B070 F002 — fetch survivorship-free prices incl. delisted names (research).

Prices the UNION of every PIT member in the F002 survivorship-free universe
(``cn_pit_universe.csv``) — crucially the now-delisted names baostock retains
(F001 Gate B = REACHABLE, right-censored to each name's ``outDate``). Writes the
unified prices CSV F003's backtest reads, to a **research data root** (NOT the
production one B067's advisory reads).

Output schema = the unified prices CSV (`trade.data.loader`, DictReader-tolerant):
``date,ticker,open,high,low,close,adj_close,volume`` PLUS a ``tradestatus`` column
so F003 can mask 停牌 days (F001 §5 #1 STOP-BIAS: 停牌 is ~30% over a delisted
name's full window, not a tail effect — frozen-close bars must NOT be tradeable).
Prices are qfq (``adjustflag="2"``, matches akshare qfq / cn_provider:255), so
``adj_close = close`` (a qfq bar); only RETURNS are comparable across names.

F001 §5 #5 SCALE: ONE baostock session for the whole batch (no per-name login).
The full ~1900-name pull is the ~3-4h job F003/Codex runs on the VM; ``--limit``
samples a handful (incl. delisted) for in-session evidence.

HARD BOUNDARY: baostock only (no broker SDK). Runs from the root ``.venv``.

Usage::

    .venv/bin/python scripts/research/b070_fetch_survivorship_free_prices.py \
        --out-dir data/research/b070 --limit 40 \
        --out-json data/research/b070/f002_prices_sample.json
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import date
from pathlib import Path

from scripts.research.b070_survivorship_free import to_baostock

logger = logging.getLogger(__name__)

UNIVERSE_RELPATH = ("snapshots", "universe", "cn_pit_universe.csv")
PRICES_RELPATH = ("snapshots", "prices", "unified", "prices_daily.csv")
PRICES_HEADER = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "tradestatus",
)
# baostock k-fields (qfq); tradestatus 1=trading 0=suspended (停牌).
_K_FIELDS = "date,open,high,low,close,volume,tradestatus"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B070 F002 survivorship-free price fetch")
    parser.add_argument("--out-dir", type=Path, required=True, help="research data root (NOT prod)")
    parser.add_argument("--from-date", type=_parse_date, default=date(2018, 1, 1))
    parser.add_argument("--to-date", type=_parse_date, default=date.today())
    parser.add_argument(
        "--limit", type=int, default=0, help="cap names fetched (0 = all; full pull is the VM job)"
    )
    parser.add_argument("--out-json", type=Path, default=None, help="also write summary JSON here")
    return parser.parse_args(argv)


def _union_tickers(universe_csv: Path) -> list[str]:
    """Distinct tickers across all rebalance blocks in the universe CSV."""
    if not universe_csv.is_file():
        raise FileNotFoundError(f"universe CSV not found: {universe_csv} (run the build first)")
    with universe_csv.open(encoding="utf-8", newline="") as handle:
        tickers = {row["ticker"].strip() for row in csv.DictReader(handle)}
    return sorted(tickers)


def _fetch_one(bs: object, canonical: str, start: str, end: str) -> list[list[str]]:
    rs = bs.query_history_k_data_plus(  # type: ignore[attr-defined]
        to_baostock(canonical),
        _K_FIELDS,
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="2",
    )
    rows: list[list[str]] = []
    while getattr(rs, "error_code", "0") == "0" and rs.next():
        rows.append(rs.get_row_data())
    return rows


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)

    tickers = _union_tickers(args.out_dir.joinpath(*UNIVERSE_RELPATH))
    if args.limit > 0:
        tickers = tickers[: args.limit]
    start, end = args.from_date.isoformat(), args.to_date.isoformat()

    import baostock as bs

    login = bs.login()
    logger.info(
        "baostock login: %s %s — pricing %d names",
        login.error_code, login.error_msg, len(tickers),
    )

    prices_path = args.out_dir.joinpath(*PRICES_RELPATH)
    prices_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    suspended_rows = 0
    priced: list[str] = []
    empty: list[str] = []
    sample_delisted: dict[str, object] | None = None
    try:
        with prices_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(PRICES_HEADER)
            for canonical in tickers:
                rows = _fetch_one(bs, canonical, start, end)
                if not rows:
                    empty.append(canonical)
                    continue
                priced.append(canonical)
                for r in rows:
                    # r = date, open, high, low, close, volume, tradestatus
                    d, o, h, lo, c, vol, ts = r
                    writer.writerow((d, canonical, o, h, lo, c, c, vol, ts))
                    total_rows += 1
                    if ts == "0" or vol in ("0", "0.0", ""):
                        suspended_rows += 1
                if sample_delisted is None and rows[-1][0] < end:
                    # last bar before the window end → likely right-censored (delisted)
                    sample_delisted = {
                        "ticker": canonical,
                        "rows": len(rows),
                        "first": rows[0],
                        "last": rows[-1],
                    }
    finally:
        bs.logout()

    doc = {
        "batch": "b070_f002_survivorship_free_prices",
        "from_date": start,
        "to_date": end,
        "names_requested": len(tickers),
        "names_priced": len(priced),
        "names_empty": len(empty),
        "empty_examples": empty[:8],
        "total_rows": total_rows,
        "suspended_rows": suspended_rows,
        "suspended_fraction": round(suspended_rows / total_rows, 4) if total_rows else 0.0,
        "prices_path": str(prices_path),
        "sample_right_censored": sample_delisted,
        "note": "limit>0 = in-session sample; full ~1900-name pull is the F003/VM job",
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
