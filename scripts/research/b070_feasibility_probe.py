#!/usr/bin/env python
"""B070 F001 §23 — survivorship-free A-share data feasibility probe.

NOT product code. A spike tool answering the single hard prerequisite for the
whole B070 batch (spec §1): **can the FREE data sources (akshare / baostock)
deliver the two ingredients a survivorship-free revalidation needs?**

    Gate A — Historical point-in-time index constituents (incl. names that have
             SINCE been delisted/removed). akshare's ``index_stock_cons*`` family
             returns only the CURRENT membership (no date arg), so Gate A hinges
             entirely on baostock's *dated* ``query_{hs300,zz500,sz50}_stocks``.
    Gate B — Historical prices for now-delisted names during their LISTED window
             (so a backtest can actually trade them). baostock retains delisted
             tickers' k-line history; akshare ``stock_zh_a_hist`` is the alternate.
    Gate C — Scale: hundreds of names × multiple years of daily pulls within an
             acceptable wall-clock for a (gated, research-only) universe build.

cn_universe.py's own docstring records the residual survivorship bias B065 could
not fix: *"cannot include names delisted before today without a PAID historical-
constituents feed."* This probe's entire job is to test whether a FREE feed
(baostock dated constituents) closes that gap after all.

Judgment (spec §1):
    GO       = Gate A reachable AND truly point-in-time (membership changes over
               time AND includes now-delisted names) AND Gate B reachable.
    PARTIAL  = Gate A reachable but Gate B (delisted prices) missing → bias only
               partially removable; residual must be honestly flagged.
    NO-GO    = Gate A unreachable / not truly point-in-time → free sources cannot
               fix it → honest conclusion: strategy stays research-only, real
               validation needs a paid feed (Wind / JoinQuant).

NO-GO / PARTIAL is a SUCCESSFUL spike, not a failure (spec §1, §3 F001).

HARD BOUNDARY: databases only (akshare / baostock). Never a broker SDK.

Usage::

    .venv/bin/python scripts/research/b070_feasibility_probe.py
    .venv/bin/python scripts/research/b070_feasibility_probe.py --out probe.json --label vm
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from collections.abc import Callable
from typing import Any

# --- date ladder for the constituent-history depth probe. Spans the full plausible
# baostock history so the report can state how many years are actually available.
CONSTITUENT_DATE_LADDER: tuple[str, ...] = (
    "2007-01-31",
    "2010-01-29",
    "2013-01-31",
    "2016-01-29",
    "2019-01-31",
    "2022-01-28",
    "2025-01-27",
    "2026-01-30",
)

# baostock dated point-in-time index-constituent endpoints (Gate A candidates).
PIT_INDEX_FNS: tuple[tuple[str, str], ...] = (
    ("hs300", "query_hs300_stocks"),
    ("zz500", "query_zz500_stocks"),
    ("sz50", "query_sz50_stocks"),
)

# Known now-delisted A-shares to test Gate B price retrieval during their LISTED
# window. (baostock code, human name, a window when it was demonstrably trading).
DELISTED_PRICE_TESTS: tuple[tuple[str, str, str, str], ...] = (
    ("sz.300104", "乐视网 (delisted 2020)", "2017-01-01", "2019-06-30"),
    ("sz.300431", "暴风集团 (delisted 2020)", "2017-01-01", "2019-06-30"),
    ("sz.002450", "*ST康得新 (delisted 2021)", "2017-01-01", "2018-12-31"),
    ("sh.600090", "*ST济堂 (delisted 2021)", "2017-01-01", "2019-12-31"),
)

K_FIELDS = "date,code,open,high,low,close,volume,amount,turn,pctChg"


def _err(stage: str, exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "stage": stage,
        "error_class": type(exc).__name__,
        "error": str(exc)[:400],
        "traceback_tail": traceback.format_exc().splitlines()[-3:],
    }


def _drain(rs: Any) -> list[list[str]]:
    """Drain a baostock ResultData cursor into a list of row lists."""
    rows: list[list[str]] = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    return rows


def _timed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.monotonic()
    out = fn(*args, **kwargs)
    return out, round(time.monotonic() - start, 2)


def _fetch_k(bs: Any, code: str, start: str, end: str) -> list[list[str]]:
    """Drain a delisted/active name's daily k-line over a window (qfq, adjustflag=2)."""
    return _drain(
        bs.query_history_k_data_plus(
            code, K_FIELDS, start_date=start, end_date=end, frequency="d", adjustflag="2"
        )
    )


