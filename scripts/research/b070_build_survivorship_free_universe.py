#!/usr/bin/env python
"""B070 F002 — build the survivorship-free PIT A-share universe (research artifact).

Drives :mod:`scripts.research.b070_survivorship_free` against baostock's dated
index-constituent endpoints (F001 §23 = GO) and writes, to a **research data root**
(NOT the production ``/var/lib/workbench/data`` B067's live advisory reads):

  * ``snapshots/universe/cn_pit_universe.csv`` — survivorship-FREE: real
    HS300∪ZZ500∪SZ50 membership per quarterly rebalance, INCLUDING now-delisted
    names (the gap B068's current-only universe was blind to).
  * ``snapshots/universe/cn_pit_universe_current_control.csv`` — survivorship-BIASED
    control: today's index members applied to every historical rebalance date
    (survivors only). F003 backtests BOTH; their OOS difference isolates
    survivorship as the single variable (composition otherwise identical).

Both share ``cn_universe.UNIVERSE_HEADER`` so ``trade.data.cn_attack_universe``
reads them unchanged (point the loader at the research root via WORKBENCH_DATA_ROOT,
as B068's ``run_cn_wide_backtest.py`` does).

Evidence (spec §3 F002): per-rebalance member count + the *non-current-member*
fraction, plus a bounded ``query_stock_basic`` sample that splits that fraction into
TRULY-DELISTED vs merely-rotated-out (F001 §5 verify-lens honesty: rotations
dominate; the survivorship gap is the delisted subset only).

HARD BOUNDARY: baostock only (no broker SDK). Runs from the root ``.venv``
(baostock installed; no ``workbench_api`` import needed). Full history back to 2007
is available; default window matches B068 (2019+) for the F003 comparison.

Usage::

    .venv/bin/python scripts/research/b070_build_survivorship_free_universe.py \
        --out-dir data/research/b070 --from-date 2019-01-01 \
        --out-json data/research/b070/f002_universe_build.json
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import date
from pathlib import Path

from scripts.research.b070_survivorship_free import (
    UNIVERSE_HEADER,
    DatedConstituentLoader,
    TransientConstituentError,
    build_current_control_rows,
    build_pit_universe_rows,
    delisted_fraction,
    quarterly_rebalance_dates,
    to_baostock,
)

logger = logging.getLogger(__name__)

UNIVERSE_RELPATH = ("snapshots", "universe", "cn_pit_universe.csv")
CONTROL_RELPATH = ("snapshots", "universe", "cn_pit_universe_current_control.csv")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B070 F002 survivorship-free universe build")
    parser.add_argument("--out-dir", type=Path, required=True, help="research data root (NOT prod)")
    parser.add_argument("--from-date", type=_parse_date, default=date(2019, 1, 1))
    parser.add_argument("--to-date", type=_parse_date, default=date.today())
    parser.add_argument("--out-json", type=Path, default=None, help="also write summary JSON here")
    parser.add_argument(
        "--delist-sample",
        type=int,
        default=80,
        help="bounded query_stock_basic checks to split non-current into delisted vs rotated",
    )
    return parser.parse_args(argv)


def _write_csv(path: Path, rows: list[tuple[str, str, int, str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(UNIVERSE_HEADER)
        writer.writerows(rows)


def _classify_non_current(bs: object, codes: list[str], limit: int) -> dict[str, object]:
    """Bounded split of non-current members into truly-delisted vs rotated-out
    (status / outDate via query_stock_basic). Honest evidence, not a full census."""
    delisted: list[dict[str, str]] = []
    checked = 0
    for canonical in codes[:limit]:
        rs = bs.query_stock_basic(code=to_baostock(canonical))  # type: ignore[attr-defined]
        rows: list[list[str]] = []
        while getattr(rs, "error_code", "0") == "0" and rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            continue
        checked += 1
        row = rows[0]  # code, code_name, ipoDate, outDate, type, status
        out_date = row[3] if len(row) > 3 else ""
        status = row[5] if len(row) > 5 else ""
        if (out_date and out_date != "") or status == "0":
            delisted.append({"ticker": canonical, "name": row[1], "outDate": out_date})
    rate = round(len(delisted) / checked, 4) if checked else 0.0
    return {
        "sampled": min(limit, len(codes)),
        "checked": checked,
        "delisted_in_sample": len(delisted),
        "delisted_rate_in_sample": rate,
        "delisted_examples": delisted[:12],
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)

    import baostock as bs

    login = bs.login()
    logger.info("baostock login: %s %s", login.error_code, login.error_msg)
    try:
        loader = DatedConstituentLoader(bs)
        rebalances = quarterly_rebalance_dates(args.from_date, args.to_date)
        members_by_date: dict[date, tuple[str, ...]] = {}
        for as_of in rebalances:
            try:
                members_by_date[as_of] = loader.pit_members(as_of)
            except TransientConstituentError as exc:
                logger.error("skip rebalance %s — %s", as_of.isoformat(), exc)
        current_members = loader.current_members(args.to_date)

        pit_rows = build_pit_universe_rows(members_by_date)
        control_rows = build_current_control_rows(current_members, members_by_date.keys())

        _write_csv(args.out_dir.joinpath(*UNIVERSE_RELPATH), pit_rows)
        _write_csv(args.out_dir.joinpath(*CONTROL_RELPATH), control_rows)

        # evidence: per-date counts + non-current fraction (rotated + delisted)
        current_set = frozenset(current_members)
        per_date = {
            as_of.isoformat(): {
                "members": len(members),
                "non_current_fraction": delisted_fraction(members, current_set),
            }
            for as_of, members in sorted(members_by_date.items())
        }
        union_ever = sorted({m for members in members_by_date.values() for m in members})
        non_current = [m for m in union_ever if m not in current_set]
        delist_sample = _classify_non_current(bs, non_current, args.delist_sample)
    finally:
        bs.logout()

    doc = {
        "batch": "b070_f002_survivorship_free_universe",
        "from_date": args.from_date.isoformat(),
        "to_date": args.to_date.isoformat(),
        "rebalance_count": len(members_by_date),
        "current_member_count": len(current_members),
        "union_ever_members": len(union_ever),
        "non_current_members": len(non_current),
        "universe_path": str(args.out_dir.joinpath(*UNIVERSE_RELPATH)),
        "control_path": str(args.out_dir.joinpath(*CONTROL_RELPATH)),
        "per_rebalance": per_date,
        "non_current_delisted_sample": delist_sample,
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
