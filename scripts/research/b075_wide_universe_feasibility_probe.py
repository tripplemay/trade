#!/usr/bin/env python
"""B075 F001 §23 — wide A-share universe production-feasibility probe.

NOT product code. A spike tool answering the single hard prerequisite for the
whole B075 batch (spec §0 / §2 F001): **at what N can the production data
pipeline actually refresh a wide A-share universe on the prod VM?** The batch
target is top ~1500, but it is *feasibility-gated* — the real N is decided by
this VM measurement, and if 1500 is not reliably refreshable we honestly fall
back to the largest feasible N (no silent cap, B070 precedent).

It measures the four production cost centres, **reusing the real production
loaders / discovery** (not synthetic stand-ins), so the probe doubles as a live
validation of the ungated wide-universe code path:

    Phase A — bulk superset discovery via ``discover_ashare_superset`` with the
              sina fallback enabled (the §23 VM-reachable bulk endpoint; the
              eastmoney push host SSL-/Connection-fails on the VM). Records the
              provenance (``sina_spot`` on the VM, ``seed`` if all bulk endpoints
              fail) + the discovered count + wall-clock.
    Phase B — per-name daily PRICE fetch (``CnHkPricesLoader``, the daily 命门)
              over a random sample with the production 5-year lookback. The daily
              refresh re-fetches the full window per symbol every run, so the
              serial per-name time × N is the real daily wall-clock.
    Phase C — per-name historical MARKET-CAP fetch (``CnMarketCapLoader`` /
              ``stock_value_em``) — the universe-build (ranking) cost.
    Phase D — per-name CAS FUNDAMENTALS fetch (``CnFundamentalsLoader`` /
              ``stock_financial_abstract``) — the quality-variant cost, which the
              batch decouples to a low-frequency (weekly/monthly) schedule.

It then extrapolates each per-name cost to the target N and emits a mechanical
GO / PARTIAL verdict + the largest feasible N inside a wall-clock budget.

HARD BOUNDARY: databases only (akshare). Never a broker SDK. Bounded: it samples
a few dozen names and extrapolates — it never fetches all N (that IS the daily
job). Run on the VM from the deployed backend so ``workbench_api`` imports
resolve::

    cd /srv/workbench/current/backend
    /opt/workbench/.venv/bin/python /tmp/b075_wide_universe_feasibility_probe.py \
        --out /tmp/b075_probe_vm.json --label vm

Usage flags::

    --target-n        the batch goal N to extrapolate to (default 1500)
    --sample          random sample size per cost centre (default 18)
    --lookback-days   price-fetch window (default 1825 = the production 5y)
    --price-budget-min daily price-fetch wall-clock budget for the GO gate (default 90)
    --seed            RNG seed for the deterministic sample (default 20260622)
"""

from __future__ import annotations

import argparse
import json
import random
import time
import traceback
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

# Production code under test (reused, not re-implemented) — these imports resolve
# only from the deployed backend tree (cd /srv/workbench/current/backend).
from workbench_api.data_refresh.cn_fundamentals import CnFundamentalsLoader
from workbench_api.data_refresh.cn_hk_prices import CnHkPricesLoader
from workbench_api.data_refresh.cn_marketcap import (
    CnMarketCapLoader,
    discover_ashare_superset,
)

# A small, known-liquid fallback sample so the per-name phases still produce a
# signal if discovery degrades to the seed (off-VM / all bulk endpoints down).
_FALLBACK_SAMPLE: tuple[str, ...] = (
    "600519.SH",
    "601318.SH",
    "600036.SH",
    "000858.SZ",
    "000333.SZ",
    "300750.SZ",
    "002594.SZ",
    "601012.SH",
    "600276.SH",
    "300760.SZ",
)


def _err(stage: str, exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "stage": stage,
        "error_class": type(exc).__name__,
        "error": str(exc)[:400],
        "traceback_tail": traceback.format_exc().splitlines()[-3:],
    }


def _timed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.monotonic()
    out = fn(*args, **kwargs)
    return out, round(time.monotonic() - start, 3)