def probe_gate_a(bs: Any) -> dict[str, Any]:
    """Gate A: dated point-in-time constituents — depth, membership change, and
    the survivorship test (do historical lists carry now-delisted names?)."""
    out: dict[str, Any] = {"gate": "A_historical_pit_constituents", "indexes": {}}
    union_codes: set[str] = set()
    current_codes: set[str] = set()

    for key, fn_name in PIT_INDEX_FNS:
        fn = getattr(bs, fn_name)
        ladder: list[dict[str, Any]] = []
        earliest: str | None = None
        first_codes: set[str] = set()
        last_codes: set[str] = set()
        for d in CONSTITUENT_DATE_LADDER:
            try:
                rs, elapsed = _timed(fn, date=d)
                rows = _drain(rs)
            except Exception as exc:  # noqa: BLE001
                ladder.append({"requested": d, **_err(f"{fn_name}({d})", exc)})
                continue
            codes = {r[1] for r in rows}
            actual_date = rows[0][0] if rows else None
            ladder.append(
                {
                    "requested": d,
                    "actual_update_date": actual_date,
                    "n_constituents": len(rows),
                    "elapsed_s": elapsed,
                    "sample": rows[:2],
                }
            )
            if rows:
                if earliest is None:
                    earliest = actual_date
                    first_codes = codes
                last_codes = codes
                union_codes |= codes
        # membership-change proof (point-in-time, not a static snapshot)
        delta = {
            "first_date_n": len(first_codes),
            "last_date_n": len(last_codes),
            "left_index": len(first_codes - last_codes),
            "joined_index": len(last_codes - first_codes),
            "left_sample": sorted(first_codes - last_codes)[:6],
        }
        out["indexes"][key] = {
            "fn": fn_name,
            "earliest_data_date": earliest,
            "ladder": ladder,
            "membership_change": delta,
        }
        current_codes |= last_codes

    # survivorship test: historical-ever members no longer current — how many are
    # now DELISTED (status != listing per baostock basic info)? These are exactly
    # the names B068's current-only universe could not see.
    ever_not_now = sorted(union_codes - current_codes)
    delist_check: dict[str, Any] = {
        "union_ever_members": len(union_codes),
        "current_members": len(current_codes),
        "ever_but_not_current": len(ever_not_now),
        "delisted_confirmed": [],
        "checked": 0,
    }
    for code in ever_not_now[:40]:  # bounded basic-info lookups
        try:
            rs = bs.query_stock_basic(code=code)
            rows = _drain(rs)
        except Exception:  # noqa: BLE001
            continue
        delist_check["checked"] += 1
        if not rows:
            continue
        # fields: code, code_name, ipoDate, outDate, type, status
        row = rows[0]
        out_date = row[3] if len(row) > 3 else ""
        status = row[5] if len(row) > 5 else ""
        if (out_date and out_date != "") or status == "0":
            name = row[1] if len(row) > 1 else code
            delist_check["delisted_confirmed"].append(
                {"code": name, "name": name, "outDate": out_date, "status": status}
            )
    delist_check["n_delisted_confirmed"] = len(delist_check["delisted_confirmed"])
    delist_check["delisted_confirmed"] = delist_check["delisted_confirmed"][:10]
    out["survivorship_test"] = delist_check
    return out


def probe_gate_b(bs: Any) -> dict[str, Any]:
    """Gate B: can we fetch a NOW-DELISTED name's prices during its listed window?"""
    out: dict[str, Any] = {"gate": "B_delisted_name_prices", "tests": []}
    for code, name, start, end in DELISTED_PRICE_TESTS:
        try:
            rows, elapsed = _timed(_fetch_k, bs, code, start, end)
        except Exception as exc:  # noqa: BLE001
            out["tests"].append({"code": code, "name": name, **_err("k_data", exc)})
            continue
        out["tests"].append(
            {
                "code": code,
                "name": name,
                "window": f"{start}..{end}",
                "ok": bool(rows),
                "n_rows": len(rows),
                "elapsed_s": elapsed,
                "first_row": rows[0] if rows else None,
                "last_row": rows[-1] if rows else None,
            }
        )
    out["n_reachable"] = sum(1 for t in out["tests"] if t.get("ok"))
    return out


def probe_gate_c(bs: Any) -> dict[str, Any]:
    """Gate C: scale — time a full-history single fetch + a 5-name batch, extrapolate."""
    out: dict[str, Any] = {"gate": "C_scale"}
    sample_codes = ["sh.600519", "sh.601318", "sz.000001", "sz.300750", "sh.600036"]
    try:
        single_rows, single_s = _timed(_fetch_k, bs, "sh.600519", "2015-01-01", "2026-06-19")
        out["single_full_history_s"] = single_s
        out["single_full_history_rows"] = len(single_rows)
        batch_start = time.monotonic()
        batch_rows = 0
        for code in sample_codes:
            batch_rows += len(_fetch_k(bs, code, "2015-01-01", "2026-06-19"))
        batch_s = round(time.monotonic() - batch_start, 2)
        per_name = round(batch_s / len(sample_codes), 2)
        out.update(
            {
                "batch_n": len(sample_codes),
                "batch_total_s": batch_s,
                "batch_total_rows": batch_rows,
                "per_name_s": per_name,
                "est_800_names_min": round(per_name * 800 / 60, 1),
            }
        )
    except Exception as exc:  # noqa: BLE001
        out.update(_err("scale", exc))
    return out


