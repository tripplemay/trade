#!/usr/bin/env python
"""B064 §23 — CN/HK fundamentals + news akshare endpoint reachability probe.

NOT product code. A spike tool that answers the single §23 (framework v0.9.45)
hard prerequisite for B064: **which akshare fundamentals / individual-news
functions are actually reachable and what real shape / fields do they return?**

akshare routes different data (price vs fundamentals vs news) through different
functions, hosts and reachability — B062's HK price endpoint
``stock_hk_hist`` (eastmoney push host) read-timed-out reproducibly while the
A-share eastmoney host worked. So the fundamentals / news functions must be
**run for real** (not just mocked) before any provider is built against them.

This probe:

* lives under ``scripts/test/`` (excluded from CI collection — ``testpaths =
  ["tests"]``), imports ``akshare`` lazily, and is imported by no product code;
* runs every candidate function in an **isolated subprocess with a hard wall
  clock timeout** (a hung eastmoney/sina socket is killed, not waited on), so
  one unreachable endpoint never blocks the rest of the sweep;
* HARD BOUNDARY: **databases only** (akshare). Never a broker SDK.

Output: one structured JSON document on stdout (and optionally ``--out``) — for
each candidate: ``ok`` / latency / error-class / returned columns (or dict
keys) / a small sample so a human can map the real fields. Codex re-runs this
on the production VM for F004 to confirm the prod-host reachability conclusion.

Usage::

    python scripts/test/cn_hk_fundamentals_news_probe.py
    python scripts/test/cn_hk_fundamentals_news_probe.py --timeout 60 --out probe.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
import traceback
from typing import Any

# Representative symbols (same as the price probes): 贵州茅台 / 腾讯控股.
CN_SYMBOL_6 = "600519"  # akshare A-share 6-digit code
HK_SYMBOL_5 = "00700"  # akshare HK 5-digit zero-padded code

# (label, module-fn-name, args, kwargs) — every candidate akshare fn for the
# four data needs. Each runs in its own subprocess so a hang is contained.
CANDIDATES: list[tuple[str, str, list[Any], dict[str, Any]]] = [
    # --- A-share fundamentals ---
    ("cn_fund.stock_individual_info_em", "stock_individual_info_em", [], {"symbol": CN_SYMBOL_6}),
    ("cn_fund.stock_financial_abstract", "stock_financial_abstract", [], {"symbol": CN_SYMBOL_6}),
    ("cn_fund.stock_a_indicator_lg", "stock_a_indicator_lg", [], {"symbol": CN_SYMBOL_6}),
    (
        "cn_fund.stock_financial_analysis_indicator",
        "stock_financial_analysis_indicator",
        [],
        {"symbol": CN_SYMBOL_6, "start_year": "2023"},
    ),
    # --- HK fundamentals (biggest unknown, B062 HK-host lesson) ---
    ("hk_fund.stock_hk_spot_em", "stock_hk_spot_em", [], {}),
    (
        "hk_fund.stock_financial_hk_analysis_indicator_em",
        "stock_financial_hk_analysis_indicator_em",
        [],
        {"symbol": HK_SYMBOL_5, "indicator": "年度"},
    ),
    (
        "hk_fund.stock_hk_indicator_eniu",
        "stock_hk_indicator_eniu",
        [],
        {"symbol": f"hk{HK_SYMBOL_5}", "indicator": "市盈率"},
    ),
    # --- A-share individual news ---
    ("cn_news.stock_news_em", "stock_news_em", [], {"symbol": CN_SYMBOL_6}),
    # --- HK individual news (candidate uncertain; try the same eastmoney fn) ---
    ("hk_news.stock_news_em", "stock_news_em", [], {"symbol": HK_SYMBOL_5}),
]


def _describe(result: Any) -> dict[str, Any]:
    """Best-effort shape description of an akshare return (DataFrame or other)."""
    info: dict[str, Any] = {"py_type": type(result).__name__}
    # pandas DataFrame
    if hasattr(result, "columns") and hasattr(result, "to_dict"):
        try:
            info["row_count"] = int(len(result))
            info["columns"] = [str(c) for c in result.columns]
            info["dtypes"] = {str(c): str(result[c].dtype) for c in result.columns}
            head = result.head(3).to_dict("records")
            # Stringify to keep JSON-serialisable (Timestamps, numpy types).
            info["sample"] = [{str(k): _safe(v) for k, v in r.items()} for r in head]
        except Exception as exc:  # noqa: BLE001
            info["describe_error"] = repr(exc)
    elif isinstance(result, (list, tuple)):
        info["row_count"] = len(result)
        info["sample"] = [_safe(x) for x in list(result)[:3]]
    else:
        info["sample"] = _safe(result)
    return info


def _safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _run_candidate(fn_name: str, args: list[Any], kwargs: dict[str, Any], q: mp.Queue) -> None:  # type: ignore[type-arg]
    """Subprocess worker: import akshare, call one fn, push a result dict."""
    out: dict[str, Any] = {}
    start = time.monotonic()
    try:
        import akshare as ak  # lazy, inside the child

        fn = getattr(ak, fn_name, None)
        if fn is None:
            out = {
                "ok": False,
                "error_class": "AttributeError",
                "error": f"akshare has no {fn_name}",
            }
        else:
            result = fn(*args, **kwargs)
            out = {"ok": True, "shape": _describe(result)}
    except Exception as exc:  # noqa: BLE001
        out = {
            "ok": False,
            "error_class": type(exc).__name__,
            "error": str(exc)[:500],
            "traceback_tail": traceback.format_exc().splitlines()[-3:],
        }
    out["elapsed_s"] = round(time.monotonic() - start, 2)
    q.put(out)


def probe_one(
    label: str, fn_name: str, args: list[Any], kwargs: dict[str, Any], timeout: float
) -> dict[str, Any]:
    """Run a candidate in an isolated process; kill + report on timeout."""
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()  # type: ignore[type-arg]
    proc = ctx.Process(target=_run_candidate, args=(fn_name, args, kwargs, q))
    started = time.monotonic()
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return {
            "label": label,
            "fn": fn_name,
            "kwargs": kwargs,
            "ok": False,
            "error_class": "TimeoutError",
            "error": f"no return within {timeout}s (host hang / geo-block)",
            "elapsed_s": round(time.monotonic() - started, 2),
        }
    try:
        result = q.get_nowait()
    except Exception:  # noqa: BLE001
        result = {"ok": False, "error_class": "NoResult", "error": "worker died without a result"}
    result.update({"label": label, "fn": fn_name, "kwargs": kwargs})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="B064 §23 CN/HK fundamentals+news probe")
    parser.add_argument(
        "--timeout", type=float, default=45.0, help="per-candidate wall-clock seconds"
    )
    parser.add_argument("--out", type=str, default=None, help="also write JSON to this path")
    parser.add_argument("--label", type=str, default="local", help="run label (env/timeslot)")
    cli = parser.parse_args()

    results = [
        probe_one(label, fn, args, kwargs, cli.timeout)
        for label, fn, args, kwargs in CANDIDATES
    ]
    doc = {
        "probe": "b064_cn_hk_fundamentals_news",
        "run_label": cli.label,
        "per_candidate_timeout_s": cli.timeout,
        "cn_symbol": CN_SYMBOL_6,
        "hk_symbol": HK_SYMBOL_5,
        "results": results,
        "summary": {
            "reachable": sorted(r["label"] for r in results if r.get("ok")),
            "unreachable": sorted(r["label"] for r in results if not r.get("ok")),
        },
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if cli.out:
        with open(cli.out, "w", encoding="utf-8") as handle:
            handle.write(text)


if __name__ == "__main__":
    main()
