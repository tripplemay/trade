"""B037 F001 — ``python -m workbench_api.prices.cli fetch`` entrypoint.

Daily read-only price-snapshot ingest CLI. It fetches recent daily closes
through the B027 ``TiingoSnapshotLoader`` and persists them into the
``price_snapshot`` table (idempotent by ``(symbol, obs_date)``). The
production VM runs this once a day via a **systemd timer**
(``workbench/deploy/systemd/workbench-prices.timer``) — not an in-process
scheduler, so the app stays stateless and no APScheduler runtime dep is
introduced.

The symbol set is the **union of**:

* the held symbols in the latest ``AccountSnapshot`` (the Home Day P&L marks
  them to market), and
* the **strategy target universe** — every symbol the modes can target, taken
  from the SAME ``data_refresh.price_universe()`` the recommendation precompute
  is fed (B058 F002). Before this, the CLI priced only held symbols, so a paper
  account targeting a symbol the user does not already hold (e.g. the regime
  ETFs QQQ/VWO/IEF/TLT/DBC) had NO mark in ``price_snapshot`` → the paper engine
  skipped it → the book stranded in cash (S2). Pricing the target universe
  aligns the paper mark source with the recommendation price source.

The Home page's Day P&L marks positions to market by reading the two most
recent closes per symbol from this table, so a short look-back window
(default 7 calendar days) guarantees the latest + prior trading day land.

After the fetch, the CLI checks which target-universe symbols are still NOT
markable (fewer than two stored closes) and logs them loudly — coverage gaps
surface (B058 F002 "无市价响亮"), they never silently leave a paper book in cash.

Permanent product boundary **(r)** (B035 spec §3, B036 revision): this
CLI does **read-only data fetching only**. It composes ``loader →
PriceSnapshotRepository`` and never touches broker / order-ticket /
execution / recommendation code (reading the target universe is a read-only
data concern; ``data_refresh.price_universe`` imports no trade-execution
surface). ``tests/safety/test_market_scheduler_scope.py`` greps this module
(and the systemd unit) to enforce that.

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

from workbench_api.cli_clock import add_as_of_argument
from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.db.engine import get_engine
from workbench_api.db.models.price_snapshot import PriceSnapshot
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
    # Target-universe symbols still NOT markable after this run (fewer than two
    # stored closes). Surfaced so a coverage gap is loud, never silent (B058 F002).
    uncovered_targets: tuple[str, ...] = ()


def _build_loader() -> _Loader:
    """Construct the real Tiingo loader (requires ``TIINGO_API_KEY``).

    Imported lazily so a fake ``loader_factory`` in tests never touches
    the real loader's key-required constructor."""

    from workbench_api.data.tiingo_loader import TiingoSnapshotLoader

    return TiingoSnapshotLoader()


def held_symbols(session: Session) -> list[str]:
    """Distinct upper-cased symbols in the latest account snapshot.

    Empty when there is no snapshot / no positions (Day P&L stays null until
    holdings exist) — the strategy target universe is still priced regardless."""

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


def target_universe() -> set[str]:
    """Upper-cased strategy target universe — every symbol the modes can target.

    Reuses ``data_refresh.price_universe()`` (ETFs incl. the regime set + the
    B025 equities), the SAME universe the recommendation precompute is fed, so
    the paper mark source (``price_snapshot``) covers exactly what targets draw
    from (B058 F002 — one universe definition, no two-source split). Imported
    lazily to keep the CLI's import surface minimal; it pulls no trade-execution
    surface (boundary (r))."""

    from workbench_api.data_refresh.refresh import price_universe

    return {symbol.upper() for symbol in price_universe()}


def symbols_to_fetch(session: Session) -> list[str]:
    """Held symbols ∪ the strategy target universe (sorted, de-duplicated)."""

    return sorted(set(held_symbols(session)) | target_universe())


def _is_markable(rows: list[PriceSnapshot]) -> bool:
    """Whether ``rows`` (newest-first, ≤2) make the symbol markable for the paper
    engine: two closes (so the provider yields a mark) AND a strictly positive
    latest close (mirrors ``paper/engine._usable`` — a zero/negative close is a
    bad snapshot, not a buildable mark)."""

    return len(rows) == 2 and float(rows[0].close) > 0


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
    add_as_of_argument(fetch)
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
    uncovered: tuple[str, ...] = ()
    try:
        repo = PriceSnapshotRepository(session)
        targets = symbols_to_fetch(session)
        if not targets:
            logger.info("price_cli_no_symbols", extra={"run_date": run_date.isoformat()})
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

        # Coverage check (B058 F002): which target-universe symbols are still
        # NOT markable? A symbol is markable exactly as the paper engine builds
        # it — two stored closes (so the provider yields a mark) AND a strictly
        # positive latest close (paper/engine._usable treats a zero/negative
        # close as a bad snapshot, not a buildable mark; matching that here keeps
        # the coverage warning honest instead of a false all-clear). A paper book
        # targeting an unmarkable symbol would skip it and sit in cash, so surface
        # the gap loudly rather than letting it silently strand the account.
        uncovered = tuple(
            sorted(
                symbol
                for symbol in target_universe()
                if not _is_markable(repo.latest_two_by_symbol(symbol))
            )
        )
        if uncovered:
            logger.warning(
                "price_cli_uncovered_target_symbols: %d strategy target "
                "symbol(s) lack two closes after fetch and are NOT markable "
                "(%s) — paper books targeting them cannot build until priced.",
                len(uncovered),
                ",".join(uncovered),
            )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return FetchSummary(
        symbols=symbols, saved=saved, errors=errors, uncovered_targets=uncovered
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "fetch":
        return 2
    # B072 F003 — --as-of pins the fetch window's run date; omitted → today (UTC).
    summary = fetch_main(args, today=args.as_of)
    print(
        f"price-snapshot ingest done — symbols={summary.symbols} "
        f"saved={summary.saved} errors={summary.errors} "
        f"uncovered_targets={len(summary.uncovered_targets)}"
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
