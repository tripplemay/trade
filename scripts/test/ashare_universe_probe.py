#!/usr/bin/env python
"""B065 F001 §23 — A-share point-in-time universe data-source reachability probe.

NOT product code. A spike tool answering the single §23 (framework v0.9.45) hard
prerequisite for B065 F001: **can akshare fetch the HISTORICAL market cap +
turnover a point-in-time universe builder needs, and which bulk-snapshot
endpoint (if any) can discover the wide superset?**

akshare routes different data through different hosts with different
reachability (B062/B064 lesson: the eastmoney *push* hosts — ``*.push2*`` —
read-time-out / SSL-fail from some networks while the eastmoney *finance* hosts
and baidu hosts answer). So every candidate must be **run for real** before the
builder is built against it.

This probe runs each candidate in an isolated subprocess with a hard wall-clock
timeout (a hung socket is killed, not waited on) and prints one structured JSON
document so a human / Codex can map the real columns + reachability.

Findings (local dev box, 2026-06-18 — captured in the
``workbench_api.data_refresh.cn_universe`` module docstring; Codex re-runs this
on the prod VM for F004):

* ``stock_value_em(600519)`` — ✅ REACHABLE: ~2050 daily rows, columns
  ``数据日期 / 当日收盘价 / 总市值 / 流通市值 / 总股本 / PE(TTM) / 市净率 / …``
  from 2018 to today (raw CNY). This IS the point-in-time historical market-cap
  source (eastmoney finance host, reachable local + VM).
* turnover (成交额) — derived offline as ``volume × close`` from the unified
  prices CSV the refresh already writes (no extra endpoint; spec §3 F001 proxy).
* ``stock_zh_a_hist`` (prices, ``push2his`` host) — SSL-fails locally but works
  on the prod VM (B061 lookup verified) → the prices CSV carries volume there.
* ``stock_zh_a_spot_em`` / ``stock_sh_a_spot_em`` (``push2`` hosts) +
  ``stock_info_a_code_name`` (szse.cn) — bulk-superset-discovery candidates;
  SSL-fail locally → discovery is BEST-EFFORT and degrades to the curated seed.

HARD BOUNDARY: databases only (akshare). Never a broker SDK.

Usage::

    python scripts/test/ashare_universe_probe.py
    python scripts/test/ashare_universe_probe.py --timeout 60 --out probe.json --label vm
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
import traceback
from typing import Any

# Representative liquid A-share: 贵州茅台.
CN_SYMBOL_6 = "600519"

# (label, module-fn-name, args, kwargs). Each runs in its own subprocess so a
# hung host never blocks the rest of the sweep.
CANDIDATES: list[tuple[str, str, list[Any], dict[str, Any]]] = [
    # --- historical market cap (THE point-in-time mcap source) ---
    ("hist_mcap.stock_value_em", "stock_value_em", [], {"symbol": CN_SYMBOL_6}),
    # --- historical price/volume (turnover source on the VM; push2his host) ---
    (
        "hist_px.stock_zh_a_hist",
        "stock_zh_a_hist",
        [],
        {"symbol": CN_SYMBOL_6, "period": "daily", "adjust": "qfq"},
    ),
    # --- bulk superset discovery (current top-N liquid; push2 / szse hosts) ---
    ("superset.stock_zh_a_spot_em", "stock_zh_a_spot_em", [], {}),
    ("superset.stock_sh_a_spot_em", "stock_sh_a_spot_em", [], {}),
    ("superset.stock_info_a_code_name", "stock_info_a_code_name", [], {}),
]


def _describe(result: Any) -> dict[str, Any]:
    """Best-effort shape description of an akshare return (DataFrame or other)."""
    info: dict[str, Any] = {"py_type": type(result).__name__}
    if hasattr(result, "columns") and hasattr(result, "to_dict"):
        try:
            info["row_count"] = int(len(result))
            info["columns"] = [str(c) for c in result.columns]
            head = result.head(2).to_dict("records")
            info["head"] = [{str(k): _safe(v) for k, v in r.items()} for r in head]
            tail = result.tail(1).to_dict("records")
            info["tail"] = [{str(k): _safe(v) for k, v in r.items()} for r in tail]
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
            out = {"ok": False, "error_class": "AttributeError", "error": f"no {fn_name}"}
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
    parser = argparse.ArgumentParser(description="B065 F001 §23 A-share universe data probe")
    parser.add_argument("--timeout", type=float, default=45.0, help="per-candidate wall-clock s")
    parser.add_argument("--out", type=str, default=None, help="also write JSON to this path")
    parser.add_argument("--label", type=str, default="local", help="run label (env/timeslot)")
    cli = parser.parse_args()

    results = [
        probe_one(label, fn, args, kwargs, cli.timeout)
        for label, fn, args, kwargs in CANDIDATES
    ]
    doc = {
        "probe": "b065_ashare_universe",
        "run_label": cli.label,
        "per_candidate_timeout_s": cli.timeout,
        "cn_symbol": CN_SYMBOL_6,
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
