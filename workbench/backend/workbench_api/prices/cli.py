"""B037 F001 — ``python -m workbench_api.prices.cli fetch`` entrypoint.

Daily read-only price-snapshot ingest CLI. For every distinct symbol the
latest ``AccountSnapshot`` holds, it fetches the recent daily closes
through the B027 ``TiingoSnapshotLoader`` and persists them into the
``price_snapshot`` table (idempotent by ``(symbol, obs_date)``). The
production VM runs this once a day via a **systemd timer**
(``workbench/deploy/systemd/workbench-prices.timer``) — not an in-process
scheduler, so the app stays stateless and no APScheduler runtime dep is
introduced.

The Home page's Day P&L marks positions to market by reading the two most
recent closes per symbol from this table, so a short look-back window
(default 7 calendar days) guarantees the latest + prior trading day land.

Permanent product boundary **(r)** (B035 spec §3, B036 revision): this
CLI does **read-only data fetching only**. It composes ``loader →
PriceSnapshotRepository`` and never touches broker / order-ticket /
execution / recommendation code. ``tests/safety/test_market_scheduler_scope.py``
greps this module (and the systemd unit) to enforce that.

Flags:

``--lookback-days``  how many calendar days back to fetch (default 7).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS: int = 7
PRICE_SOURCE: str = "tiingo"


class _Loader(Protocol):
    """Structural type the price loader satisfies (read-only fetch).

    Both the real ``TiingoSnapshotLoader`` and the test fake match it."""

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]: ...


LoaderFactory = Callable[[], _Loader]


@dataclass(frozen=True, slots=True)
class FetchSummary:
    """Aggregate result of one CLI fetch run."""

    symbols: int
    saved: int
    errors: int


def _build_loader() -> _Loader:
    """Construct the real Tiingo loader (requires ``TIINGO_API_KEY``).

    Imported lazily so a fake ``loader_factory`` in tests never touches
    the real loader's key-required constructor."""

    from workbench_api.data.tiingo_loader import TiingoSnapshotLoader

    return TiingoSnapshotLoader()


def held_symbols(session: Session) -> list[str]:
    """Distinct upper-cased symbols in the latest account snapshot.

    Empty when there is no snapshot / no positions — the CLI then fetches
    nothing (Day P&L stays null until holdings exist)."""

    snapshot = AccountSnapshotRepository(session).latest()
    if snapshot is None:
        return []
    symbols: set[str] = set()
    for entry in snapshot.positions or []:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).upper()
        if symbol:
            symbols.add(symbol)
    return sorted(symbols)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.prices.cli",
        description="B037 price-snapshot ingest CLI — fetch daily closes for held symbols.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Fetch recent closes for held symbols.")
    fetch.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Calendar days back to fetch (default: %(default)s).",
    )
    return parser.parse_args(argv)


def fetch_main(
    args: argparse.Namespace,
    *,
    loader_factory: LoaderFactory | None = None,
    today: date | None = None,
) -> FetchSummary:
    """Drive the fetch loop. Returns aggregated counts.

    ``loader_factory`` is injectable for tests (swap the real Tiingo
    loader for a fake returning known bars); ``today`` pins the window."""

    run_date = today or datetime.now(UTC).date()
    from_date = run_date - timedelta(days=max(1, args.lookback_days))
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    symbols = 0
    saved = 0
    errors = 0
    try:
        repo = PriceSnapshotRepository(session)
        targets = held_symbols(session)
        if not targets:
            logger.info("price_cli_no_holdings", extra={"run_date": run_date.isoformat()})
            return FetchSummary(symbols=0, saved=0, errors=0)
        loader = (loader_factory or _build_loader)()
        for symbol in targets:
            symbols += 1
            try:
                bars = loader.fetch_daily_bars(symbol, from_date, run_date)
            except Exception:
                errors += 1
                logger.exception("price_cli_fetch_failure", extra={"symbol": symbol})
                continue
            for bar in bars:
                row = repo.save_if_new(
                    symbol=symbol,
                    obs_date=bar.bar_date,
                    close=float(bar.close),
                    source=PRICE_SOURCE,
                )
                if row is not None:
                    saved += 1
            # Commit per symbol so one symbol's failure can't roll back the
            # closes already persisted for earlier symbols.
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return FetchSummary(symbols=symbols, saved=saved, errors=errors)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "fetch":
        return 2
    summary = fetch_main(args)
    print(
        f"price-snapshot ingest done — symbols={summary.symbols} "
        f"saved={summary.saved} errors={summary.errors}"
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
