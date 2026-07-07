#!/usr/bin/env python
"""B102 — fetch qfq prices for the SMALL-CAP (non-liquid) insider-buying sleeve.

B101 tested the insider-BUYING signal (大股东/高管增持) only on the 998/3233 (30.9%)
insider names that happened to sit in the liquid B070 survivorship-free cache. That cache
is LIQUIDITY-TILTED (B070 selected it on size/liquidity/quality), so the remaining ~2235
insider names — SMALL-CAP / illiquid, exactly where A-share insider / smart-money signals
plausibly CONCENTRATE — were never priced. This script closes that gap.

What it does:
  1. Recompute the small-cap universe = insider event codes NOT in the B101 liquid price
     panel (data/research/b101_insider/prices.pkl).
  2. Restrict to a SAMPLING FRAME = small-cap codes with >=1 announcement in the price
     window (>= 2017-06-01) so no fetch is wasted on names with no scoreable cohort. This
     frame is defined purely by the EXISTENCE of an in-window event, NOT by any outcome /
     return — so the sample stays SIGNAL-INDEPENDENT.
  3. Take a DETERMINISTIC seed-102 random sample of --sample-size names (default 800, in
     the requested 600-1000 band). random.Random(102).sample over the SORTED frame ->
     fully reproducible, and random (not outcome-selected) so it does not cherry-pick.
  4. Fetch qfq daily adj_close per name via ak.stock_zh_a_daily(symbol='sh/sz'+code,
     adjust='qfq'), applying the B092/B094 floor+spike guard (pre-2017 qfq corruption).

★ SURVIVORSHIP CAVEAT (fetch-level): ak.stock_zh_a_daily returns only CURRENTLY-listed
  names. DELISTED small-caps are simply absent from the feed, so they can never enter the
  sample. Small-caps delist more often than large-caps, so this is an UPWARD survivorship
  bias — any edge measured downstream is an OPTIMISTIC UPPER BOUND. Disclosed in the IC
  script + report; unfixable with free data.

research-only / no broker / no real money / no production change / no paid data.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import socket
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_B101_DIR = Path("data/research/b101_insider")
_EVENTS_CSV = _B101_DIR / "insider_events.csv"
_B101_PRICES = _B101_DIR / "prices.pkl"

_OUT_DIR = Path("data/research/b102_smallcap")
_PRICES_PKL = _OUT_DIR / "prices.pkl"
_SAMPLE_JSON = _OUT_DIR / "sample.json"
_COVERAGE_JSON = _OUT_DIR / "coverage.json"

_SEED = 102
_DEFAULT_SAMPLE = 800          # in the requested 600-1000 band
_FRAME_ANNOUNCE_MIN = "2017-06-01"  # in-window inclusion floor (price panel starts 2018)
_PRICE_START = "20180101"      # match the B101 liquid window for comparability
_PRICE_END = "20260707"

# B092/B094 floor+spike guard (pre-2017 qfq split-adjust corruption).
_PRICE_FLOOR = 0.01
_PRICE_SPIKE = 5.0


def small_cap_frame(events_csv: Path, liquid_codes: set[str],
                    announce_min: str) -> list[str]:
    """Sorted list of small-cap insider codes (NOT in the liquid panel) that have >=1
    announcement on/after ``announce_min``. Deterministic; outcome-independent."""
    import pandas as pd

    ev = pd.read_csv(events_csv, dtype={"code": str})
    ev["code"] = ev["code"].str.extract(r"(\d{6})")[0]
    ev["announce_date"] = pd.to_datetime(ev["announce_date"], errors="coerce")
    ev = ev.dropna(subset=["code", "announce_date"])
    small = ev[~ev["code"].isin(liquid_codes)]
    in_window = small[small["announce_date"] >= pd.Timestamp(announce_min)]
    return sorted(in_window["code"].unique())


def deterministic_sample(frame: list[str], size: int, seed: int) -> list[str]:
    """Reproducible seed-N random sample over the SORTED frame. Returns the full frame
    (sorted) when it is already <= size."""
    ordered = sorted(frame)
    if len(ordered) <= size:
        return ordered
    rng = random.Random(seed)
    return sorted(rng.sample(ordered, size))


def code_to_symbol(code: str) -> str | None:
    """Bare 6-digit code -> stock_zh_a_daily symbol ('sh'/'sz' + code)."""
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    return f"{'sh' if digits[0] in {'6', '9'} else 'sz'}{digits}"


def guard_price(prev: float | None, close: float | None) -> float | None:
    """B092/B094 floor+spike guard. Drop non-positive / sub-floor bars and >5x single-bar
    jumps vs the previous KEPT close (corrupted qfq split-adjust)."""
    if close is None or close != close or close <= _PRICE_FLOOR:  # noqa: PLR0124 NaN
        return None
    if prev is not None and prev > 0:
        ratio = close / prev
        if ratio > _PRICE_SPIKE or ratio < 1.0 / _PRICE_SPIKE:
            return None
    return close


def _coerce_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def fetch_one(akshare: Any, code: str, start: str, end: str) -> list[tuple[str, str, float]]:
    """qfq daily adj_close for one code, guarded. Returns [(date, code, close), ...].
    Best-effort: any akshare error -> empty (skip the name, never fatal)."""
    symbol = code_to_symbol(code)
    if symbol is None:
        return []
    try:
        frame = akshare.stock_zh_a_daily(
            symbol=symbol, adjust="qfq", start_date=start, end_date=end)
    except Exception as exc:  # noqa: BLE001 — best-effort per name
        logger.debug("fetch %s failed: %r", code, exc)
        return []
    if frame is None or not len(frame):
        return []
    rows: list[tuple[str, str, float]] = []
    prev: float | None = None
    for rec in frame.to_dict("records"):
        raw_date = rec.get("date")
        close = _coerce_float(rec.get("close"))
        kept = guard_price(prev, close)
        if kept is None:
            continue
        rows.append((str(raw_date)[:10], code, round(kept, 4)))
        prev = kept
    return rows


def _to_frame(all_rows: list[tuple[str, str, float]]) -> Any:
    import pandas as pd

    df = pd.DataFrame(all_rows, columns=["date", "code", "adj_close"])
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["code", "date"]).reset_index(drop=True)
    return df


def fetch_prices(akshare: Any, codes: list[str], start: str, end: str,
                 pause: float, checkpoint_every: int = 25) -> Any:
    """Fetch every sampled code -> long-form DataFrame(date, code, adj_close).

    CHECKPOINTS the accumulated panel to _PRICES_PKL every ``checkpoint_every`` names, so
    a mid-run stop / network hang leaves a USABLE partial panel (the first-K of the sorted
    deterministic sample) rather than nothing. Per-name errors are already swallowed in
    fetch_one; combined with a process-wide socket timeout (set in main) a hung HTTP call
    fails fast and the loop moves on instead of blocking forever."""
    all_rows: list[tuple[str, str, float]] = []
    ok = 0
    for i, code in enumerate(codes, 1):
        rows = fetch_one(akshare, code, start, end)
        if rows:
            ok += 1
            all_rows.extend(rows)
        if i % checkpoint_every == 0 or i == len(codes):
            _to_frame(all_rows).to_pickle(_PRICES_PKL)
            logger.info("prices: %d/%d fetched, %d ok, %d bars (checkpoint)",
                        i, len(codes), ok, len(all_rows))
        time.sleep(pause)
    return _to_frame(all_rows)


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="B102 small-cap insider price fetch")
    ap.add_argument("--sample-size", type=int, default=_DEFAULT_SAMPLE)
    ap.add_argument("--seed", type=int, default=_SEED)
    ap.add_argument("--announce-min", default=_FRAME_ANNOUNCE_MIN)
    ap.add_argument("--price-start", default=_PRICE_START)
    ap.add_argument("--price-end", default=_PRICE_END)
    ap.add_argument("--pause", type=float, default=0.2)
    ap.add_argument("--timeout", type=float, default=20.0,
                    help="socket timeout (s) so a hung akshare call fails fast")
    ap.add_argument("--limit", type=int, default=0, help="debug: cap fetched names")
    args = ap.parse_args(argv)

    # Break hung HTTP calls: without this a single stalled akshare request blocks the
    # whole loop indefinitely. A timed-out call raises -> fetch_one swallows -> skip name.
    socket.setdefaulttimeout(args.timeout)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    liquid = set(pd.read_pickle(_B101_PRICES)["code"].astype(str).unique())
    frame = small_cap_frame(_EVENTS_CSV, liquid, args.announce_min)
    sample = deterministic_sample(frame, args.sample_size, args.seed)
    logger.info("small-cap frame=%d, sampled=%d (seed=%d)",
                len(frame), len(sample), args.seed)

    fetch_list = sample[: args.limit] if args.limit else sample
    import akshare as ak
    prices = fetch_prices(ak, fetch_list, args.price_start, args.price_end, args.pause)
    prices.to_pickle(_PRICES_PKL)

    fetched_codes = set(prices["code"].unique()) if len(prices) else set()

    # Event coverage: how many small-cap events fall on the fetched, in-window names.
    ev = pd.read_csv(_EVENTS_CSV, dtype={"code": str})
    ev["code"] = ev["code"].str.extract(r"(\d{6})")[0]
    ev["announce_date"] = pd.to_datetime(ev["announce_date"], errors="coerce")
    ev = ev.dropna(subset=["code", "announce_date"])
    # Denominator = small-cap (non-liquid) events in the price window ONLY, so the
    # coverage % is measured against the small-cap sleeve, not the full insider feed.
    ev_win = ev[(ev["announce_date"] >= pd.Timestamp(args.announce_min))
                & (~ev["code"].isin(liquid))]
    ev_covered = ev_win[ev_win["code"].isin(fetched_codes)]

    sample_meta = {
        "seed": args.seed,
        "sample_size_requested": args.sample_size,
        "frame_size": len(frame),
        "sample_size_actual": len(sample),
        "sample_codes": sample,
        "signal_independent": True,
        "frame_rule": (
            f"small-cap insider codes (NOT in B101 liquid panel) with >=1 announcement "
            f">= {args.announce_min}; random seed-{args.seed} sample over the sorted frame"),
    }
    with open(_SAMPLE_JSON, "w") as fh:
        json.dump(sample_meta, fh, ensure_ascii=False, indent=2)

    coverage = {
        "universe": "SMALL-CAP insider names (non-B070-liquid sleeve)",
        "small_cap_codes_total": int(len(set(ev["code"]) - liquid)),
        "small_cap_frame_in_window": len(frame),
        "sampled_names": len(sample),
        "fetched_ok_names": int(len(fetched_codes)),
        "fetch_success_pct": round(100 * len(fetched_codes) / max(len(fetch_list), 1), 1),
        "price_rows": int(len(prices)),
        "price_date_min": str(prices["date"].min().date()) if len(prices) else None,
        "price_date_max": str(prices["date"].max().date()) if len(prices) else None,
        "smallcap_events_in_window": int(len(ev_win)),
        "smallcap_events_covered_by_fetch": int(len(ev_covered)),
        "event_coverage_pct_of_window": round(
            100 * len(ev_covered) / max(len(ev_win), 1), 1),
        "price_start": args.price_start,
        "price_end": args.price_end,
        "guard": f"floor={_PRICE_FLOOR} spike={_PRICE_SPIKE}x (B092/B094)",
        "survivorship_note": (
            "ak.stock_zh_a_daily returns only CURRENTLY-listed names; delisted small-caps "
            "are absent -> UPWARD survivorship bias, edge is an optimistic upper bound"),
    }
    with open(_COVERAGE_JSON, "w") as fh:
        json.dump(coverage, fh, ensure_ascii=False, indent=2)
    logger.info("coverage -> %s", json.dumps(coverage, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