def probe_discovery(target_n: int) -> dict[str, Any]:
    """Phase A: time the real ungated bulk discovery (sina fallback enabled)."""

    out: dict[str, Any] = {"phase": "A_bulk_discovery", "target_n": target_n}
    try:
        (symbols, provenance), elapsed = _timed(
            discover_ashare_superset, top_n=target_n, allow_sina_fallback=True
        )
        out.update(
            {
                "ok": True,
                "provenance": provenance,
                "discovered": len(symbols),
                "elapsed_s": elapsed,
                "sample_head": list(symbols[:8]),
                "vm_reachable_bulk": provenance in {"bulk_spot", "sina_spot"},
            }
        )
        out["symbols"] = list(symbols)
    except Exception as exc:  # noqa: BLE001
        out.update(_err("discover_ashare_superset", exc))
        out["symbols"] = list(_FALLBACK_SAMPLE)
    return out


def _per_name_phase(
    name: str,
    fetch: Callable[[str], int],
    sample: list[str],
) -> dict[str, Any]:
    """Run ``fetch`` over ``sample``, timing each + counting empties/errors."""

    out: dict[str, Any] = {"phase": name, "sample_n": len(sample), "per_name": []}
    ok = 0
    empty = 0
    errors = 0
    total_s = 0.0
    rows_total = 0
    for ticker in sample:
        try:
            rows, elapsed = _timed(fetch, ticker)
        except Exception as exc:  # noqa: BLE001 — best-effort per name (production behaviour)
            errors += 1
            out["per_name"].append({"ticker": ticker, **_err(name, exc)})
            continue
        total_s += elapsed
        rows_total += rows
        if rows > 0:
            ok += 1
        else:
            empty += 1
        out["per_name"].append(
            {"ticker": ticker, "ok": rows > 0, "rows": rows, "elapsed_s": elapsed}
        )
    attempted = len(sample)
    # Mean over names that returned at all (ok or empty, i.e. no exception): the
    # serial daily loop pays this per name regardless of payload size.
    timed_names = ok + empty
    mean_s = round(total_s / timed_names, 3) if timed_names else None
    out.update(
        {
            "attempted": attempted,
            "ok": ok,
            "empty": empty,
            "errors": errors,
            "success_rate": round(ok / attempted, 3) if attempted else 0.0,
            "mean_s_per_name": mean_s,
            "rows_total": rows_total,
            "total_s": round(total_s, 2),
        }
    )
    return out


def _extrapolate(mean_s: float | None, n: int) -> dict[str, Any]:
    if mean_s is None:
        return {"feasible": False, "reason": "no successful timing sample"}
    serial_s = mean_s * n
    return {
        "n": n,
        "mean_s_per_name": mean_s,
        "est_serial_s": round(serial_s, 1),
        "est_serial_min": round(serial_s / 60, 1),
    }


def _largest_feasible_n(mean_s: float | None, budget_min: float) -> int | None:
    if not mean_s or mean_s <= 0:
        return None
    return int((budget_min * 60) / mean_s)


