#!/usr/bin/env python
"""B076 F001 — fetch PIT circulating market cap for the B070 de-biased universe.

The size-tilt factor (``small_cap_score``) ranks names by circulating market cap, but
the B070 survivorship-free universe includes **delisted** names whose market cap the
production ``stock_value_em`` loader (current-listed only) cannot serve. baostock's
daily k-data *does* retain delisted names AND carries ``turn`` (换手率 %, volume-based),
so circulating market cap is reconstructable point-in-time for the WHOLE universe:

    float_shares = volume * 100 / turn          # turn = volume / float_shares * 100
    circ_mv      = close_raw * float_shares      # raw (unadjusted) close × float shares
                 = close_raw * volume * 100 / turn

(Verified 2026-06-23: 600519.SH 2024-01-02 → ~2.1e12 CNY, matching 贵州茅台's real
circulating cap.) Prices are pulled **unadjusted** (``adjustflag="3"``) so ``close`` is
the real price level the cap identity needs — qfq close would corrupt the cap.

Output is **month-end** downsampled (last valid trading day per calendar month per name)
→ a small ``cn_size.csv`` (``data_date,ticker,market_cap``). Market cap moves slowly
versus the monthly selection cadence, so the size factor's "latest cap <= as_of" lookup
needs no finer grain, and the artifact stays ~100 dates × ~1300 names instead of daily.

gated / research-only: writes to a research path, never the production data root. baostock
only (no broker SDK). Runs from the root ``.venv`` (which has baostock). The full
~1310-name pull is a ~30-40 min background job; ``--limit`` samples for in-session tests.

Usage::

    .venv/bin/python scripts/research/b076_fetch_pit_marketcap.py \
        --universe data/research/b070/snapshots/universe/cn_pit_universe.csv \
        --out data/research/b076/cn_size.csv \
        --out-json data/research/b076/f001_size_fetch.json
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

SIZE_HEADER = ("data_date", "ticker", "market_cap")
# baostock daily fields: raw close + volume + turn (换手率 %, volume-based).
_K_FIELDS = "date,close,volume,turn"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B076 F001 PIT circ-market-cap fetch")
    parser.add_argument("--universe", type=Path, required=True, help="B070 PIT universe CSV")
    parser.add_argument("--out", type=Path, required=True, help="cn_size.csv output path")
    parser.add_argument("--from-date", type=_parse_date, default=date(2018, 1, 1))
    parser.add_argument("--to-date", type=_parse_date, default=date.today())
    parser.add_argument(
        "--limit", type=int, default=0, help="cap names fetched (0 = all; full pull is the job)"
    )
    parser.add_argument("--out-json", type=Path, default=None, help="also write summary JSON here")
    return parser.parse_args(argv)


def union_tickers(universe_csv: Path) -> list[str]:
    """Distinct tickers across all rebalance blocks in the universe CSV (sorted)."""
    if not universe_csv.is_file():
        raise FileNotFoundError(
            f"universe CSV not found: {universe_csv} (run the B070 build first)"
        )
    with universe_csv.open(encoding="utf-8", newline="") as handle:
        tickers = {row["ticker"].strip() for row in csv.DictReader(handle)}
    return sorted(tickers)


def circ_mv_from_bar(close: str, volume: str, turn: str) -> float | None:
    """``close * volume * 100 / turn`` (circulating market cap), or None if unusable.

    A suspended / no-turnover bar (``turn`` or ``volume`` zero/blank) cannot yield a
    cap and returns None so it is simply skipped (never written as a 0-cap row, which
    would poison the cross-sectional size rank)."""
    try:
        close_f = float(close)
        volume_f = float(volume)
        turn_f = float(turn)
    except (TypeError, ValueError):
        return None
    if close_f <= 0 or volume_f <= 0 or turn_f <= 0:
        return None
    return close_f * volume_f * 100.0 / turn_f


def month_end_marketcap(bars: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Downsample valid ``(date_iso, circ_mv)`` bars to the last one per calendar month.

    Input must be chronologically ordered (baostock returns ascending). Returns one
    ``(date_iso, circ_mv)`` per ``YYYY-MM`` — the month's last valid observation — so a
    name suspended on the literal month-end still contributes its last traded cap."""
    by_month: dict[str, tuple[str, float]] = {}
    for date_iso, circ_mv in bars:
        by_month[date_iso[:7]] = (date_iso, circ_mv)
    return [by_month[key] for key in sorted(by_month)]


def _fetch_one(bs: object, canonical: str, start: str, end: str) -> list[list[str]]:
    rs = bs.query_history_k_data_plus(  # type: ignore[attr-defined]
        to_baostock(canonical),
        _K_FIELDS,
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="3",  # unadjusted close — the cap identity needs the real price level
    )
    rows: list[list[str]] = []
    while getattr(rs, "error_code", "0") == "0" and rs.next():
        rows.append(rs.get_row_data())
    return rows


def _name_month_end(rows: list[list[str]]) -> list[tuple[str, float]]:
    """One name's raw k-rows (date,close,volume,turn) → month-end (date, circ_mv)."""
    valid: list[tuple[str, float]] = []
    for row in rows:
        date_iso, close, volume, turn = row[0], row[1], row[2], row[3]
        circ_mv = circ_mv_from_bar(close, volume, turn)
        if circ_mv is not None:
            valid.append((date_iso, circ_mv))
    return month_end_marketcap(valid)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)

    tickers = union_tickers(args.universe)
    if args.limit > 0:
        tickers = tickers[: args.limit]
    start, end = args.from_date.isoformat(), args.to_date.isoformat()

    import baostock as bs

    login = bs.login()
    logger.info(
        "baostock login: %s %s — sizing %d names",
        login.error_code, login.error_msg, len(tickers),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    priced: list[str] = []
    empty: list[str] = []
    try:
        with args.out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(SIZE_HEADER)
            for index, canonical in enumerate(tickers, start=1):
                rows = _fetch_one(bs, canonical, start, end)
                month_end = _name_month_end(rows)
                if not month_end:
                    empty.append(canonical)
                    continue
                priced.append(canonical)
                for date_iso, circ_mv in month_end:
                    writer.writerow((date_iso, canonical, f"{circ_mv:.2f}"))
                    total_rows += 1
                if index % 100 == 0:
                    logger.info("…%d/%d names (%d rows)", index, len(tickers), total_rows)
    finally:
        bs.logout()

    doc = {
        "batch": "b076_f001_pit_marketcap",
        "from_date": start,
        "to_date": end,
        "names_requested": len(tickers),
        "names_priced": len(priced),
        "names_empty": len(empty),
        "empty_examples": empty[:8],
        "total_rows": total_rows,
        "out_path": str(args.out),
        "note": "month-end circ_mv from baostock turn; covers delisted; limit>0 = sample",
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
