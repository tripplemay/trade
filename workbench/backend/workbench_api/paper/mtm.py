"""B056 F002 — daily paper-trading mark-to-market job.

``python -m workbench_api.paper.mtm`` — the ``workbench-paper-mtm`` timer entry.
For every paper account, each run:

1. **Rebalances if due** — ``rebalance_if_due`` fires only when the strategy
   published a new allocation (a quarter rolled), at the day's close + real cost.
2. **Marks to market** — values the (possibly rebalanced) book at the latest
   close via the shared ``mark_to_market`` pipeline, computes per-asset P&L, and
   records one ``paper_nav_history`` point (idempotent on date), capturing the
   SPY close for the F003 benchmark overlay.

Forward-only: points accumulate from the activation day. Off the request path,
reads the stored strategy target + price snapshots only — never imports
``trade`` or contacts a broker (the scheduler-scope guard enforces this).
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.cli_clock import add_as_of_argument, resolve_now
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperNavHistoryRepository,
    PaperPositionRepository,
)
from workbench_api.monitoring.tracking import STRATEGY_BENCHMARK
from workbench_api.paper.pnl import compute_position_pnl
from workbench_api.paper.service import rebalance_if_due
from workbench_api.services.mark_to_market import compute_mark_to_market, marks_for
from workbench_api.services.prices_provider import DbPriceProvider, PriceProvider

logger = logging.getLogger(__name__)

# Default benchmark (master / regime / USD strategies). B080 F004 fix ① — the
# per-strategy benchmark comes from STRATEGY_BENCHMARK; cn_attack resolves to CSI300
# (read from cn_csi300.csv, since it is not in the price table). Anything not mapped
# stays "SPY" → the byte-identical pre-B080 path (Master zero-regression).
BENCHMARK_SYMBOL = "SPY"
_CSI300_RELPATH = ("snapshots", "benchmark", "cn_csi300.csv")


def _load_csi300_series() -> dict[date, float]:
    """Parse cn_csi300.csv (``date,close``) → {date: close}; {} when unavailable.

    Best-effort under ``WORKBENCH_DATA_ROOT`` (with a repo-relative fallback) — the
    daily job must not fail when the benchmark CSV is missing (cn_attack accounts
    then simply record a null benchmark_close for that day)."""

    data_root = os.environ.get("WORKBENCH_DATA_ROOT")
    candidates = []
    if data_root:
        candidates.append(Path(data_root).joinpath(*_CSI300_RELPATH))
    candidates.append(
        Path(__file__).resolve().parents[3].joinpath("data", *_CSI300_RELPATH)
    )
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return {}
    series: dict[date, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                series[date.fromisoformat(str(row["date"])[:10])] = float(row["close"])
            except (KeyError, ValueError):
                continue
    return series


def _csi300_close_on_or_before(series: dict[date, float], on_date: date) -> float | None:
    """The most recent CSI300 close on/before ``on_date`` (None if none / empty)."""

    eligible = [d for d in series if d <= on_date]
    return series[max(eligible)] if eligible else None


@dataclass(frozen=True, slots=True)
class MtmSummary:
    accounts: int
    points: int
    rebalanced: int


def run_daily_mtm(
    session: Session,
    *,
    on_date: date,
    now: datetime,
    provider: PriceProvider | None = None,
) -> MtmSummary:
    """Rebalance-if-due + mark-to-market every paper account; record nav points."""

    provider = provider or DbPriceProvider(session)
    acc_repo = PaperAccountRepository(session)
    pos_repo = PaperPositionRepository(session)
    nav_repo = PaperNavHistoryRepository(session)

    accounts = acc_repo.list_active()
    # Loaded once — cn_attack accounts read their CSI300 benchmark from it.
    csi300 = _load_csi300_series()
    points = 0
    rebalanced = 0
    for account in accounts:
        if rebalance_if_due(
            session, account, on_date=on_date, now=now, provider=provider
        ) is not None:
            rebalanced += 1

        benchmark = STRATEGY_BENCHMARK.get(account.strategy_id, BENCHMARK_SYMBOL)
        positions = pos_repo.list_by_account(account.id)
        symbols = {p.symbol.upper() for p in positions}
        # Only union SPY when this account benchmarks against it (master / regime).
        # cn_attack reads CSI300 from the CSV instead — SPY isn't in the price table
        # on a CN-only host, and fetching it would be wasted.
        if benchmark == BENCHMARK_SYMBOL:
            symbols = symbols | {BENCHMARK_SYMBOL}
        marks = marks_for(provider, symbols)
        close_marks = {sym: mark.latest_close for sym, mark in marks.items()}

        mtm = compute_mark_to_market(
            ((p.symbol, float(p.shares)) for p in positions),
            float(account.cash),
            marks,
        )
        pnl = compute_position_pnl(
            ((p.symbol, float(p.shares), float(p.avg_cost)) for p in positions),
            close_marks,
        )
        breakdown = [
            {
                "symbol": item.symbol,
                "shares": item.shares,
                "avg_cost": item.avg_cost,
                "close": item.close,
                "market_value": item.market_value,
                "unrealized_pnl": item.unrealized_pnl,
                "unrealized_pnl_pct": item.unrealized_pnl_pct,
            }
            for item in pnl
        ]
        # SPY strategies read the fetched mark (byte-identical to pre-B080); cn_attack
        # reads the CSI300 close on/before today from the CSV.
        benchmark_close = (
            close_marks.get(BENCHMARK_SYMBOL)
            if benchmark == BENCHMARK_SYMBOL
            else _csi300_close_on_or_before(csi300, on_date)
        )
        nav_repo.record_point(
            point_id=uuid.uuid4().hex,
            account_id=account.id,
            as_of_date=on_date,
            nav=mtm.nav,
            cash=float(account.cash),
            positions=breakdown,
            benchmark_close=benchmark_close,
            created_at=now,
        )
        points += 1

    session.commit()
    return MtmSummary(accounts=len(accounts), points=points, rebalanced=rebalanced)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``python -m workbench_api.paper.mtm`` (timer)."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.paper.mtm",
        description="B056 daily paper-trading mark-to-market job.",
    )
    add_as_of_argument(parser)
    args = parser.parse_args(argv)

    # B072 F003 — --as-of fast-forwards the mark/rebalance date; omitted → now (UTC).
    now = resolve_now(args.as_of)
    on_date = args.as_of or now.date()
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        summary = run_daily_mtm(session, on_date=on_date, now=now)
    finally:
        session.close()
    print(
        f"paper mtm done — accounts={summary.accounts} "
        f"points={summary.points} rebalanced={summary.rebalanced}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