def judge(
    discovery: dict[str, Any],
    prices: dict[str, Any],
    marketcap: dict[str, Any],
    fundamentals: dict[str, Any],
    *,
    target_n: int,
    price_budget_min: float,
) -> dict[str, Any]:
    """Mechanical GO / PARTIAL / NO-GO from the gathered evidence (spec §0)."""

    bulk_ok = bool(discovery.get("vm_reachable_bulk")) and discovery.get(
        "discovered", 0
    ) >= target_n
    price_mean = prices.get("mean_s_per_name")
    price_success = prices.get("success_rate", 0.0)
    price_est = _extrapolate(price_mean, target_n)
    daily_fits = bool(price_est.get("est_serial_min", 1e9) <= price_budget_min)
    feasible_n_by_price = _largest_feasible_n(price_mean, price_budget_min)

    # The daily 命门 is the price fetch; the universe-build (mcap) + fundamentals
    # run on their own (quarterly-relevant / low-freq) schedules, so they inform
    # the schedule but do not gate the daily GO.
    if bulk_ok and daily_fits and price_success >= 0.9:
        verdict = "GO"
        feasible_n = target_n
        reason = (
            f"Bulk discovery reachable ({discovery.get('provenance')}, "
            f"{discovery.get('discovered')} names) AND daily price refresh of "
            f"N={target_n} fits the {price_budget_min}min budget "
            f"(~{price_est.get('est_serial_min')}min, success {price_success})."
        )
    elif bulk_ok and feasible_n_by_price and feasible_n_by_price > 0:
        verdict = "PARTIAL"
        feasible_n = min(target_n, feasible_n_by_price)
        reason = (
            f"Bulk discovery reachable but daily price refresh of N={target_n} "
            f"exceeds the {price_budget_min}min budget "
            f"(~{price_est.get('est_serial_min')}min). Honest fallback: largest "
            f"feasible N inside budget ≈ {feasible_n} (no silent cap)."
        )
    else:
        verdict = "NO-GO"
        feasible_n = 0
        reason = (
            "Bulk discovery unreachable on the VM (degraded to seed) OR price "
            "fetch sample failed — wide universe not feasible from free sources; "
            "stays at the curated seed until a reachable bulk endpoint exists."
        )

    return {
        "verdict": verdict,
        "feasible_n": feasible_n,
        "target_n": target_n,
        "reason": reason,
        "signals": {
            "bulk_discovery_ok": bulk_ok,
            "bulk_provenance": discovery.get("provenance"),
            "bulk_discovered": discovery.get("discovered"),
            "daily_price_fits_budget": daily_fits,
            "price_success_rate": price_success,
            "price_est_serial_min_at_target": price_est.get("est_serial_min"),
            "largest_feasible_n_by_price_budget": feasible_n_by_price,
            "marketcap_est_serial_min_at_target": _extrapolate(
                marketcap.get("mean_s_per_name"), target_n
            ).get("est_serial_min"),
            "fundamentals_est_serial_min_at_target": _extrapolate(
                fundamentals.get("mean_s_per_name"), target_n
            ).get("est_serial_min"),
        },
        "extrapolation": {
            "prices_daily": price_est,
            "marketcap_build": _extrapolate(marketcap.get("mean_s_per_name"), target_n),
            "fundamentals_lowfreq": _extrapolate(
                fundamentals.get("mean_s_per_name"), target_n
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B075 F001 §23 wide A-share universe feasibility probe"
    )
    parser.add_argument("--target-n", type=int, default=1500)
    parser.add_argument("--sample", type=int, default=18)
    parser.add_argument("--lookback-days", type=int, default=1825)
    parser.add_argument("--price-budget-min", type=float, default=90.0)
    parser.add_argument("--seed", type=int, default=20260622)
    parser.add_argument("--out", type=str, default=None, help="also write JSON here")
    parser.add_argument("--label", type=str, default="local", help="run label (env)")
    cli = parser.parse_args()

    to_date = date.today()
    from_date = to_date - timedelta(days=max(1, cli.lookback_days))

    discovery = probe_discovery(cli.target_n)
    universe = discovery.pop("symbols", list(_FALLBACK_SAMPLE))

    rng = random.Random(cli.seed)
    pool = universe if len(universe) >= cli.sample else list(_FALLBACK_SAMPLE)
    sample = rng.sample(pool, min(cli.sample, len(pool)))

    price_loader = CnHkPricesLoader()
    mcap_loader = CnMarketCapLoader()
    fund_loader = CnFundamentalsLoader()

    prices = _per_name_phase(
        "B_prices_daily",
        lambda t: len(price_loader.fetch_daily_bars(t, from_date, to_date)),
        sample,
    )
    marketcap = _per_name_phase(
        "C_marketcap_build",
        lambda t: len(mcap_loader.fetch_market_cap_history(t, from_date, to_date)),
        sample,
    )
    fundamentals = _per_name_phase(
        "D_fundamentals_lowfreq",
        lambda t: len(fund_loader.fetch_fundamentals_rows(t, from_date, to_date)),
        sample,
    )

    doc = {
        "probe": "b075_wide_universe_feasibility",
        "run_label": cli.label,
        "params": {
            "target_n": cli.target_n,
            "sample": cli.sample,
            "lookback_days": cli.lookback_days,
            "price_budget_min": cli.price_budget_min,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
        "phase_a_discovery": discovery,
        "phase_b_prices_daily": prices,
        "phase_c_marketcap_build": marketcap,
        "phase_d_fundamentals_lowfreq": fundamentals,
        "judgment": judge(
            discovery,
            prices,
            marketcap,
            fundamentals,
            target_n=cli.target_n,
            price_budget_min=cli.price_budget_min,
        ),
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if cli.out:
        with open(cli.out, "w", encoding="utf-8") as handle:
            handle.write(text)


if __name__ == "__main__":
    main()
