#!/usr/bin/env python
"""B094 — fetch 龙虎榜 (dragon-tiger) events + seat detail + prices for a 游资
(retail hot-money) seat FIRST-LOOK.

NOT product code. NOT the user's PRIMARY institutional-following goal (that needs the
paid Tushare ¥200 full-coverage LHB institutional seats and is deliberately left for
the user). This is the FREE, documented "second sleeve" of the smart-money backlog:
tracking 游资/打板 (chasing limit-ups) — a KNOWN crowded / loss-prone game. A NO-GO /
INCONCLUSIVE is the expected and fully valid outcome; no GO is manufactured.

Data (all free via akshare, no key):
  * EVENTS   ``stock_lhb_detail_em(start_date, end_date)`` — one row per LHB-listed
             stock per 上榜日: 代码/名称/上榜日/龙虎榜净买额 + a ``解读`` editorial tag
             ("实力游资买入" / "N家机构买入" / "主力做T" ...). Fetched monthly.
  * BRANCHES ``stock_lhb_hyyyb_em(start, end)`` — 活跃营业部 (active branch offices)
             with per-window buy/sell totals → aggregated into a buy-side appearance
             FREQUENCY table used to identify the well-known active 游资 seats.
  * SEATS    ``stock_lhb_stock_detail_em(symbol, date, flag)`` — the top-5 buy/sell
             seats for one (stock, date): 交易营业部名称 + 净额. Fetched for a bounded
             SAMPLE of events to compute the genuine seat-level 游资 net-buy signal and
             to validate the ``解读`` tag against the raw seat classification.
  * PRICES   ``stock_zh_a_daily(symbol=sh/sz+code, adjust='qfq')`` — qfq daily bars for
             the LHB stocks → strict-no-lookahead forward returns (entry t+1).

★游资 seat identification (a documented judgment call, see ``classify_branch``):
  机构 seats carry the exchange label "机构专用"; 沪/深股通 carry "股通专用". Everything
  else is a NAMED 营业部 (branch office) = 游资 candidate. The WELL-KNOWN active hot-money
  seats are then the named branches that appear MOST FREQUENTLY on the LHB buy side
  (frequency heuristic over the BRANCHES table). We report both the raw seat-level
  signal (游资 net buy summed over 游资-classified buy seats) and the cheap ``解读``-tag
  binary flag, and the agreement rate between them.

research-only / no broker / no real money / no production change / no paid data.
Best-effort per window/ticker (a failure is logged + skipped, never fatal).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import logging
import random
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Column names (§ verified 2026-07-05 against live akshare).
# --------------------------------------------------------------------------- #
EVENT_HEADER = ("event_date", "code", "ticker", "name", "lhb_net_buy", "jiedu", "reason")
BRANCH_HEADER = ("branch", "seat_class", "buy_windows", "buy_stock_count", "buy_amount")
SEAT_HEADER = (
    "event_date",
    "ticker",
    "youzi_buy_net",
    "youzi_top_net_buyer",
    "inst_buy_net",
    "n_buy_seats",
    "jiedu_is_youzi",
)
PRICE_HEADER = ("date", "ticker", "adj_close")

# stock_lhb_detail_em columns.
_E_CODE, _E_NAME, _E_DATE = "代码", "名称", "上榜日"
_E_NET, _E_JIEDU, _E_REASON = "龙虎榜净买额", "解读", "上榜原因"
# stock_lhb_hyyyb_em columns.
_H_BRANCH, _H_BUY_CNT, _H_BUY_AMT = "营业部名称", "买入个股数", "买入总金额"
# stock_lhb_stock_detail_em columns.
_S_BRANCH, _S_NET = "交易营业部名称", "净额"

# Sanity floor/spike guard for qfq prices (B092 saw pre-2017 corruption).
_PRICE_FLOOR = 0.01
_PRICE_SPIKE = 5.0  # a >5x single-bar jump is a corrupted split-adjust, drop the bar


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested offline).
# --------------------------------------------------------------------------- #
def classify_branch(name: object) -> str:
    """Classify an LHB seat by its 营业部/席位 name (the 游资 identification core).

    Returns one of ``机构`` (institutional — exchange label "机构专用"), ``股通``
    (northbound 沪/深股通 channel), or ``游资`` (a named retail branch office =
    hot-money candidate). Blank / unparseable names classify as ``游资`` only when a
    non-empty name remains; empty → ``unknown``.
    """
    text = str(name or "").strip()
    if not text:
        return "unknown"
    if "机构专用" in text:
        return "机构"
    if "股通" in text:  # 沪股通专用 / 深股通专用
        return "股通"
    return "游资"


def is_youzi_jiedu(jiedu: object) -> bool:
    """EastMoney ``解读`` editorial tag → is this a 游资 buy event? (cheap tag method).

    True only for a 游资 BUY interpretation ("实力游资买入"); a 游资 SELL ("实力游资卖出")
    is not a follow-buy signal.
    """
    text = str(jiedu or "")
    return "游资" in text and "买" in text and "卖" not in text


def code_to_symbol(code: object) -> str | None:
    """Bare 6-digit code -> stock_zh_a_daily symbol (``sh``/``sz`` + code)."""
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    return f"{'sh' if digits[0] in {'6', '9'} else 'sz'}{digits}"


def code_to_ticker(code: object) -> str | None:
    """Bare 6-digit code -> canonical ``NNNNNN.SH/.SZ`` ticker (join key)."""
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != 6:
        return None
    return f"{digits}.{'SH' if digits[0] in {'6', '9'} else 'SZ'}"


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


def month_windows(from_ym: str, to_ym: str) -> list[tuple[str, str]]:
    """Inclusive month windows ``[(YYYYMMDD_start, YYYYMMDD_end), ...]`` oldest first."""
    fy, fm = (int(p) for p in from_ym.split("-"))
    ty, tm = (int(p) for p in to_ym.split("-"))
    out: list[tuple[str, str]] = []
    year, month = fy, fm
    while (year, month) <= (ty, tm):
        start = date(year, month, 1)
        nxt = date(year + (month == 12), (month % 12) + 1, 1)
        last = date.fromordinal(nxt.toordinal() - 1)
        out.append((start.strftime("%Y%m%d"), last.strftime("%Y%m%d")))
        year, month = year + (month == 12), (month % 12) + 1
    return out


def youzi_seat_nets(seat_records: list[dict[str, Any]]) -> dict[str, float]:
    """Buy-side seat rows -> {'youzi': sum净额 over 游资 seats, 'inst': sum over 机构,
    'youzi_top': net of the single largest-net 游资 seat}. Pure; drives the seat-level
    signal + the tests. Non-buy (净额<=0) 游资 seats still count toward youzi net (they
    are on the BUY table but may have net-sold; the sum is the net 游资 posture)."""
    youzi = 0.0
    inst = 0.0
    youzi_top = 0.0
    for row in seat_records:
        seat_class = classify_branch(row.get(_S_BRANCH))
        net = coerce_float(row.get(_S_NET)) or 0.0
        if seat_class == "游资":
            youzi += net
            youzi_top = max(youzi_top, net)
        elif seat_class == "机构":
            inst += net
    return {"youzi": youzi, "inst": inst, "youzi_top": youzi_top}


def guard_price(prev: float | None, close: float) -> float | None:
    """Sanity floor/spike guard (B092 pre-2017 corruption). Drop non-positive / sub-floor
    bars and >5x single-bar spikes vs the previous kept close."""
    if close is None or close <= _PRICE_FLOOR:
        return None
    if prev is not None and prev > 0:
        ratio = close / prev
        if ratio > _PRICE_SPIKE or ratio < 1.0 / _PRICE_SPIKE:
            return None
    return close


# --------------------------------------------------------------------------- #
# Fetch (best-effort; never fatal).
# --------------------------------------------------------------------------- #
def _records(module: Any, fn_name: str, **kwargs: Any) -> list[dict[str, Any]]:
    fn = getattr(module, fn_name, None)
    if fn is None:
        return []
    try:
        frame = fn(**kwargs)
        return frame.to_dict("records") if frame is not None else []
    except Exception:  # noqa: BLE001 — best-effort
        return []


def fetch_events(akshare: Any, windows: list[tuple[str, str]], out: Path) -> tuple[int, list[dict]]:
    """Fetch all LHB events monthly -> events.csv. Returns (count, in-memory rows)."""
    rows: list[dict] = []
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(EVENT_HEADER)
        for i, (start, end) in enumerate(windows, 1):
            for rec in _records(akshare, "stock_lhb_detail_em", start_date=start, end_date=end):
                event_date = coerce_date(rec.get(_E_DATE))
                ticker = code_to_ticker(rec.get(_E_CODE))
                net = coerce_float(rec.get(_E_NET))
                if event_date is None or ticker is None:
                    continue
                row = {
                    "event_date": event_date.isoformat(),
                    "code": "".join(c for c in str(rec.get(_E_CODE)) if c.isdigit())[:6],
                    "ticker": ticker,
                    "name": str(rec.get(_E_NAME) or "").strip(),
                    "lhb_net_buy": round(net, 2) if net is not None else "",
                    "jiedu": str(rec.get(_E_JIEDU) or "").strip(),
                    "reason": str(rec.get(_E_REASON) or "").strip(),
                }
                writer.writerow([row[k] for k in EVENT_HEADER])
                rows.append(row)
            if i % 6 == 0 or i == len(windows):
                logger.info("events: %d/%d windows, %d rows", i, len(windows), len(rows))
            time.sleep(0.3)
    return len(rows), rows


def fetch_branches(akshare: Any, windows: list[tuple[str, str]], out: Path) -> int:
    """Aggregate 活跃营业部 buy-side appearance frequency across windows -> branches.csv,
    sorted by buy_windows desc. This is the 游资 frequency-heuristic source."""
    agg: dict[str, dict[str, float]] = {}
    for i, (start, end) in enumerate(windows, 1):
        for rec in _records(akshare, "stock_lhb_hyyyb_em", start_date=start, end_date=end):
            branch = str(rec.get(_H_BRANCH) or "").strip()
            if not branch:
                continue
            buy_cnt = coerce_float(rec.get(_H_BUY_CNT)) or 0.0
            buy_amt = coerce_float(rec.get(_H_BUY_AMT)) or 0.0
            slot = agg.setdefault(
                branch, {"buy_windows": 0.0, "buy_stock_count": 0.0, "buy_amount": 0.0}
            )
            if buy_cnt > 0:
                slot["buy_windows"] += 1
                slot["buy_stock_count"] += buy_cnt
                slot["buy_amount"] += buy_amt
        if i % 6 == 0 or i == len(windows):
            logger.info("branches: %d/%d windows, %d branches", i, len(windows), len(agg))
        time.sleep(0.3)
    ranked = sorted(agg.items(), key=lambda kv: kv[1]["buy_windows"], reverse=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(BRANCH_HEADER)
        for branch, slot in ranked:
            writer.writerow(
                [branch, classify_branch(branch), int(slot["buy_windows"]),
                 int(slot["buy_stock_count"]), round(slot["buy_amount"], 2)]
            )
    return len(agg)


def fetch_seats_sample(
    akshare: Any, events: list[dict], out: Path, *, sample_size: int, seed: int
) -> int:
    """For a bounded random SAMPLE of events, fetch top buy+sell seats and compute the
    seat-level 游资 net buy -> seats_sample.csv (validates the 解读 tag on raw seats)."""
    rng = random.Random(seed)
    pool = list(events)
    rng.shuffle(pool)
    sample = pool[:sample_size]
    written = 0
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(SEAT_HEADER)
        for i, ev in enumerate(sample, 1):
            code = ev["code"]
            date_str = ev["event_date"].replace("-", "")
            buy_rows = _records(akshare, "stock_lhb_stock_detail_em",
                                symbol=code, date=date_str, flag="买入")
            if not buy_rows:
                continue
            nets = youzi_seat_nets(buy_rows)
            writer.writerow([
                ev["event_date"], ev["ticker"], round(nets["youzi"], 2),
                round(nets["youzi_top"], 2), round(nets["inst"], 2),
                len(buy_rows), int(is_youzi_jiedu(ev["jiedu"])),
            ])
            written += 1
            if i % 50 == 0 or i == len(sample):
                logger.info("seats: %d/%d sampled, %d written", i, len(sample), written)
            time.sleep(0.25)
    return written


def fetch_prices(
    akshare: Any, tickers: list[str], out: Path, *, start: str, end: str
) -> tuple[int, int]:
    """qfq daily adj_close for each unique ticker -> prices.csv (long form). Applies the
    floor/spike guard. Returns (n_tickers_ok, n_bars)."""
    ok = 0
    bars = 0
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(PRICE_HEADER)
        for i, ticker in enumerate(tickers, 1):
            symbol = code_to_symbol(ticker.split(".")[0])
            if symbol is None:
                continue
            recs = _records(akshare, "stock_zh_a_daily",
                            symbol=symbol, adjust="qfq", start_date=start, end_date=end)
            prev: float | None = None
            wrote_any = False
            for rec in recs:
                bar_date = coerce_date(rec.get("date"))
                close = coerce_float(rec.get("close"))
                if bar_date is None or close is None:
                    continue
                kept = guard_price(prev, close)
                if kept is None:
                    continue
                writer.writerow([bar_date.isoformat(), ticker, round(kept, 4)])
                prev = kept
                bars += 1
                wrote_any = True
            if wrote_any:
                ok += 1
            if i % 50 == 0 or i == len(tickers):
                logger.info("prices: %d/%d tickers, %d ok, %d bars", i, len(tickers), ok, bars)
            time.sleep(0.2)
    return ok, bars


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B094 游资 seat first-look fetch")
    parser.add_argument("--from", dest="from_ym", default="2022-01")
    parser.add_argument("--to", dest="to_ym", default="2024-12")
    parser.add_argument("--out-dir", type=Path,
                        default=Path("data/research/b094_youzi"))
    parser.add_argument("--sample-size", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=94)
    parser.add_argument("--stages", default="events,branches,seats,prices",
                        help="comma list of stages to run")
    parser.add_argument("--price-start", default="20211201")
    parser.add_argument("--price-end", default="20250228")
    parser.add_argument("--max-tickers", type=int, default=0,
                        help="cap unique tickers for the price fetch (0 = all); a "
                             "deterministic random subset for a bounded first-look")
    cli = parser.parse_args(argv)

    try:
        akshare = importlib.import_module("akshare")
    except Exception:  # noqa: BLE001
        logger.error("akshare not importable — cannot fetch")
        return 1

    cli.out_dir.mkdir(parents=True, exist_ok=True)
    stages = {s.strip() for s in cli.stages.split(",") if s.strip()}
    windows = month_windows(cli.from_ym, cli.to_ym)
    logger.info("window %s..%s = %d months, stages=%s",
                cli.from_ym, cli.to_ym, len(windows), stages)

    events: list[dict] = []
    events_path = cli.out_dir / "events.csv"
    if "events" in stages:
        n, events = fetch_events(akshare, windows, events_path)
        logger.info("EVENTS done: %d rows -> %s", n, events_path)
    elif events_path.exists():
        with events_path.open(encoding="utf-8", newline="") as handle:
            events = list(csv.DictReader(handle))

    if "branches" in stages:
        n = fetch_branches(akshare, windows, cli.out_dir / "branches.csv")
        logger.info("BRANCHES done: %d branches", n)

    if "seats" in stages and events:
        # normalise loaded-from-disk rows (DictReader keeps strings; ok for seats)
        norm = [{"code": e["code"], "event_date": e["event_date"], "ticker": e["ticker"],
                 "jiedu": e.get("jiedu", "")} for e in events]
        n = fetch_seats_sample(akshare, norm, cli.out_dir / "seats_sample.csv",
                               sample_size=cli.sample_size, seed=cli.seed)
        logger.info("SEATS done: %d events with seat detail", n)

    if "prices" in stages and events:
        tickers = sorted({e["ticker"] for e in events if e.get("ticker")})
        if cli.max_tickers and len(tickers) > cli.max_tickers:
            rng = random.Random(cli.seed)
            tickers = sorted(rng.sample(tickers, cli.max_tickers))
            logger.info("prices: capped to %d/%d tickers (seed %d, deterministic subset)",
                        len(tickers), len({e['ticker'] for e in events}), cli.seed)
        ok, bars = fetch_prices(akshare, tickers, cli.out_dir / "prices.csv",
                                start=cli.price_start, end=cli.price_end)
        logger.info("PRICES done: %d/%d tickers ok, %d bars", ok, len(tickers), bars)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
