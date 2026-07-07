#!/usr/bin/env python
"""B104 — EXPAND the LHB institutional-seat sample to pressure-test B103's finding.

B103 found the exact per-event institutional net-buy ¥ (``inst_buy_net``, summed over
"机构专用" seats) has a 5-day forward-return rank-IC of +0.205 (t=2.22) — BUT on only
232 price-covered pairs / 26 months, because B094 fetched per-event seat detail for only
800 of the 52k LHB events. The QUESTION B104 answers: does that +0.20 HOLD on a LARGER
free sample (a real signal) or DECAY (thin-sample noise)?

This script EXPANDS the seat sample. It reuses B094's existing 800 seats verbatim and
fetches per-event seats (``ak.stock_lhb_stock_detail_em``, "机构专用" net) for MANY MORE
events — a DETERMINISTIC seed-104 sample drawn from the PRICE-COVERED event universe
(so every new pair is usable for forward returns), target ~2500-4000 total.

★ Signal independence: the sample is a seed-104 shuffle of price-covered event keys —
  it is NOT selected on any outcome / signal value, so no selection bias is introduced.
★ Price-coverage first: we sample only events whose ticker has qfq price coverage in
  B094's prices.csv. This maximizes the number of USABLE (inst_buy_net, fwd-ret) pairs
  vs B103's 232 — the existing 800 were seed-94 sampled from ALL events (only 188 were
  price-covered), so the covered pool is largely un-fetched (~10.5k keys).
★ Throttle-safe: a socket default timeout makes a hung akshare call fail fast; each
  fetch is best-effort (failure logged + skipped, never fatal). We CHECKPOINT the
  accumulating seat file every ``--checkpoint`` events, and the run is RESUMABLE (an
  existing output file's keys are skipped), so partial progress is always usable. If the
  feed throttles, we cap to whatever completed and the IC step documents the achieved
  size honestly.

Output: ``data/research/b104_seats/seats_expanded.csv`` (gitignored) — the SAME schema as
B094's seats_sample.csv (event_date, ticker, youzi_buy_net, youzi_top_net_buyer,
inst_buy_net, n_buy_seats, jiedu_is_youzi), so ``b103_lhb_inst_ic.py`` / the B104 IC step
can read ``inst_buy_net`` directly. It contains the 800 existing rows PLUS the new ones.

research-only / no broker / no real money / no production change / no paid data.
The pure sample/parse core is unit-tested offline; the network fetch is best-effort.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import logging
import random
import socket
import sys
import time
from pathlib import Path
from typing import Any

# Reuse the VERIFIED B094 seat helpers (same directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from b094_youzi_fetch import (  # noqa: E402
    SEAT_HEADER,
    classify_branch,  # noqa: F401 — re-exported for tests
    code_to_ticker,
    is_youzi_jiedu,
    youzi_seat_nets,
)

logger = logging.getLogger(__name__)

DEFAULT_SEED = 104
DEFAULT_TARGET_TOTAL = 3500   # existing 800 + new; capped by feed availability
DEFAULT_CHECKPOINT = 100


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested offline).
# --------------------------------------------------------------------------- #
def load_price_covered_tickers(prices_csv: Path) -> set[str]:
    """Set of tickers that have >=1 qfq price bar (usable for forward returns)."""
    covered: set[str] = set()
    if not prices_csv.exists():
        return covered
    with prices_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("ticker", "")).strip()
            if ticker:
                covered.add(ticker)
    return covered


def load_seat_keys(seats_csv: Path) -> set[tuple[str, str]]:
    """Already-fetched (event_date, ticker) keys from an existing seats file."""
    keys: set[tuple[str, str]] = set()
    if not seats_csv.exists():
        return keys
    with seats_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            keys.add((str(row.get("event_date", "")).strip(),
                      str(row.get("ticker", "")).strip()))
    return keys


def load_seat_rows(seats_csv: Path) -> list[dict[str, str]]:
    """All rows of an existing seats file (for seeding the expanded output)."""
    if not seats_csv.exists():
        return []
    with seats_csv.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_events(events_csv: Path) -> list[dict[str, str]]:
    """Raw LHB event rows (event_date, code, ticker, name, jiedu, ...)."""
    with events_csv.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_seed_sample(
    events: list[dict[str, str]],
    covered_tickers: set[str],
    already_fetched: set[tuple[str, str]],
    *,
    target_new: int,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, str]]:
    """DETERMINISTIC seed-N sample of PRICE-COVERED, not-yet-fetched event keys.

    Dedupes events to unique (event_date, ticker) keys (a stock can appear on the LHB
    multiple times per day for different 上榜原因 — seats are per stock/date, so we fetch
    each key once), keeps only keys whose ticker has price coverage and that are not
    already fetched, sorts the keys for reproducibility, shuffles with ``Random(seed)``,
    and returns the first ``target_new`` event rows (one representative row per key).

    Signal-independent: the ordering depends only on the seed, never on any outcome."""
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in events:
        event_date = str(row.get("event_date", "")).strip()
        ticker = str(row.get("ticker", "")).strip()
        if not event_date or not ticker:
            continue
        key = (event_date, ticker)
        if ticker not in covered_tickers or key in already_fetched:
            continue
        by_key.setdefault(key, row)  # first occurrence is the representative
    keys = sorted(by_key)
    rng = random.Random(seed)
    rng.shuffle(keys)
    chosen = keys[: max(0, target_new)]
    return [by_key[k] for k in chosen]


def seat_row_from_buys(event: dict[str, str], buy_rows: list[dict[str, Any]]) -> list[Any]:
    """Build a seats_sample-schema row from an event + its top-5 buy seat records.

    ``inst_buy_net`` = sum of 净额 over "机构专用" seats (via B094's youzi_seat_nets)."""
    nets = youzi_seat_nets(buy_rows)
    return [
        event["event_date"],
        event["ticker"],
        round(nets["youzi"], 2),
        round(nets["youzi_top"], 2),
        round(nets["inst"], 2),
        len(buy_rows),
        int(is_youzi_jiedu(event.get("jiedu", ""))),
    ]


def event_code(event: dict[str, str]) -> str | None:
    """The 6-digit code for the seat-detail call (prefer 'code', else derive)."""
    code = "".join(ch for ch in str(event.get("code", "")) if ch.isdigit())
    if len(code) >= 6:
        return code[:6]
    ticker = code_to_ticker(event.get("ticker"))
    return ticker.split(".")[0] if ticker else None


# --------------------------------------------------------------------------- #
# Fetch (best-effort; never fatal; resumable + checkpointed).
# --------------------------------------------------------------------------- #
def _records(module: Any, fn_name: str, **kwargs: Any) -> list[dict[str, Any]]:
    fn = getattr(module, fn_name, None)
    if fn is None:
        return []
    try:
        frame = fn(**kwargs)
        return frame.to_dict("records") if frame is not None else []
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.debug("fetch %s failed: %s", fn_name, exc)
        return []


def fetch_expanded(
    akshare: Any,
    sample: list[dict[str, str]],
    out_csv: Path,
    *,
    seed_rows: list[dict[str, str]],
    checkpoint: int = DEFAULT_CHECKPOINT,
    sleep: float = 0.25,
) -> dict[str, int]:
    """Fetch seats for each event in ``sample`` and append to ``out_csv``.

    If ``out_csv`` does not exist, it is seeded with ``seed_rows`` (the existing 800)
    first. New rows are appended and the file flushed every ``checkpoint`` events so a
    throttle/kill leaves a usable partial file. Best-effort: an empty seat fetch (throttle
    / delisted / no detail) is skipped, never fatal."""
    fresh = not out_csv.exists()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    with out_csv.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if fresh:
            writer.writerow(SEAT_HEADER)
            for row in seed_rows:
                writer.writerow([row.get(col, "") for col in SEAT_HEADER])
            handle.flush()
            logger.info("seeded %d existing rows into %s", len(seed_rows), out_csv)
        for i, event in enumerate(sample, 1):
            code = event_code(event)
            date_str = str(event["event_date"]).replace("-", "")
            if code is None:
                skipped += 1
                continue
            buy_rows = _records(akshare, "stock_lhb_stock_detail_em",
                                symbol=code, date=date_str, flag="买入")
            if not buy_rows:
                skipped += 1
            else:
                writer.writerow(seat_row_from_buys(event, buy_rows))
                written += 1
            if i % checkpoint == 0 or i == len(sample):
                handle.flush()
                logger.info("seats: %d/%d fetched, %d written, %d skipped",
                            i, len(sample), written, skipped)
            time.sleep(sleep)
    return {"attempted": len(sample), "written": written, "skipped": skipped}


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B104 institutional-seat sample expansion")
    parser.add_argument("--events", type=Path,
                        default=Path("data/research/b094_youzi/events.csv"))
    parser.add_argument("--prices", type=Path,
                        default=Path("data/research/b094_youzi/prices.csv"))
    parser.add_argument("--existing-seats", type=Path,
                        default=Path("data/research/b094_youzi/seats_sample.csv"))
    parser.add_argument("--out", type=Path,
                        default=Path("data/research/b104_seats/seats_expanded.csv"))
    parser.add_argument("--target-total", type=int, default=DEFAULT_TARGET_TOTAL,
                        help="existing 800 + new; total seat events to reach")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--checkpoint", type=int, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="socket default timeout (s) so a hung call fails fast")
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--dry-run", action="store_true",
                        help="build + report the sample, do not fetch")
    cli = parser.parse_args(argv)

    socket.setdefaulttimeout(cli.timeout)

    covered = load_price_covered_tickers(cli.prices)
    existing_rows = load_seat_rows(cli.existing_seats)
    existing_keys = load_seat_keys(cli.existing_seats)
    # Resume: if the output already has rows, treat those keys as fetched too.
    out_keys = load_seat_keys(cli.out)
    already = existing_keys | out_keys
    events = load_events(cli.events)

    n_existing = len(existing_keys)
    target_new = max(0, cli.target_total - n_existing)
    # If resuming, subtract rows already appended to out (beyond the seeded existing).
    resumed_new = max(0, len(out_keys - existing_keys))
    target_new = max(0, target_new - resumed_new)

    sample = build_seed_sample(events, covered, already,
                               target_new=target_new, seed=cli.seed)
    logger.info(
        "covered_tickers=%d existing_seats=%d resumed_new=%d target_total=%d "
        "-> fetch %d new price-covered events (seed %d)",
        len(covered), n_existing, resumed_new, cli.target_total, len(sample), cli.seed,
    )

    if cli.dry_run:
        logger.info("dry-run: not fetching. sample head: %s",
                    [(r["event_date"], r["ticker"]) for r in sample[:5]])
        return 0

    try:
        akshare = importlib.import_module("akshare")
    except Exception:  # noqa: BLE001
        logger.error("akshare not importable — cannot fetch")
        return 1

    seed_rows = existing_rows if not cli.out.exists() else []
    stats = fetch_expanded(akshare, sample, cli.out, seed_rows=seed_rows,
                           checkpoint=cli.checkpoint, sleep=cli.sleep)
    final_keys = load_seat_keys(cli.out)
    logger.info("DONE: attempted=%d written=%d skipped=%d | out has %d total seat events",
                stats["attempted"], stats["written"], stats["skipped"], len(final_keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
