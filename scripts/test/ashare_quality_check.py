#!/usr/bin/env python
"""B062 F003 — candidate-universe data-quality runner (Codex/VM tool, NOT CI).

Fetches the B062 candidate A-share + HK universe via akshare (+ baostock for the
A-share cross-source check) and runs the **tested, pure** ``data_quality`` checks
on the result, emitting one structured JSON report. Codex runs this on the prod
VM in F004 to verify the §8 deep metrics (full-history depth / adjustment /
akshare-baostock cross-source agreement) before the data could ever feed a
strategy.

This is a spike/ops runner like ``scripts/test/ashare_p0_probe.py``: not in CI
(``testpaths = ["tests"]``), akshare / baostock lazy-imported (degrades to an
honest per-symbol error when absent), databases-only (never a broker SDK).

Usage::

    python scripts/test/ashare_quality_check.py --out quality.json
    python scripts/test/ashare_quality_check.py --symbols 600519.SH,0700.HK
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Resolve the workbench backend onto the import path so this script can reuse
# the tested symbology + akshare-frame + data-quality modules without an install.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_BACKEND_PKG = _REPO_ROOT / "workbench" / "backend"
if str(_BACKEND_PKG) not in sys.path:
    sys.path.insert(0, str(_BACKEND_PKG))

from workbench_api.data.snapshot_loader import PriceBar  # noqa: E402
from workbench_api.data_refresh.refresh import CN_HK_UNIVERSE  # noqa: E402
from workbench_api.symbols.akshare_frames import bars_from_records, to_iso  # noqa: E402
from workbench_api.symbols.data_quality import assess_symbol  # noqa: E402
from workbench_api.symbols.symbol_ref import SymbolRef  # noqa: E402

# B063 F004: the §8 quality gate must cover the FULL candidate universe the
# real-data strategy selects from (the wide 26-name set the data_refresh job
# pulls), not a 7-name sample — single source of truth = the refresh universe.
_DEFAULT_UNIVERSE = CN_HK_UNIVERSE
_HISTORY_START = "2018-01-01"


def _import_optional(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _akshare_bars(
    akshare: Any, ref: SymbolRef, start: str, end: str, adjust: str
) -> list[PriceBar]:
    try:
        if ref.market == "HK":
            frame = akshare.stock_hk_hist(
                symbol=ref.code.zfill(5),
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
        else:
            frame = akshare.stock_zh_a_hist(
                symbol=ref.code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
    except Exception:
        return []
    if frame is None:
        return []
    try:
        columns = [str(c) for c in frame.columns]
        records: list[dict[str, Any]] = frame.to_dict("records")
    except Exception:
        return []
    return bars_from_records(records, columns, ref.canonical)


def _baostock_bars(baostock: Any, ref: SymbolRef, start: str, end: str) -> list[PriceBar]:
    if ref.market != "CN":
        return []
    prefix = "sh" if ref.canonical.endswith(".SH") else "sz"
    try:
        baostock.login()
    except Exception:
        return []
    try:
        result = baostock.query_history_k_data_plus(
            f"{prefix}.{ref.code}",
            "date,open,high,low,close,volume",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="2",
        )
        if getattr(result, "error_code", "0") != "0":
            return []
        columns = list(result.fields)
        records: list[dict[str, Any]] = []
        while result.next():
            records.append(dict(zip(columns, result.get_row_data(), strict=False)))
    except Exception:
        return []
    finally:
        with contextlib.suppress(Exception):
            baostock.logout()
    return bars_from_records(records, columns, ref.canonical)


def run(symbols: tuple[str, ...], history_start: str) -> dict[str, Any]:
    started = _now()
    akshare = _import_optional("akshare")
    baostock = _import_optional("baostock")
    end_ymd = _ymd(started)
    start_ymd = history_start.replace("-", "")

    reports: list[dict[str, Any]] = []
    for symbol in symbols:
        ref = SymbolRef.parse(symbol)
        qfq = _akshare_bars(akshare, ref, start_ymd, end_ymd, "qfq") if akshare else []
        raw = _akshare_bars(akshare, ref, start_ymd, end_ymd, "") if akshare else []
        cross = (
            _baostock_bars(baostock, ref, to_iso(_parse_ymd(start_ymd)), to_iso(started))
            if baostock and ref.market == "CN"
            else []
        )
        report = assess_symbol(
            symbol,
            qfq_bars=qfq,
            raw_bars=raw or None,
            cross_source_bars=cross or None,
        )
        reports.append(dataclasses.asdict(report))

    return {
        "tool": "ashare_quality_check",
        "feature": "B062-F003",
        "run_started_at": started.isoformat(),
        "libraries": {
            "akshare": akshare is not None,
            "baostock": baostock is not None,
        },
        "history_start": history_start,
        "reports": reports,
    }


def _now() -> datetime:
    return datetime.now(UTC)


def _ymd(stamp: datetime) -> str:
    return stamp.strftime("%Y%m%d")


def _parse_ymd(ymd: str) -> date:
    return datetime.strptime(ymd, "%Y%m%d").replace(tzinfo=UTC).date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=None, help="Comma list (default: candidate universe).")
    parser.add_argument("--history-start", default=_HISTORY_START, help="YYYY-MM-DD history start.")
    parser.add_argument("--out", default=None, help="Optional path to write the JSON report.")
    args = parser.parse_args(argv)

    symbols = (
        tuple(s.strip() for s in args.symbols.split(",") if s.strip())
        if args.symbols
        else _DEFAULT_UNIVERSE
    )
    report = run(symbols, args.history_start)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.out:
        try:
            Path(args.out).write_text(serialized + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"warning: could not write --out: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
