#!/usr/bin/env python
"""B077 F002 — fetch the 龙虎榜机构席位 (dragon-tiger institutional-seat) event history.

NOT product code. The data-gather prerequisite for F002's first-look signal probe:
F001 found ``stock_lhb_jgmmtj_em`` is the cleanest LIVE smart-money signal with
~6y depth (institutional net-buy ``机构买入净额`` per LHB-listed stock). This script
walks month-long windows back over the B070 de-biased universe period and writes a
flat event table the (offline, deterministic, unit-tested) IC probe then joins to
the B070 survivorship-free prices for forward returns.

It is intentionally a SLOW one-time VM gather (eastmoney finance host, ~7s/window),
decoupled from the fast compute exactly like B076's fetch/compare split. best-effort:
a window that fails is logged + skipped, never fatal. read-only public disclosure
(akshare) — never a broker SDK.

Self-contained (inlines the few akshare-frame helpers) so it copies to the VM ``/tmp``
and runs under ``/opt/workbench/.venv`` with no workbench_api on the path::

    scp scripts/research/b077_fetch_lhb_events.py tripplezhou@<vm>:/tmp/
    /opt/workbench/.venv/bin/python /tmp/b077_fetch_lhb_events.py \
        --from 2019-01 --to 2026-06 --out /tmp/b077_lhb_inst_events.csv
"""

from __future__ import annotations

import argparse
import csv
import importlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVENT_HEADER = (
    "event_date",
    "ticker",
    "inst_net_buy",
    "inst_buyers",
    "inst_sellers",
    "inst_net_buy_pct",
)

# stock_lhb_jgmmtj_em real columns (§23-verified F001 2026-06-25).
_COL_DATE = "上榜日期"
_COL_CODE = "代码"
_COL_NET_BUY = "机构买入净额"
_COL_BUYERS = "买方机构数"
_COL_SELLERS = "卖方机构数"
_COL_NET_BUY_PCT = "机构净买额占总成交额比"


def coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if result != result else result  # NaN -> None


def coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def code_to_canonical(code: object) -> str | None:
    """Bare 6-digit eastmoney code -> canonical (``.SH`` for 6/9 lead, else ``.SZ``)."""
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    return f"{digits}.{'SH' if digits[0] in {'6', '9'} else 'SZ'}"


def month_windows(from_ym: str, to_ym: str) -> list[tuple[str, str]]:
    """Inclusive month windows ``[(YYYYMMDD_start, YYYYMMDD_end), ...]`` oldest first."""
    fy, fm = (int(p) for p in from_ym.split("-"))
    ty, tm = (int(p) for p in to_ym.split("-"))
    out: list[tuple[str, str]] = []
    year, month = fy, fm
    while (year, month) <= (ty, tm):
        start = date(year, month, 1)
        end = date(year + (month == 12), (month % 12) + 1, 1)  # first of next month
        last = date.fromordinal(end.toordinal() - 1)  # last day of this month
        out.append((start.strftime("%Y%m%d"), last.strftime("%Y%m%d")))
        year, month = year + (month == 12), (month % 12) + 1
    return out


def _frame_records(module: Any, fn_name: str, **kwargs: Any) -> list[dict[str, Any]]:
    fn = getattr(module, fn_name, None)
    if fn is None:
        return []
    try:
        frame = fn(**kwargs)
        return frame.to_dict("records") if frame is not None else []
    except Exception:  # noqa: BLE001 — best-effort per window
        return []


def event_rows(records: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """``stock_lhb_jgmmtj_em`` records -> EVENT_HEADER rows (skip unparseable)."""
    rows: list[tuple[Any, ...]] = []
    for record in records:
        event_date = coerce_date(record.get(_COL_DATE))
        ticker = code_to_canonical(record.get(_COL_CODE))
        net_buy = coerce_float(record.get(_COL_NET_BUY))
        if event_date is None or ticker is None or net_buy is None:
            continue
        rows.append(
            (
                event_date.isoformat(),
                ticker,
                round(net_buy, 2),
                coerce_float(record.get(_COL_BUYERS)),
                coerce_float(record.get(_COL_SELLERS)),
                coerce_float(record.get(_COL_NET_BUY_PCT)),
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B077 F002 LHB institutional-seat fetch")
    parser.add_argument("--from", dest="from_ym", default="2019-01", help="YYYY-MM start")
    parser.add_argument("--to", dest="to_ym", default="2026-06", help="YYYY-MM end")
    parser.add_argument("--out", type=Path, required=True, help="event CSV output path")
    cli = parser.parse_args(argv)

    try:
        akshare = importlib.import_module("akshare")
    except Exception:  # noqa: BLE001
        logger.error("akshare not importable — cannot fetch")
        return 1

    windows = month_windows(cli.from_ym, cli.to_ym)
    cli.out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    empty_windows = 0
    with cli.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(EVENT_HEADER)
        for index, (start, end) in enumerate(windows, start=1):
            records = _frame_records(
                akshare, "stock_lhb_jgmmtj_em", start_date=start, end_date=end
            )
            rows = event_rows(records)
            if not rows:
                empty_windows += 1
            for row in rows:
                writer.writerow(row)
            total += len(rows)
            if index % 12 == 0 or index == len(windows):
                logger.info("…%d/%d windows (%d events)", index, len(windows), total)

    logger.info(
        "done: %d events across %d windows (%d empty) -> %s",
        total, len(windows), empty_windows, cli.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