def probe_akshare_current_only(ak: Any) -> dict[str, Any]:
    """Negative control: confirm akshare's index_stock_cons* are CURRENT-only (no
    date arg) — i.e. cannot supply Gate A on their own. Reachability best-effort."""
    out: dict[str, Any] = {
        "note": "akshare index_stock_cons* take no date arg (current-only)",
        "checks": {},
    }
    for fn_name in ("index_stock_cons_csindex", "index_stock_cons"):
        fn = getattr(ak, fn_name, None)
        if fn is None:
            out["checks"][fn_name] = {"ok": False, "error": "missing"}
            continue
        try:
            df, elapsed = _timed(fn, symbol="000300")
            # NOTE: these fns expose no date parameter in their signature (verified
            # via inspect.signature → current-only); we record the reachable shape,
            # not an asserted date-arg flag. Gate A is delivered by baostock, not here.
            out["checks"][fn_name] = {
                "ok": True,
                "n_rows": int(len(df)),
                "columns": [str(c) for c in df.columns][:12],
                "elapsed_s": elapsed,
            }
        except Exception as exc:  # noqa: BLE001
            out["checks"][fn_name] = _err(fn_name, exc)
    return out


def judge(gate_a: dict[str, Any], gate_b: dict[str, Any]) -> dict[str, Any]:
    """Mechanical GO / PARTIAL / NO-GO from the gathered evidence (spec §1)."""
    a_reachable = any(idx.get("earliest_data_date") for idx in gate_a.get("indexes", {}).values())
    changes = any(
        idx.get("membership_change", {}).get("left_index", 0) > 0
        for idx in gate_a.get("indexes", {}).values()
    )
    has_delisted_members = gate_a.get("survivorship_test", {}).get("n_delisted_confirmed", 0) > 0
    a_truly_pit = a_reachable and changes and has_delisted_members
    b_reachable = gate_b.get("n_reachable", 0) > 0

    if a_truly_pit and b_reachable:
        verdict = "GO"
        reason = (
            "Gate A point-in-time (dated, membership changes, carries now-delisted names) "
            "AND Gate B delisted prices reachable."
        )
    elif a_truly_pit and not b_reachable:
        verdict = "PARTIAL"
        reason = (
            "Gate A point-in-time but Gate B delisted prices missing → "
            "bias only partially removable; flag residual."
        )
    elif a_reachable and not a_truly_pit:
        verdict = "PARTIAL"
        reason = (
            "Gate A reachable but not demonstrably survivorship-free "
            "(no membership change or no now-delisted members found)."
        )
    else:
        verdict = "NO-GO"
        reason = (
            "Gate A unreachable → free sources cannot fix survivorship bias; "
            "strategy stays research-only (needs paid feed)."
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "signals": {
            "gate_a_reachable": a_reachable,
            "gate_a_membership_changes": changes,
            "gate_a_carries_delisted": has_delisted_members,
            "gate_a_truly_point_in_time": a_truly_pit,
            "gate_b_delisted_prices_reachable": b_reachable,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B070 F001 §23 survivorship-free feasibility probe"
    )
    parser.add_argument("--out", type=str, default=None, help="also write JSON to this path")
    parser.add_argument("--label", type=str, default="local", help="run label (env/timeslot)")
    parser.add_argument(
        "--skip-akshare", action="store_true", help="skip the akshare negative control"
    )
    cli = parser.parse_args()

    import baostock as bs

    lg = bs.login()
    login_info = {"error_code": lg.error_code, "error_msg": lg.error_msg}
    try:
        gate_a = probe_gate_a(bs)
        gate_b = probe_gate_b(bs)
        gate_c = probe_gate_c(bs)
    finally:
        bs.logout()

    akshare_ctrl: dict[str, Any] = {"skipped": True}
    if not cli.skip_akshare:
        try:
            import akshare as ak

            akshare_ctrl = probe_akshare_current_only(ak)
        except Exception as exc:  # noqa: BLE001
            akshare_ctrl = _err("akshare_import", exc)

    doc = {
        "probe": "b070_survivorship_free_feasibility",
        "run_label": cli.label,
        "baostock_login": login_info,
        "gate_a_historical_pit_constituents": gate_a,
        "gate_b_delisted_name_prices": gate_b,
        "gate_c_scale": gate_c,
        "akshare_current_only_control": akshare_ctrl,
        "judgment": judge(gate_a, gate_b),
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if cli.out:
        with open(cli.out, "w", encoding="utf-8") as handle:
            handle.write(text)


if __name__ == "__main__":
    main()
